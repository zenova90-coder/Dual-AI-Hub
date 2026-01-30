import streamlit as st

import google.generativeai as genai

from openai import OpenAI



# 페이지 설정

st.set_page_config(page_title="Dual-AI Hub", layout="wide")

st.title("🤖 Dual-AI Insight Hub")



# --- 1. Secrets에서 API 키 가져오기 ---

try:

    gemini_api_key = st.secrets["GEMINI_API_KEY"]

    gpt_api_key = st.secrets["GPT_API_KEY"]

except FileNotFoundError:

    st.error("🚨 Secrets 설정이 안 되어 있습니다. Streamlit Settings를 확인하세요.")

    st.stop()



# --- 2. 모델 초기화 ---

genai.configure(api_key=gemini_api_key)

gpt_client = OpenAI(api_key=gpt_api_key)



# 세션 상태 초기화 (결론 데이터 추가)

if "g_resp" not in st.session_state: st.session_state.g_resp = ""

if "o_resp" not in st.session_state: st.session_state.o_resp = ""

if "g_an" not in st.session_state: st.session_state.g_an = ""

if "o_an" not in st.session_state: st.session_state.o_an = ""

if "final_con" not in st.session_state: st.session_state.final_con = "" # 최종 결론 저장용



# --- 3. [닥터 다온] 사용 가능한 모델 자동 진단 및 선택 ---

def get_available_gemini_model():

    try:

        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]

        preferred_order = ['models/gemini-1.5-flash', 'models/gemini-pro', 'models/gemini-1.0-pro']

        for model in preferred_order:

            if model in available_models:

                return model

        if available_models:

            return available_models[0]

        return None

    except Exception:

        return None



valid_model_name = get_available_gemini_model()

if not valid_model_name:

    valid_model_name = "gemini-pro"



# --- 탭 구성 (3단계 추가) ---

tab1, tab2, tab3 = st.tabs(["💬 1. 동시 질문", "📊 2. 교차 분석", "🏆 3. 최종 결론"])



# --- 탭 1: 질문하기 ---

with tab1:

    st.info("👋 사용자님 반갑습니다. 무엇을 도와드릴까요?")

    

    if user_input := st.chat_input("질문을 입력하세요..."):

        st.session_state.user_q = user_input # 질문 내용 저장

        st.write(f"**🙋‍♂️ 질문:** {user_input}")

        

        with st.spinner("다온과 루가 답변을 작성 중입니다..."):

            # 1. 다온 (Gemini)

            try:

                model = genai.GenerativeModel(valid_model_name.replace('models/', '')) 

                response = model.generate_content(user_input)

                st.session_state.g_resp = response.text

            except Exception as e:

                st.session_state.g_resp = f"❌ 다온 에러: {str(e)}"



            # 2. 루 (GPT)

            try:

                response = gpt_client.chat.completions.create(

                    model="gpt-4o",

                    messages=[{"role": "user", "content": user_input}]

                )

                st.session_state.o_resp = response.choices[0].message.content

            except Exception as e:

                st.session_state.o_resp = f"❌ 루 에러: {str(e)}"



        col1, col2 = st.columns(2)

        with col1:

            st.info(f"💎 다온 ({valid_model_name})")

            st.write(st.session_state.g_resp)

        with col2:

            st.success("🧠 루 (GPT-4o)")

            st.write(st.session_state.o_resp)

            

    elif st.session_state.g_resp:

         st.write(f"**🙋‍♂️ 질문:** {st.session_state.get('user_q', '')}")

         col1, col2 = st.columns(2)

         with col1:

             st.info(f"💎 다온")

             st.write(st.session_state.g_resp)

         with col2:

             st.success("🧠 루 (GPT-4o)")

             st.write(st.session_state.o_resp)



# --- 탭 2: 교차 분석 ---

with tab2:

    if st.button("교차 분석 시작"):

        if not st.session_state.g_resp or not st.session_state.o_resp:

            st.warning("먼저 1단계에서 질문을 입력해주세요.")

        else:

            with st.spinner("서로의 논리를 검증하는 중..."):

                # 다온 -> 루 분석

                try:

                    model = genai.GenerativeModel(valid_model_name.replace('models/', ''))

                    res = model.generate_content(f"다음은 '루(GPT)'의 답변입니다. 논리적 허점이나 보완할 점을 비판적으로 분석해주세요:\n{st.session_state.o_resp}")

                    st.session_state.g_an = res.text

                except Exception as e:

                    st.session_state.g_an = f"분석 실패: {e}"



                # 루 -> 다온 분석

                try:

                    res = gpt_client.chat.completions.create(

                        model="gpt-4o",

                        messages=[{"role":"user","content":f"다음은 '다온(Gemini)'의 답변입니다. 창의성과 감성적인 측면, 그리고 논리성을 평가해주세요:\n{st.session_state.g_resp}"}]

                    )

                    st.session_state.o_an = res.choices[0].message.content

                except Exception as e:

                    st.session_state.o_an = f"분석 실패: {e}"

            

            c1, c2 = st.columns(2)

            with c1:

                st.info("💎 다온의 비평")

                st.write(st.session_state.g_an)

            with c2:

                st.success("🧠 루의 평가")

                st.write(st.session_state.o_an)

    

    # 분석 결과 유지

    elif st.session_state.g_an:

        c1, c2 = st.columns(2)

        with c1:

            st.info("💎 다온의 비평")

            st.write(st.session_state.g_an)

        with c2:

            st.success("🧠 루의 평가")

            st.write(st.session_state.o_an)



# --- 탭 3: 최종 결론 (New!) ---

with tab3:

    st.subheader("🏆 루(GPT)가 내리는 최종 판결")

    st.caption("질문, 두 AI의 답변, 그리고 상호 비판 내용을 모두 종합하여 GPT-4o가 최종 결론을 내립니다.")



    if st.button("최종 결론 도출하기"):

        # 데이터가 다 있는지 확인

        if not st.session_state.g_an or not st.session_state.o_an:

            st.warning("먼저 '2. 교차 분석' 탭에서 분석을 완료해야 결론을 내릴 수 있습니다.")

        else:

            with st.spinner("루(GPT)가 모든 논의를 종합하여 최종 보고서를 작성 중입니다..."):

                try:

                    # 최종 결론을 위한 프롬프트 설계 (루에게 '의장' 역할 부여)

                    final_prompt = f"""

                    너는 논쟁을 중재하고 최종 결론을 내리는 '수석 의장'이다.

                    아래의 대화 내용을 모두 검토하고, 사용자에게 가장 도움이 되는 핵심 요약과 최종 결론을 작성하라.



                    [사용자 질문]

                    {st.session_state.get('user_q', '')}



                    [AI 1: 다온(Gemini)의 의견]

                    {st.session_state.g_resp}



                    [AI 2: 루(GPT)의 의견]

                    {st.session_state.o_resp}



                    [상호 비판 1: 다온의 지적]

                    {st.session_state.g_an}



                    [상호 비판 2: 루의 지적]

                    {st.session_state.o_an}



                    ---

                    [작성 가이드]

                    1. 두 의견의 공통점과 차이점을 간략히 짚어줄 것.

                    2. 상호 비판에서 나온 유효한 지적을 반영할 것.

                    3. 결론적으로 사용자가 어떻게 이해하거나 행동하면 좋을지 '최종 조언'을 명확히 제시할 것.

                    4. 톤앤매너: 전문적이고 명쾌하게.

                    """



                    # GPT-4o 호출

                    res = gpt_client.chat.completions.create(

                        model="gpt-4o",

                        messages=[{"role": "user", "content": final_prompt}]

                    )

                    st.session_state.final_con = res.choices[0].message.content

                

                except Exception as e:

                    st.error(f"결론 도출 실패: {e}")



    # 결과 보여주기

    if st.session_state.final_con:

        st.markdown("---")

        st.markdown(st.session_state.final_con)


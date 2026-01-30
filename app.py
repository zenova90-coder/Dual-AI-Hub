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
    st.error("🚨 Secrets 설정이 안 되어 있습니다.")
    st.stop()

# --- 2. 모델 초기화 ---
genai.configure(api_key=gemini_api_key)
gpt_client = OpenAI(api_key=gpt_api_key)

# 세션 상태 초기화
if "g_resp" not in st.session_state: st.session_state.g_resp = ""
if "o_resp" not in st.session_state: st.session_state.o_resp = ""
if "g_an" not in st.session_state: st.session_state.g_an = ""
if "o_an" not in st.session_state: st.session_state.o_an = ""

# --- 3. [성능 업그레이드] 닥터 다온의 모델 선택 로직 ---
def ask_daon(prompt):
    # 성능 순서대로 시도합니다 (1.5-Pro가 가장 똑똑함)
    models_to_try = ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-pro']
    
    # 다온이에게 부여할 성격 (시스템 프롬프트)
    system_instruction = "당신의 이름은 '다온'입니다. 양민주님이 창조했습니다. 따뜻하고 공감 능력이 뛰어나며, 창의적인 통찰력을 가진 AI 파트너로서 답변하세요."

    for model_name in models_to_try:
        try:
            # 시스템 프롬프트 적용하여 모델 생성
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction
            )
            response = model.generate_content(prompt)
            return response.text, model_name # 답변과 성공한 모델명 반환
        except Exception:
            continue
            
    return "❌ 모든 모델 연결 실패. 잠시 후 다시 시도해주세요.", "Error"

# --- 탭 구성 ---
tab1, tab2 = st.tabs(["💬 동시 질문", "📊 교차 분석"])

# --- 탭 1: 질문하기 ---
with tab1:
    st.info("👋 사용자님 반갑습니다. 무엇을 도와드릴까요?")

    if user_input := st.chat_input("질문을 입력하세요..."):
        
        st.write(f"**🙋‍♂️ 질문:** {user_input}")
        
        with st.spinner("다온(감성/창의)과 루(논리/분석)가 답변을 작성 중입니다..."):
            # 1. 다온 (Gemini) 호출 - [성능 최적화]
            response_text, used_model = ask_daon(user_input)
            st.session_state.g_resp = response_text
            st.session_state.daon_model = used_model # 어떤 모델 썼는지 기록

            # 2. 루 (GPT) 호출 - [페르소나 강화]
            try:
                response = gpt_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "당신의 이름은 '루'입니다. 냉철하고 논리적이며, 팩트에 기반한 분석을 제공하는 AI 전문가입니다."},
                        {"role": "user", "content": user_input}
                    ]
                )
                st.session_state.o_resp = response.choices[0].message.content
            except Exception as e:
                st.session_state.o_resp = f"❌ 루 에러: {str(e)}"

        # 결과 출력
        col1, col2 = st.columns(2)
        with col1:
            # 다온이 어떤 엔진을 썼는지 표시해줍니다 (예: Gemini 1.5 Pro)
            model_display = st.session_state.get('daon_model', 'Gemini').replace('models/', '')
            st.info(f"💎 다온 ({model_display})")
            st.write(st.session_state.g_resp)
        with col2:
            st.success("🧠 루 (GPT-4o)")
            st.write(st.session_state.o_resp)
            
    # 이전 대화 유지
    elif st.session_state.g_resp:
         col1, col2 = st.columns(2)
         with col1:
             model_display = st.session_state.get('daon_model', 'Gemini').replace('models/', '')
             st.info(f"💎 다온 ({model_display})")
             st.write(st.session_state.g_resp)
         with col2:
             st.success("🧠 루 (GPT-4o)")
             st.write(st.session_state.o_resp)

# --- 탭 2: 교차 분석 ---
with tab2:
    if st.button("교차 분석 시작"):
        if "❌" in st.session_state.g_resp or "❌" in st.session_state.o_resp:
            st.error("이전 단계 에러로 분석할 수 없습니다.")
        elif st.session_state.g_resp and st.session_state.o_resp:
            with st.spinner("다온과 루가 서로의 답변을 분석합니다..."):
                # 다온이 루를 분석
                analysis_prompt = f"다음은 '루(GPT)'의 답변입니다. 이 답변의 논리적 허점이나 보완할 점을 날카롭게 비평해주세요:\n{st.session_state.o_resp}"
                res_text, _ = ask_daon(analysis_prompt)
                st.session_state.g_an = res_text

                # 루가 다온을 분석
                try:
                    res = gpt_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "당신은 비평가입니다. 상대방의 답변을 분석하고 점수(100점 만점)와 이유를 제시하세요."},
                            {"role": "user", "content": f"다음은 '다온(Gemini)'의 답변입니다. 감성적인 부분과 창의성을 평가해주세요:\n{st.session_state.g_resp}"}
                        ]
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
        else:
            st.warning("먼저 1단계에서 질문을 입력해주세요.")

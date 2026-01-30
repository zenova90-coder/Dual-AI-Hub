import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import os
import json
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="Dual-AI Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# --- 1. API 키 설정 ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
except FileNotFoundError:
    st.error("🚨 Secrets 설정이 안 되어 있습니다. Streamlit Settings를 확인하세요.")
    st.stop()

# --- 2. 모델 초기화 ---
genai.configure(api_key=gemini_api_key)
gpt_client = OpenAI(api_key=gpt_api_key)

# 세션 상태 초기화
if "g_resp" not in st.session_state: st.session_state.g_resp = ""
if "o_resp" not in st.session_state: st.session_state.o_resp = ""
if "g_an" not in st.session_state: st.session_state.g_an = ""
if "o_an" not in st.session_state: st.session_state.o_an = ""
if "final_con" not in st.session_state: st.session_state.final_con = "" 
if "user_q" not in st.session_state: st.session_state.user_q = "" # 질문 기억용

# --- 3. [핵심] 사용 가능한 모델 자동 진단 및 선택 ---
# 이 함수가 404 에러를 막아주는 핵심입니다!
def get_available_gemini_model():
    try:
        # 1. 사용 가능한 모델 목록을 서버에 물어봅니다.
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 2. 우리가 원하는 순서대로 찾아봅니다. (최신 Flash 우선)
        preferred_order = ['models/gemini-1.5-flash', 'models/gemini-pro', 'models/gemini-1.0-pro']
        
        for model in preferred_order:
            if model in available_models:
                return model
        
        # 3. 없으면 목록에 있는 거 아무거나라도 가져옵니다.
        if available_models:
            return available_models[0]
            
        return None
    except Exception:
        return None

# 모델 결정
valid_model_name = get_available_gemini_model()
if not valid_model_name:
    # 정말 못 찾겠으면 기본값 (하지만 위 함수에서 대부분 찾아냅니다)
    valid_model_name = "gemini-pro"

# --- 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["💬 1. 동시 질문", "📊 2. 교차 분석", "🏆 3. 최종 결론"])

# --- 탭 1: 질문하기 ---
with tab1:
    st.info("👋 사용자님 반갑습니다. 무엇을 도와드릴까요?")
    
    if user_input := st.chat_input("질문을 입력하세요..."):
        st.session_state.user_q = user_input
        st.write(f"**🙋‍♂️ 질문:** {user_input}")
        
        with st.spinner("다온과 루가 답변을 작성 중입니다..."):
            # 1. 다온 (Gemini) - 자동 선택된 모델 사용
            try:
                # 모델 이름에서 'models/'를 빼고 호출해야 할 때도 있어서 처리
                safe_model_name = valid_model_name.replace('models/', '')
                model = genai.GenerativeModel(safe_model_name) 
                response = model.generate_content(user_input)
                st.session_state.g_resp = response.text
            except Exception as e:
                st.session_state.g_resp = f"❌ 다온 에러 (시도한 모델: {valid_model_name}):\n{str(e)}"

            # 2. 루 (GPT)
            try:
                response = gpt_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": user_input}]
                )
                st.session_state.o_resp = response.choices[0].message.content
            except Exception as e:
                st.session_state.o_resp = f"❌ 루 에러: {str(e)}"

        # 결과 출력
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"💎 다온 (Gemini)")
            st.write(st.session_state.g_resp)
        with col2:
            st.success("🧠 루 (Chat GPT)")
            st.write(st.session_state.o_resp)
            
    # 이전 결과 보여주기
    elif st.session_state.g_resp:
         st.write(f"**🙋‍♂️ 질문:** {st.session_state.get('user_q', '')}")
         col1, col2 = st.columns(2)
         with col1:
             st.info(f"💎 다온 (Gemini)")
             st.write(st.session_state.g_resp)
         with col2:
             st.success("🧠 루 (Chat GPT)")
             st.write(st.session_state.o_resp)

# --- 탭 2: 교차 분석 ---
with tab2:
    if st.button("교차 분석 시작"):
        if not st.session_state.g_resp or not st.session_state.o_resp:
            st.warning("먼저 1단계에서 질문을 입력해주세요.")
        else:
            with st.spinner("서로의 논리를 검증하는 중..."):
                # 다온 -> 루 분석 (안전 설정 적용)
                try:
                    safe_model_name = valid_model_name.replace('models/', '')
                    model = genai.GenerativeModel(safe_model_name)
                    
                    # 비판 허용 설정
                    safety_settings = [
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                    ]
                    
                    prompt = f"다음은 '루(GPT)'의 답변입니다. 논리적 허점이나 보완할 점을 비판적으로 분석해주세요:\n{st.session_state.o_resp}"
                    res = model.generate_content(prompt, safety_settings=safety_settings)
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

# --- 탭 3: 최종 결론 ---
with tab3:
    st.subheader("🏆 루(GPT)가 내리는 최종 판결")
    st.caption("질문, 답변, 상호 비판을 모두 종합하여 최종 결론을 내립니다.")

    if st.button("최종 결론 도출하기"):
        if not st.session_state.g_an or not st.session_state.o_an:
            st.warning("먼저 '2. 교차 분석' 탭에서 분석을 완료해야 결론을 내릴 수 있습니다.")
        else:
            with st.spinner("최종 보고서 작성 중..."):
                try:
                    final_prompt = f"""
                    너는 최종 의사결정권자다. 아래 내용을 종합하여 사용자에게 명쾌한 결론을 내려라.

                    [질문] {st.session_state.user_q}
                    [다온 답변] {st.session_state.g_resp}
                    [루 답변] {st.session_state.o_resp}
                    [다온 비평] {st.session_state.g_an}
                    [루 비평] {st.session_state.o_an}

                    작성 가이드:
                    1. 핵심 쟁점 요약
                    2. 양측 의견의 장단점 비교
                    3. 최종 조언 (구체적으로)
                    """

                    res = gpt_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": final_prompt}]
                    )
                    st.session_state.final_con = res.choices[0].message.content
                
                except Exception as e:
                    st.error(f"결론 도출 실패: {e}")

    if st.session_state.final_con:
        st.markdown("---")
        st.markdown(st.session_state.final_con)

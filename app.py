import streamlit as st
import google.generativeai as genai
from openai import OpenAI

# 페이지 설정
st.set_page_config(page_title="Dual-AI Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# --- 1. Secrets에서 API 키 가져오기 (자동 로그인) ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
except FileNotFoundError:
    st.error("🚨 Secrets가 설정되지 않았습니다. Streamlit Settings에서 키를 넣어주세요.")
    st.stop()

# --- 2. 모델 초기화 ---
# Gemini 설정 (최신 1.5 Flash 모델 사용)
genai.configure(api_key=gemini_api_key)

# GPT 설정
gpt_client = OpenAI(api_key=gpt_api_key)

# 세션 상태 초기화
if "g_resp" not in st.session_state: st.session_state.g_resp = ""
if "o_resp" not in st.session_state: st.session_state.o_resp = ""
if "g_an" not in st.session_state: st.session_state.g_an = ""
if "o_an" not in st.session_state: st.session_state.o_an = ""

tab1, tab2 = st.tabs(["💬 동시 질문", "📊 교차 분석"])

# --- 탭 1: 질문하기 ---
with tab1:
    st.info("💡 현재 '다온'님의 API 키로 자동 연결되어 있습니다. 바로 질문하세요!")
    user_input = st.text_area("질문을 입력하세요:", height=150)
    
    if st.button("질문 보내기"):
        if not user_input:
            st.warning("질문을 입력해주세요.")
        else:
            with st.spinner("Gemini와 GPT가 답변을 작성 중입니다..."):
                # Gemini 호출
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(user_input)
                    st.session_state.g_resp = response.text
                except Exception as e:
                    st.session_state.g_resp = f"❌ Gemini 에러: {str(e)}"

                # GPT 호출
                try:
                    response = gpt_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": user_input}]
                    )
                    st.session_state.o_resp = response.choices[0].message.content
                except Exception as e:
                    st.session_state.o_resp = f"❌ GPT 에러: {str(e)}"

            col1, col2 = st.columns(2)
            with col1:
                st.info("💎 Gemini (1.5 Flash)")
                st.write(st.session_state.g_resp)
            with col2:
                st.success("🧠 GPT (4o)")
                st.write(st.session_state.o_resp)

# --- 탭 2: 교차 분석 ---
with tab2:
    if st.button("교차 분석 시작"):
        if "❌" in st.session_state.g_resp or "❌" in st.session_state.o_resp:
            st.error("이전 단계에서 에러가 발생하여 분석할 수 없습니다.")
        elif st.session_state.g_resp and st.session_state.o_resp:
            with st.spinner("서로 채점하는 중..."):
                # Gemini가 분석
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    res = model.generate_content(f"다음 내용을 비판적으로 평가해줘:\n{st.session_state.o_resp}")
                    st.session_state.g_an = res.text
                except Exception as e:
                    st.session_state.g_an = f"분석 실패: {e}"

                # GPT가 분석
                try:
                    res = gpt_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role":"user","content":f"다음 내용을 평가해줘:\n{st.session_state.g_resp}"}]
                    )
                    st.session_state.o_an = res.choices[0].message.content
                except Exception as e:
                    st.session_state.o_an = f"분석 실패: {e}"
            
            c1, c2 = st.columns(2)
            with c1:
                st.info("Gemini의 평가")
                st.write(st.session_state.g_an)
            with c2:
                st.success("GPT의 평가")
                st.write(st.session_state.o_an)
        else:
            st.warning("먼저 1단계에서 질문을 입력하세요.")

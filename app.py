import streamlit as st
import google.generativeai as genai  # 엔진 교체 완료
from openai import OpenAI

# 페이지 설정
st.set_page_config(page_title="Dual-AI Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# 사이드바 API 설정
with st.sidebar:
    st.header("🔑 API 설정")
    gemini_key = st.text_input("Gemini API Key", type="password")
    gpt_key = st.text_input("GPT API Key", type="password")

# 세션 상태 초기화
if "g_resp" not in st.session_state: st.session_state.g_resp = ""
if "o_resp" not in st.session_state: st.session_state.o_resp = ""
if "g_an" not in st.session_state: st.session_state.g_an = ""
if "o_an" not in st.session_state: st.session_state.o_an = ""

tab1, tab2 = st.tabs(["💬 동시 질문", "📊 교차 분석"])

# --- 탭 1 ---
with tab1:
    user_input = st.text_area("질문을 입력하세요:", height=150)
    if st.button("질문 보내기"):
        if not gemini_key or not gpt_key:
            st.error("사이드바에 API 키를 입력해주세요!")
        else:
            with st.spinner("생각 중..."):
                # 1. Gemini 호출 (안정화 버전)
                try:
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel('gemini-pro') # 가장 안정적인 모델 사용
                    response = model.generate_content(user_input)
                    st.session_state.g_resp = response.text
                except Exception as e:
                    st.error(f"Gemini 에러: {e}")
                
                # 2. GPT 호출
                try:
                    o_client = OpenAI(api_key=gpt_key)
                    res = o_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":user_input}])
                    st.session_state.o_resp = res.choices[0].message.content
                except Exception as e:
                    st.error(f"GPT 에러: {e}")

            col1, col2 = st.columns(2)
            with col1:
                st.info("Gemini")
                st.write(st.session_state.g_resp)
            with col2:
                st.success("GPT")
                st.write(st.session_state.o_resp)

# --- 탭 2 ---
with tab2:
    if st.button("교차 분석 시작"):
        if st.session_state.g_resp and st.session_state.o_resp:
            with st.spinner("분석 중..."):
                # Gemini가 분석
                try:
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel('gemini-pro')
                    res = model.generate_content(f"다음 내용을 비판적으로 분석해줘:\n{st.session_state.o_resp}")
                    st.session_state.g_an = res.text
                except: st.session_state.g_an = "분석 실패"

                # GPT가 분석
                try:
                    o_client = OpenAI(api_key=gpt_key)
                    res = o_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":f"다음 내용을 평가해줘:\n{st.session_state.g_resp}"}])
                    st.session_state.o_an = res.choices[0].message.content
                except: st.session_state.o_an = "분석 실패"
            
            c1, c2 = st.columns(2)
            with c1:
                st.info("Gemini의 평가")
                st.write(st.session_state.g_an)
            with c2:
                st.success("GPT의 평가")
                st.write(st.session_state.o_an)
        else:
            st.warning("먼저 질문을 입력하세요.")

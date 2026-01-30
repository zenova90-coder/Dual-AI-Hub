import streamlit as st
from google import genai
from openai import OpenAI

# 탭 구조 및 기본 UI
st.set_page_config(page_title="Dual-AI Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# 사이드바에서 키 입력 받기 (가장 안전한 방식)
with st.sidebar:
    st.header("🔑 API 설정")
    gemini_key = st.text_input("Gemini API Key", type="password")
    gpt_key = st.text_input("GPT API Key", type="password")

tab1, tab2 = st.tabs(["💬 동시 질문", "📊 교차 분석"])

if "g_resp" not in st.session_state: st.session_state.g_resp = ""
if "o_resp" not in st.session_state: st.session_state.o_resp = ""

with tab1:
    user_input = st.text_area("질문을 입력하세요:")
    if st.button("질문 보내기"):
        if not gemini_key or not gpt_key:
            st.error("사이드바에 API 키를 먼저 입력해주세요!")
        else:
            # Gemini 호출
            g_client = genai.Client(api_key=gemini_key)
            res_g = g_client.models.generate_content(model="gemini-2.0-flash", contents=user_input)
            st.session_state.g_resp = res_g.text
            
            # GPT 호출
            o_client = OpenAI(api_key=gpt_key)
            res_o = o_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": user_input}]
            )
            st.session_state.o_resp = res_o.choices[0].message.content

            col1, col2 = st.columns(2)
            with col1:
                st.info("### Gemini")
                st.write(st.session_state.g_resp)
            with col2:
                st.success("### GPT")
                st.write(st.session_state.o_resp)

with tab2:
    if st.session_state.g_resp:
        st.subheader("🔍 AI 상호 분석 (준비됨)")
        st.write("데이터가 성공적으로 로드되었습니다. Phase 3에서 분석 로직을 추가할 예정입니다.")

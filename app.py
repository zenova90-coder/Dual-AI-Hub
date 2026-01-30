import streamlit as st
from google import genai
from openai import OpenAI

# 페이지 설정
st.set_page_config(page_title="Dual-AI Insight Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# 사이드바 API 설정
with st.sidebar:
    st.header("🔑 API 설정")
    gemini_key = st.text_input("Gemini API Key", type="password")
    gpt_key = st.text_input("GPT API Key", type="password")

# 세션 상태 초기화 (데이터 유지용)
if "g_resp" not in st.session_state: st.session_state.g_resp = ""
if "o_resp" not in st.session_state: st.session_state.o_resp = ""
if "g_analysis" not in st.session_state: st.session_state.g_analysis = ""
if "o_analysis" not in st.session_state: st.session_state.o_analysis = ""

tab1, tab2 = st.tabs(["💬 Step 1: 동시 질문", "📊 Step 2: 교차 분석"])

# --- 첫 번째 탭: 질문 및 응답 ---
with tab1:
    user_input = st.text_area("질문을 입력하세요:", height=150)
    if st.button("질문 보내기"):
        if not gemini_key or not gpt_key:
            st.error("사이드바에 API 키를 모두 입력해주세요!")
        else:
            with st.spinner("두 AI가 답변을 작성 중입니다..."):
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
                st.info("### 💎 Gemini Response")
                st.write(st.session_state.g_resp)
            with col2:
                st.success("### 🧠 GPT Response")
                st.write(st.session_state.o_resp)

# --- 두 번째 탭: 교차 분석 ---
with tab2:
    st.subheader("🧐 AI 상호 교차 분석")
    
    if not st.session_state.g_resp or not st.session_state.o_resp:
        st.warning("먼저 '동시 질문' 탭에서 답변을 생성해주세요.")
    else:
        if st.button("교차 분석 시작하기"):
            with st.spinner("서로의 답변을 분석하는 중..."):
                # Gemini가 GPT 답변 분석
                g_client = genai.Client(api_key=gemini_key)
                g_prompt = f"다음은 다른 AI(GPT)의 답변입니다. 이 답변의 장단점을 분석하고 보완할 점을 알려주세요:\n\n{st.session_state.o_resp}"
                res_g_analysis = g_client.models.generate_content(model="gemini-2.0-flash", contents=g_prompt)
                st.session_state.g_analysis = res_g_analysis.text

                # GPT가 Gemini 답변 분석
                o_client = OpenAI(api_key=gpt_key)
                o_prompt = f"다음은 다른 AI(Gemini)의 답변입니다. 이 답변의 정확성과 논리성을 평가하고 보완점을 제시하세요:\n\n{st.session_state.g_resp}"
                res_o_analysis = o_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": o_prompt}]
                )
                st.session_state.o_analysis = res_o_analysis.choices[0].message.content

        # 분석 결과 표시
        if st.session_state.g_analysis:
            col1, col2 = st.columns(2)
            with col1:
                st.info("### 💎 Gemini의 GPT 분석")
                st.write(st.session_state.g_analysis)
            with col2:
                st.success("### 🧠 GPT의 Gemini 분석")
                st.write(st.session_state.o_analysis)

import streamlit as st
import sys
import subprocess

# --- 1. 강제 설치 섹션 (도구가 없으면 스스로 설치합니다) ---
def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    from google import genai
except ImportError:
    # google-genai가 없으면 설치하고 다시 불러오기
    install_package("google-genai")
    from google import genai

try:
    from openai import OpenAI
except ImportError:
    # openai가 없으면 설치하고 다시 불러오기
    install_package("openai")
    from openai import OpenAI

# --- 2. 메인 프로그램 시작 ---
st.set_page_config(page_title="Dual-AI Insight Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# 사이드바 API 설정
with st.sidebar:
    st.header("🔑 API 설정")
    st.caption("발급받은 키를 아래에 입력하고 엔터를 누르세요.")
    gemini_key = st.text_input("Gemini API Key", type="password")
    gpt_key = st.text_input("GPT API Key", type="password")

# 세션 상태 초기화
if "g_resp" not in st.session_state: st.session_state.g_resp = ""
if "o_resp" not in st.session_state: st.session_state.o_resp = ""
if "g_analysis" not in st.session_state: st.session_state.g_analysis = ""
if "o_analysis" not in st.session_state: st.session_state.o_analysis = ""

tab1, tab2 = st.tabs(["💬 Step 1: 동시 질문", "📊 Step 2: 교차 분석"])

# --- 탭 1: 질문하기 ---
with tab1:
    user_input = st.text_area("질문을 입력하세요:", height=150)
    if st.button("질문 보내기"):
        if not gemini_key or not gpt_key:
            st.error("⬅️ 왼쪽 사이드바에 API 키를 먼저 입력해주세요!")
        else:
            with st.spinner("Gemini와 GPT가 답변을 작성 중입니다..."):
                try:
                    # Gemini 호출
                    g_client = genai.Client(api_key=gemini_key)
                    res_g = g_client.models.generate_content(model="gemini-2.0-flash", contents=user_input)
                    st.session_state.g_resp = res_g.text
                except Exception as e:
                    st.error(f"Gemini 오류: {e}")

                try:
                    # GPT 호출
                    o_client = OpenAI(api_key=gpt_key)
                    res_o = o_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": user_input}]
                    )
                    st.session_state.o_resp = res_o.choices[0].message.content
                except Exception as e:
                    st.error(f"GPT 오류: {e}")

            if st.session_state.g_resp and st.session_state.o_resp:
                col1, col2 = st.columns(2)
                with col1:
                    st.info("### 💎 Gemini Response")
                    st.write(st.session_state.g_resp)
                with col2:
                    st.success("### 🧠 GPT Response")
                    st.write(st.session_state.o_resp)

# --- 탭 2: 교차 분석 ---
with tab2:
    st.subheader("🧐 AI 상호 교차 분석")
    
    if not st.session_state.g_resp or not st.session_state.o_resp:
        st.warning("먼저 첫 번째 탭에서 질문을 하고 답변을 받아주세요.")
    else:
        if st.button("교차 분석 시작하기"):
            if not gemini_key or not gpt_key:
                st.error("API 키가 필요합니다.")
            else:
                with st.spinner("서로의 답변을 채점하는 중..."):
                    try:
                        # Gemini가 GPT 분석
                        g_client = genai.Client(api_key=gemini_key)
                        g_prompt = f"다음은 다른 AI(GPT)의 답변입니다. 이 답변의 장단점을 분석해줘:\n\n{st.session_state.o_resp}"
                        res_g_analysis = g_client.models.generate_content(model="gemini-2.0-flash", contents=g_prompt)
                        st.session_state.g_analysis = res_g_analysis.text

                        # GPT가 Gemini 분석
                        o_client = OpenAI(api_key=gpt_key)
                        o_prompt = f"다음은 다른 AI(Gemini)의 답변입니다. 이 답변의 정확성을 평가해줘:\n\n{st.session_state.g_resp}"
                        res_o_analysis = o_client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": o_prompt}]
                        )
                        st.session_state.o_analysis = res_o_analysis.choices[0].message.content
                    except Exception as e:
                        st.error(f"분석 중 오류 발생: {e}")

        # 결과 표시
        if st.session_state.g_analysis:
            col1, col2 = st.columns(2)
            with col1:
                st.info("### 💎 Gemini의 평가")
                st.write(st.session_state.g_analysis)
            with col2:
                st.success("### 🧠 GPT의 평가")
                st.write(st.session_state.o_analysis)

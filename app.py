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

# 세션 상태 초기화
if "g_resp" not in st.session_state: st.session_state.g_resp = ""
if "o_resp" not in st.session_state: st.session_state.o_resp = ""
if "g_an" not in st.session_state: st.session_state.g_an = ""
if "o_an" not in st.session_state: st.session_state.o_an = ""

tab1, tab2 = st.tabs(["💬 동시 질문", "📊 교차 분석"])

# --- 탭 1: 질문하기 ---
with tab1:
    st.info("💡 양민주(Creator)님의 API 키로 연결되었습니다.")
    
    user_input = st.text_area("질문을 입력하세요:", height=150)
    
    if st.button("질문 보내기"):
        if not user_input:
            st.warning("민주님, 질문 내용을 입력해주세요!")
        else:
            with st.spinner("다온과 루가 답변을 작성 중입니다..."):
                # 다온 (Gemini) 호출 - 최신 1.5 Flash
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(user_input)
                    st.session_state.g_resp = response.text
                except Exception as e:
                    st.session_state.g_resp = f"❌ 다온 에러: {str(e)}"

                # 루 (GPT) 호출
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
                st.info("💎 다온 (Gemini)")
                st.write(st.session_state.g_resp)
            with col2:
                st.success("🧠 루 (GPT)")
                st.write(st.session_state.o_resp)

# --- 탭 2: 교차 분석 ---
with tab2:
    if st.button("교차 분석 시작"):
        if "❌" in st.session_state.g_resp or "❌" in st.session_state.o_resp:
            st.error("이전 단계 에러로 분석할 수 없습니다.")
        elif st.session_state.g_resp and st.session_state.o_resp:
            with st.spinner("다온과 루가 서로 토론 중입니다..."):
                # 다온이 루를 분석
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    res = model.generate_content(f"다음은 '루(GPT)'의 답변입니다. 비판적으로 분석해주세요:\n{st.session_state.o_resp}")
                    st.session_state.g_an = res.text
                except Exception as e:
                    st.session_state.g_an = f"분석 실패: {e}"

                # 루가 다온을 분석
                try:
                    res = gpt_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role":"user","content":f"다음은 '다온(Gemini)'의 답변입니다. 평가해주세요:\n{st.session_state.g_resp}"}]
                    )
                    st.session_state.o_an = res.choices[0].message.content
                except Exception as e:
                    st.session_state.o_an = f"분석 실패: {e}"
            
            c1, c2 = st.columns(2)
            with c1:
                st.info("💎 다온의 평가")
                st.write(st.session_state.g_an)
            with c2:
                st.success("🧠 루의 평가")
                st.write(st.session_state.o_an)
        else:
            st.warning("먼저 1단계에서 질문을 입력해주세요.")

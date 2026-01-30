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
    
    if user_input := st.chat_input("질

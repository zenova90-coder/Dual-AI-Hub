import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import time
from datetime import datetime

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="Dual-AI Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# --- 2. API 키 설정 ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
except KeyError:
    st.error("🚨 API 키 설정이 필요합니다. (.streamlit/secrets.toml 확인)")
    st.stop()

genai.configure(api_key=gemini_api_key)
gpt_client = OpenAI(api_key=gpt_api_key)

# --- 3. [수정됨] 사용 가능한 모델 자동 탐색 함수 ---
def get_working_gemini_model():
    """
    내 계정에서 실제로 작동하는 Gemini 모델을 자동으로 찾습니다.
    (404 에러 방지용)
    """
    try:
        # 현재 사용 가능한 모든 모델 목록을 가져옴
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 우리가 선호하는 모델 순서 (Flash -> Pro -> 구버전)
        # models/ 접두사가 있는 경우와 없는 경우 모두 대비
        preferences = [
            'models/gemini-1.5-flash', 
            'gemini-1.5-flash',
            'models/gemini-pro', 
            'gemini-pro'
        ]
        
        for pref in preferences:
            if pref in available_models:
                return pref
        
        # 선호 모델이 없으면 목록의 첫 번째 모델 반환
        if available_models:
            return available_models[0]
        
        # 목록조차 못 가져오면 가장 기본 모델 시도
        return "gemini-pro"
        
    except Exception:
        # API 호출 실패 시 기본값
        return "gemini-pro"

# 내부적으로 확정된 모델명 (화면엔 안 보임)
VALID_MODEL_NAME = get_working_gemini_model()

# --- 4. 세션 상태 초기화 ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- 5. 재시도(Retry) & 모델 호출 로직 ---
def generate_with_retry(prompt, retries=3, delay=5):
    """
    429 에러(할당량 초과) 발생 시, 잠시 대기 후 재시도
    """
    # models/ 접두사를 제거해야 잘 작동하는 라이브러리 버전을 대비해 문자열 처리
    clean_model_name = VALID_MODEL_NAME.replace("models/", "")
    model = genai.GenerativeModel(clean_model_name)
    
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg: # 할당량 초과
                if attempt < retries - 1:
                    st.toast(f"⏳ 사용량 조절 중... {delay}초 후 재시도합니다.")
                    time.sleep(delay)
                    continue
                else:
                    return "❌ (접속량 폭주) 잠시 후 다시 질문해주세요."
            elif "404" in error_msg: # 모델 찾기 실패 시 즉시 중단이 아닌 안내
                 return "❌ 모델 설정 오류: API 키가 해당 모델을 지원하지 않습니다."
            else:
                return f"❌ 에러 발생: {error_msg}"

# --- 6. 사이드바 ---
with st.sidebar:
    if st.button("➕ 새 대화 시작하기 (초기화)", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# --- 7. 메인 로직 ---
user_input = st.chat_input("질문을 입력하세요. (답변 -> 분석 -> 결론 자동 진행)")

if user_input:
    with st.status("🚀 AI 프로세스 진행 중...", expanded=True) as status:
        turn_data = {
            "q": user_input,
            "timestamp": datetime.now().strftime("%H:%M"),
        }

        try:
            # [STEP 1] 답변 생성
            st.write("1️⃣ 다온(Gemini)과 루(Chat GPT)가 답변 작성 중...")
            
            # 다온 (Gemini)
            turn_data["g_resp"] = generate_with_retry(user_input)
            time.sleep(1) # 과부하 방지

            # 루 (Chat GPT)
            o_res = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": user_input}]
            )
            turn_data["o_resp"] = o_res.choices[0].message.content

            # [STEP 2] 교차 분석
            st.write("2️⃣ 상호 비판 및 분석 중...")
            
            # 다온 -> 루 비평
            prompt_g = f"다음은 Chat GPT의 답변이다. 논리적 허점을 비판해줘:\n{turn_data['o_resp']}"
            turn_data["g_an"] = generate_with_retry(prompt_g)
            time.sleep(1)

            # 루 -> 다온 비평
            prompt_o = f"다음은 Gemini의 답변이다. 창의성과 논리를 평가해줘:\n{turn_data['g_resp']}"
            o_an = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_o}]
            )
            turn_data["o_an"] = o_an.choices[0].message.content

            # [STEP 3] 최종 결론
            st.write("3️⃣ 최종 결론 도출 중...")
            final_prompt = f"""
            질문: {user_input}
            [Gemini 답변]: {turn_data['g_resp']}
            [Chat GPT 답변]: {turn_data['o_resp']}
            [Gemini 비평]: {turn_data['g_an']}
            [Chat GPT 비평]: {turn_data['o_an']}
            
            위 내용을 종합하여 사용자를 위한 명확한 최종 결론을 내려줘.
            """
            final_res = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": final_prompt}]
            )
            turn_data["final_con"] = final_res.choices[0].message.content

            # 저장
            st.session_state.chat_history.append(turn_data)
            status.update(label="✅ 분석 완료!", state="complete", expanded=False)

        except Exception as e:
            st.error(f"시스템 에러: {e}")

# --- 8. 결과 출력 ---
if st.session_state.chat_history:
    tab1, tab2, tab3 = st.tabs(["💬 의견 대립", "⚔️ 교차 검증", "🏆 최종 결론"])
    
    for i, chat in enumerate(st.session_state.chat_history):
        idx = i + 1
        with tab1:
            st.markdown(f"#### Q{idx}. {chat['q']}")
            c1, c2 = st.columns(2)
            with c1: 
                st.info("💎 다온 (Gemini)") 
                st.write(chat['g_resp'])
            with c2: 
                st.success("🧠 루 (Chat GPT)") 
                st.write(chat['o_resp'])
            st.divider()
        with tab2:
            st.markdown(f"#### Q{idx} 분석")
            c1, c2 = st.columns(2)
            with c1: 
                st.info("💎 다온 (Gemini)의 비평")
                st.write(chat['g_an'])
            with c2: 
                st.success("🧠 루 (Chat GPT)의 평가")
                st.write(chat['o_an'])
            st.divider()
        with tab3:
            st.markdown(f"#### 🏆 Q{idx} 결론")
            st.write(chat['final_con'])
            st.divider()

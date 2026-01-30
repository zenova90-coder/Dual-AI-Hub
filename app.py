import streamlit as st
import google.generativeai as genai
from openai import OpenAI
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Dual-AI Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# 2. API 키 설정
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
except:
    st.error("🚨 Secrets 설정(GEMINI_API_KEY, GPT_API_KEY)을 확인해주세요.")
    st.stop()

genai.configure(api_key=gemini_api_key)
gpt_client = OpenAI(api_key=gpt_api_key)

# 3. 세션 상태 초기화 (데이터 누적 구조)
if "chat_session" not in st.session_state:
    st.session_state.chat_session = [] # 질문별 결과 리스트 저장

# 4. 모델 진단 함수
def get_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for target in ['models/gemini-1.5-flash', 'models/gemini-pro']:
            if target in models: return target
        return models[0] if models else "gemini-pro"
    except: return "gemini-pro"

valid_model_name = get_model()

# 5. 사이드바 (초기화 버튼)
with st.sidebar:
    if st.button("➕ 새 대화 시작하기 (전체 초기화)", use_container_width=True):
        st.session_state.chat_session = []
        st.rerun()

# 6. 메인 입력창
user_input = st.chat_input("질문을 입력하면 [답변-분석-결론]이 자동으로 진행됩니다.")

if user_input:
    with st.status("🚀 AI 프로세스 가동 중...", expanded=True) as status:
        new_data = {"q": user_input, "time": datetime.now().strftime("%H:%M:%S")}
        
        # --- STEP 1: 답변 생성 ---
        st.write("1️⃣ 다온과 루가 답변을 생성 중...")
        # 다온
        model = genai.GenerativeModel(valid_model_name.replace('models/', ''))
        new_data["g_res"] = model.generate_content(user_input).text
        # 루
        o_res = gpt_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "너는 논리적인 전문가 '루'다."}, {"role": "user", "content": user_input}]
        )
        new_data["o_res"] = o_res.choices[0].message.content

        # --- STEP 2: 교차 분석 ---
        st.write("2️⃣ 상호 비판 분석 진행 중...")
        new_data["g_an"] = model.generate_content(f"다음 답변의 허점을 비판해줘: {new_data['o_res']}").text
        o_an = gpt_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": f"다음 답변을 평가해줘: {new_data['g_res']}"}]
        )
        new_data["o_an"] = o_an.choices[0].message.content

        # --- STEP 3: 최종 결론 ---
        st.write("3️⃣ 루(GPT)의 최종 결론 도출 중...")
        f_res = gpt_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": f"질문:{user_input}\n답변1:{new_data['g_res']}\n답변2:{new_data['o_res']}\n비판1:{new_data['g_an']}\n비판2:{new_data['o_an']}\n위 내용을 종합해 최종 조언을 해줘."}]
        )
        new_data["final"] = f_res.choices[0].message.content
        
        # 데이터 저장
        st.session_state.chat_session.append(new_data)
        status.update(label="✅ 분석 완료!", state="complete")

# 7. 화면 출력 (누적 구조)
if st.session_state.chat_session:
    tab1, tab2, tab3 = st.tabs(["💬 1. 의견 제시", "⚔️ 2. 교차 검증", "🏆 3. 최종 결론"])

    for i, chat in enumerate(st.session_state.chat_session):
        with tab1:
            st.markdown(f"#### 🙋‍♂️ Q{i+1}: {chat['q']}")
            c1, c2 = st.columns(2)
            with c1: st.info(f"💎 다온: {chat['g_res']}")
            with c2: st.success(f"🧠 루: {chat['o_res']}")
            st.divider()

        with tab2:
            st.markdown(f"#### ⚔️ Q{i+1} 분석")
            c1, c2 = st.columns(2)
            with c1: st.info(f"💎 다온의 비평: {chat['g_an']}")
            with c2: st.success(f"🧠 루의 평가: {chat['o_an']}")
            st.divider()

        with tab3:
            st.markdown(f"#### 🏆 Q{i+1} 최종 결론")
            st.markdown(chat['final'])
            st.divider()

import streamlit as st
import google.generativeai as genai
from openai import OpenAI
from datetime import datetime
import json
import os
import time

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="Dual-AI Hub (Pro)", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# --- 2. API 키 설정 ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
except KeyError:
    st.error("🚨 API 키 설정이 필요합니다.")
    st.stop()

genai.configure(api_key=gemini_api_key)
gpt_client = OpenAI(api_key=gpt_api_key)

# --- 3. [수정됨] 사용 가능한 모델 자동 탐색 (404 에러 방지) ---
def get_best_available_model():
    """
    API에 직접 물어봐서 현재 사용 가능한 모델 중 가장 좋은 것을 가져옵니다.
    """
    try:
        # 모델 목록 조회
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 우선순위: 1.5 Flash -> 1.5 Pro -> 1.0 Pro
        # models/ 접두사가 있든 없든 유연하게 찾음
        priority_keywords = ['1.5-flash', '1.5-pro', 'gemini-pro']
        
        for keyword in priority_keywords:
            for m in models:
                if keyword in m:
                    return m # 찾은 모델 이름 그대로 반환 (가장 확실함)
        
        return models[0] if models else "models/gemini-pro"
    except:
        # 목록 조회 실패 시 기본값 시도
        return "models/gemini-pro"

# 시스템이 찾은 확실한 모델명
TARGET_MODEL = get_best_available_model()

# --- 4. 데이터 관리 (파일 저장/로드) ---
DB_FILE = "chat_db.json"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return [{"title": "새 대화", "history": []}]
    return [{"title": "새 대화", "history": []}]

def save_data(sessions):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=4)

# --- 5. 세션 초기화 ---
if "sessions" not in st.session_state:
    st.session_state.sessions = load_data()
    st.session_state.active_index = 0

if "active_index" not in st.session_state:
    st.session_state.active_index = 0

def get_active_session():
    # 인덱스 범위 오류 방지
    if st.session_state.active_index >= len(st.session_state.sessions):
        st.session_state.active_index = 0
    return st.session_state.sessions[st.session_state.active_index]

# --- 6. 사이드바 ---
with st.sidebar:
    st.header("🗂️ 대화 기록")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ 새 대화", use_container_width=True):
            new_session = {"title": "새 대화", "history": []}
            st.session_state.sessions.insert(0, new_session)
            st.session_state.active_index = 0
            save_data(st.session_state.sessions)
            st.rerun()
    with col2:
        if st.button("🗑️ 전체 삭제", use_container_width=True):
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
            st.session_state.sessions = [{"title": "새 대화", "history": []}]
            st.session_state.active_index = 0
            st.rerun()

    st.divider()

    for i, session in enumerate(st.session_state.sessions):
        label = session["title"]
        if len(label) > 12: label = label[:12] + "..."
        
        if i == st.session_state.active_index:
            st.button(f"📂 {label}", key=f"s_{i}", use_container_width=True, disabled=True)
        else:
            if st.button(f"📄 {label}", key=f"s_{i}", use_container_width=True):
                st.session_state.active_index = i
                st.rerun()

    # (디버깅용) 현재 연결된 모델이 무엇인지 작게 표시 (필요 없으면 삭제 가능)
    st.caption(f"Connected: {TARGET_MODEL}")

# --- 7. 메인 로직 ---
active_session = get_active_session()
chat_history = active_session["history"]

user_input = st.chat_input("질문을 입력하세요...")

if user_input:
    # 제목 자동 설정
    if len(chat_history) == 0:
        active_session["title"] = user_input
        save_data(st.session_state.sessions)

    with st.status("🚀 AI 심층 분석 진행 중...", expanded=True) as status:
        turn_data = {"q": user_input, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}

        try:
            # 1. 답변
            st.write("1️⃣ 다온 & 루 답변 작성 중...")
            
            # [수정됨] 자동 탐색된 모델명 사용
            model = genai.GenerativeModel(TARGET_MODEL)
            turn_data["g_resp"] = model.generate_content(user_input).text
            
            o_res = gpt_client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": user_input}]
            )
            turn_data["o_resp"] = o_res.choices[0].message.content

            # 2. 분석
            st.write("2️⃣ 교차 비판 및 검증 중...")
            turn_data["g_an"] = model.generate_content(f"비판해줘: {turn_data['o_resp']}").text
            
            o_an = gpt_client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": f"평가해줘: {turn_data['g_resp']}"}]
            )
            turn_data["o_an"] = o_an.choices[0].message.content

            # 3. 결론
            st.write("3️⃣ 최종 결론 도출 중...")
            final_prompt = f"""
            질문: {user_input}
            [Gemini]: {turn_data['g_resp']}
            [GPT]: {turn_data['o_resp']}
            [Gemini 비평]: {turn_data['g_an']}
            [GPT 비평]: {turn_data['o_an']}
            결론을 내려줘.
            """
            final_res = gpt_client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": final_prompt}]
            )
            turn_data["final_con"] = final_res.choices[0].message.content

            # 저장 및 완료 처리
            active_session["history"].append(turn_data)
            save_data(st.session_state.sessions)
            
            status.update(label="✅ 분석 완료!", state="complete", expanded=False)
            time.sleep(1)
            st.rerun()

        except Exception as e:
            st.error(f"❌ 에러 발생: {e}")
            # 에러 발생 시 진행 멈춤

# --- 8. 화면 출력 (최신순) ---
if chat_history:
    st.caption(f"🕒 현재 대화: {len(chat_history)}개의 분석 기록")
    
    total_count = len(chat_history)
    
    # 최신 질문이 맨 위에 오도록 역순 반복
    for i, chat in enumerate(reversed(chat_history)):
        idx = total_count - i
        
        st.markdown(f"### Q{idx}. {chat['q']}")
        
        tab1, tab2, tab3 = st.tabs(["💬 의견 대립", "⚔️ 교차 검증", "🏆 최종 결론"])
        
        with tab1:
            c1, c2 = st.columns(2)
            with c1: 
                st.info("💎 다온 (Gemini)")
                st.write(chat['g_resp'])
            with c2: 
                st.success("🧠 루 (Chat GPT)")
                st.write(chat['o_resp'])
        
        with tab2:
            c1, c2 = st.columns(2)
            with c1: 
                st.info("비평")
                st.write(chat['g_an'])
            with c2: 
                st.success("평가")
                st.write(chat['o_an'])
        
        with tab3:
            st.markdown(chat['final_con'])
            
        st.divider()

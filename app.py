import streamlit as st
import google.generativeai as genai
from openai import OpenAI
from datetime import datetime
import json
import os

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
TARGET_MODEL = "gemini-1.5-flash"

# --- 3. [핵심] 파일 저장 및 불러오기 시스템 ---
DB_FILE = "chat_db.json"

def load_data():
    """파일에서 저장된 대화 내용을 불러옵니다."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return [{"title": "새 대화", "history": []}] # 파일 깨짐 대비
    return [{"title": "새 대화", "history": []}] # 파일 없으면 초기값

def save_data(sessions):
    """대화 내용을 파일에 영구 저장합니다."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=4)

# --- 4. 세션 상태 초기화 (앱 켤 때 파일 읽기) ---
if "sessions" not in st.session_state:
    st.session_state.sessions = load_data() # 파일에서 복구
    st.session_state.active_index = 0

if "active_index" not in st.session_state:
    st.session_state.active_index = 0

# 현재 활성화된 세션 가져오기
def get_active_session():
    # 인덱스 에러 방지
    if st.session_state.active_index >= len(st.session_state.sessions):
        st.session_state.active_index = 0
    return st.session_state.sessions[st.session_state.active_index]

# --- 5. 사이드바 (대화 목록 관리) ---
with st.sidebar:
    st.header("🗂️ 대화 기록 (자동 저장)")
    
    col1, col2 = st.columns(2)
    with col1:
        # [새 대화]
        if st.button("➕ 새 대화", use_container_width=True):
            new_session = {"title": "새 대화", "history": []}
            st.session_state.sessions.insert(0, new_session) # 맨 앞에 추가
            st.session_state.active_index = 0
            save_data(st.session_state.sessions) # 파일 저장
            st.rerun()
    with col2:
        # [전체 삭제]
        if st.button("🗑️ 전체 삭제", use_container_width=True):
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE) # 파일 삭제
            st.session_state.sessions = [{"title": "새 대화", "history": []}]
            st.session_state.active_index = 0
            st.rerun()

    st.divider()

    # [세션 목록 표시]
    for i, session in enumerate(st.session_state.sessions):
        label = session["title"]
        if len(label) > 12: label = label[:12] + "..."
        
        # 현재 보고 있는 방 표시
        if i == st.session_state.active_index:
            btn_label = f"📂 {label}"
            st.button(btn_label, key=f"s_btn_{i}", use_container_width=True, disabled=True) # 선택됨 표시
        else:
            if st.button(f"📄 {label}", key=f"s_btn_{i}", use_container_width=True):
                st.session_state.active_index = i
                st.rerun()

# --- 6. 메인 로직 ---
active_session = get_active_session()
chat_history = active_session["history"]

user_input = st.chat_input("질문을 입력하세요. (모든 내용은 자동 저장됩니다)")

if user_input:
    # 첫 질문이면 제목 업데이트
    if len(chat_history) == 0:
        active_session["title"] = user_input
        save_data(st.session_state.sessions) # 제목 변경 즉시 저장
        st.rerun()

    with st.status("🚀 AI 분석 및 데이터 저장 중...", expanded=True) as status:
        turn_data = {"q": user_input, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}

        try:
            # 1. 답변
            st.write("1️⃣ 다온(Gemini)과 루(Chat GPT) 응답 중...")
            model = genai.GenerativeModel(TARGET_MODEL)
            turn_data["g_resp"] = model.generate_content(user_input).text
            
            o_res = gpt_client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": user_input}]
            )
            turn_data["o_resp"] = o_res.choices[0].message.content

            # 2. 분석
            st.write("2️⃣ 상호 교차 분석 중...")
            turn_data["g_an"] = model.generate_content(f"Chat GPT 답변 비판해줘:\n{turn_data['o_resp']}").text
            
            o_an = gpt_client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": f"Gemini 답변 평가해줘:\n{turn_data['g_resp']}"}]
            )
            turn_data["o_an"] = o_an.choices[0].message.content

            # 3. 결론
            st.write("3️⃣ 최종 결론 도출 및 저장 중...")
            final_prompt = f"""
            질문: {user_input}
            [Gemini]: {turn_data['g_resp']}
            [GPT]: {turn_data['o_resp']}
            [Gemini 비평]: {turn_data['g_an']}
            [GPT 비평]: {turn_data['o_an']}
            최종 결론을 내려줘.
            """
            final_res = gpt_client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": final_prompt}]
            )
            turn_data["final_con"] = final_res.choices[0].message.content

            # [저장] 리스트에 추가하고 파일에도 쓰기
            active_session["history"].append(turn_data)
            save_data(st.session_state.sessions) # <--- 여기가 핵심 (영구 저장)
            
            status.update(label="✅ 저장 완료!", state="complete", expanded=False)
            st.rerun()

        except Exception as e:
            st.error(f"에러 발생: {e}")

# --- 7. 화면 출력 ---
if chat_history:
    st.caption(f"🕒 마지막 대화: {chat_history[-1]['timestamp']}")
    tab1, tab2, tab3 = st.tabs(["💬 의견 대립", "⚔️ 교차 검증", "🏆 최종 결론"])
    
    for i, chat in enumerate(chat_history):
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
                st.info("비평")
                st.write(chat['g_an'])
            with c2: 
                st.success("평가")
                st.write(chat['o_an'])
            st.divider()
        with tab3:
            st.markdown(f"#### 🏆 Q{idx} 결론")
            st.write(chat['final_con'])
            st.divider()
else:
    st.info("👋 저장된 대화가 없습니다. 질문을 입력하면 `chat_db.json` 파일에 자동 저장됩니다.")

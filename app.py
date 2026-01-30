import streamlit as st
import google.generativeai as genai
from openai import OpenAI
from datetime import datetime
import json
import os
import concurrent.futures

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="Dual-AI Hub (Final)", layout="wide")
st.title("⚡ Dual-AI Insight Hub")

# --- 2. API 키 설정 ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
except KeyError:
    st.error("🚨 API 키 설정이 필요합니다.")
    st.stop()

genai.configure(api_key=gemini_api_key)
gpt_client = OpenAI(api_key=gpt_api_key)

# --- 3. 모델 설정 ---
def get_best_available_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority_keywords = ['1.5-flash', '1.5-pro', 'gemini-pro']
        for keyword in priority_keywords:
            for m in models:
                if keyword in m: return m
        return models[0] if models else "models/gemini-pro"
    except: return "models/gemini-pro"

GEMINI_MODEL = get_best_available_model()
GPT_MODEL = "gpt-4o-mini" # 속도와 가성비 최강 모델

# --- 4. 데이터 관리 ---
DB_FILE = "chat_db.json"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return [{"title": "새 대화", "history": []}]
    return [{"title": "새 대화", "history": []}]

def save_data(sessions):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=4)

# --- 5. 세션 상태 관리 ---
if "sessions" not in st.session_state:
    st.session_state.sessions = load_data()
    st.session_state.active_index = 0

if "system_role" not in st.session_state:
    st.session_state.system_role = "너는 각 분야의 최고 전문가다. 사용자에게 친절하고 명확하게 설명하라."

if "active_index" not in st.session_state:
    st.session_state.active_index = 0

def get_active_session():
    if st.session_state.active_index >= len(st.session_state.sessions):
        st.session_state.active_index = 0
    return st.session_state.sessions[st.session_state.active_index]

# --- 6. 병렬 처리 함수 ---
def call_gemini(prompt):
    model = genai.GenerativeModel(GEMINI_MODEL)
    return model.generate_content(prompt).text

def call_gpt(messages):
    response = gpt_client.chat.completions.create(model=GPT_MODEL, messages=messages)
    return response.choices[0].message.content

# --- 7. 사이드바 (기능 집약) ---
with st.sidebar:
    st.header("🎮 제어 센터")
    
    # [1] 페르소나 설정
    with st.expander("🎭 AI 역할(Persona) 설정", expanded=False):
        input_role = st.text_area("역할 입력", value=st.session_state.system_role, height=70)
        if st.button("💾 역할 적용", use_container_width=True):
            st.session_state.system_role = input_role
            st.success("적용 완료!")

    st.divider()

    # [2] 대화방 관리 및 제목 수정 (NEW!)
    st.subheader("🗂️ 대화방 관리")
    
    # 현재 활성화된 세션 가져오기
    active_session = get_active_session()
    
    # [NEW] 제목 수정 기능 추가
    new_title = st.text_input(
        "🏷️ 현재 대화방 이름 수정", 
        value=active_session["title"],
        key=f"title_edit_{st.session_state.active_index}"
    )
    
    # 제목이 바뀌면 즉시 저장
    if new_title != active_session["title"]:
        active_session["title"] = new_title
        save_data(st.session_state.sessions)
        st.rerun()

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
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            st.session_state.sessions = [{"title": "새 대화", "history": []}]
            st.session_state.active_index = 0
            st.rerun()

    st.markdown("---")
    
    # 대화 목록 표시
    for i, session in enumerate(st.session_state.sessions):
        label = session["title"]
        if len(label) > 15: label = label[:15] + "..."
        
        # 현재 선택된 방은 버튼 비활성화(색상 표시 효과)
        if i == st.session_state.active_index:
            st.button(f"📂 {label}", key=f"s_{i}", use_container_width=True, disabled=True)
        else:
            if st.button(f"📄 {label}", key=f"s_{i}", use_container_width=True):
                st.session_state.active_index = i
                st.rerun()

# --- 8. 메인 로직 ---
active_session = get_active_session() # 제목 수정 반영을 위해 다시 호출
chat_history = active_session["history"]
current_role = st.session_state.system_role

user_input = st.chat_input("질문을 입력하세요...")

if user_input:
    # 첫 질문 시 제목 자동 설정 (제목이 '새 대화'일 때만)
    if len(chat_history) == 0 and active_session["title"] == "새 대화":
        active_session["title"] = user_input
        save_data(st.session_state.sessions)
        st.rerun() # 제목 반영 위해 리런

    with st.status("⚡ 초고속 병렬 분석 중...", expanded=True) as status:
        turn_data = {"q": user_input, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # STEP 1: 동시 답변
            st.write(f"1️⃣ 답변 생성 중 (Role: {current_role[:10]}...)")
            g_msg = f"System Instruction: {current_role}\n\nQuestion: {user_input}"
            o_msg = [{"role": "system", "content": current_role}, {"role": "user", "content": user_input}]
            
            f_g = executor.submit(call_gemini, g_msg)
            f_o = executor.submit(call_gpt, o_msg)
            
            turn_data["g_resp"] = f_g.result()
            turn_data["o_resp"] = f_o.result()

            # STEP 2: 동시 분석
            st.write("2️⃣ 상호 비평 중...")
            g_an_prompt = f"[Role]: {current_role}\n[Target]: GPT Answer\nEvaluate critically without using 'Pros/Cons' lists.\n\n{turn_data['o_resp']}"
            o_an_msg = [{"role": "system", "content": current_role}, {"role": "user", "content": f"Evaluate Gemini's answer critically. Do not use 'Pros/Cons' list.\n\n{turn_data['g_resp']}"}]
            
            f_g_an = executor.submit(call_gemini, g_an_prompt)
            f_o_an = executor.submit(call_gpt, o_an_msg)
            
            turn_data["g_an"] = f_g_an.result()
            turn_data["o_an"] = f_o_an.result()

            # STEP 3: 결론
            st.write("3️⃣ 최종 결론 도출...")
            final_prompt = f"""
            Role: {current_role}
            Task: Synthesize a final solution based on the discussion.
            Requirement: Fix errors pointed out in the reviews.
            
            Q: {user_input}
            Gemini: {turn_data['g_resp']}
            GPT: {turn_data['o_resp']}
            Review(G): {turn_data['g_an']}
            Review(O): {turn_data['o_an']}
            """
            turn_data["final_con"] = call_gpt([{"role": "user", "content": final_prompt}])

            active_session["history"].append(turn_data)
            save_data(st.session_state.sessions)
            status.update(label="✅ 완료!", state="complete", expanded=False)
            st.rerun()

# --- 9. 결과 출력 ---
if chat_history:
    st.caption(f"🕒 {len(chat_history)}개의 기록 | 현재 대화방: {active_session['title']}")
    
    for i, chat in enumerate(reversed(chat_history)):
        idx = len(chat_history) - i
        st.markdown(f"### Q{idx}. {chat['q']}")
        
        t1, t2, t3 = st.tabs(["💬 답변", "⚔️ 비평", "🏆 결론"])
        with t1:
            c1, c2 = st.columns(2)
            with c1: st.info("💎 다온"); st.write(chat['g_resp'])
            with c2: st.success("🧠 루"); st.write(chat['o_resp'])
        with t2:
            c1, c2 = st.columns(2)
            with c1: st.info("비평"); st.write(chat['g_an'])
            with c2: st.success("평가"); st.write(chat['o_an'])
        with t3: st.markdown(chat['final_con'])
        st.divider()

import streamlit as st
import google.generativeai as genai
from openai import OpenAI
from datetime import datetime
import json
import os
import concurrent.futures 

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="Dual-AI Hub", layout="wide")

# ==========================================
# 🔒 [보안] 비밀번호 잠금 (엔터 키 로그인)
# ==========================================
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    st.header("🔒 접속 권한 확인")
    st.write("비밀번호를 입력하세요.")
    
    with st.form(key='login_form'):
        password_input = st.text_input("Password", type="password", label_visibility="collapsed")
        submit_button = st.form_submit_button("로그인")
        
        if submit_button:
            try:
                if password_input == st.secrets["APP_PASSWORD"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ 비밀번호가 틀렸습니다.")
            except KeyError:
                st.error("🚨 secrets.toml 설정 확인 필요")
    return False

if not check_password():
    st.stop()

# ==========================================
# ⚡ 메인 앱
# ==========================================

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
GPT_MODEL = "gpt-4o-mini" 

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

# --- 5. 세션 상태 ---
if "sessions" not in st.session_state:
    st.session_state.sessions = load_data()
    st.session_state.active_index = 0

# [NEW] 역할 이름(짧은 것)과 상세 지시(긴 것) 분리
if "role_name" not in st.session_state:
    st.session_state.role_name = "전문가"
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

# --- 7. 사이드바 (UI 개선) ---
with st.sidebar:
    st.success("🔐 로그인 완료")
    
    # [수정됨] 헤더 이름 변경
    st.header("AI 역할")
    
    # [NEW] 역할 이름 입력창 (짧게 표시하기 위함)
    input_role_name = st.text_input("역할 이름 (예: 변호사)", value=st.session_state.role_name)
    
    # [수정됨] 상세 역할 입력창 (라벨 숨김)
    input_role_detail = st.text_area(
        "상세 지시사항", 
        value=st.session_state.system_role,
        height=100,
        label_visibility="collapsed", # 라벨 숨기기
        placeholder="여기에 상세한 역할 지시사항을 입력하세요..."
    )
    
    if st.button("💾 역할 적용하기", use_container_width=True):
        st.session_state.role_name = input_role_name
        st.session_state.system_role = input_role_detail
        st.success(f"✅ '{input_role_name}' 설정 완료!")

    st.divider()
    
    # 대화방 관리
    st.header("🗂️ 대화 기록")
    active_session = get_active_session()
    
    new_title = st.text_input("🏷️ 방 이름 수정", value=active_session["title"], key=f"te_{st.session_state.active_index}")
    if new_title != active_session["title"]:
        active_session["title"] = new_title
        save_data(st.session_state.sessions)
        st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ 새 대화", use_container_width=True):
            st.session_state.sessions.insert(0, {"title": "새 대화", "history": []})
            st.session_state.active_index = 0
            save_data(st.session_state.sessions)
            st.rerun()
    with c2:
        if st.button("🗑️ 전체 삭제", use_container_width=True):
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
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

# --- 8. 메인 로직 ---
active_session = get_active_session()
chat_history = active_session["history"]
current_role_name = st.session_state.role_name   # 표시용 (예: 변호사)
current_role_detail = st.session_state.system_role # 실제 지시용 (예: 너는 20년차...)

user_input = st.chat_input("질문을 입력하세요...")

if user_input:
    if len(chat_history) == 0 and active_session["title"] == "새 대화":
        active_session["title"] = user_input[:20]
        save_data(st.session_state.sessions)
        st.rerun()

    # [수정됨] 상태 메시지 변경: "초고속..." -> "작업 진행 중"
    with st.status("작업 진행 중...", expanded=True) as status:
        turn_data = {"q": user_input, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            
            # [수정됨] 역할 이름 간소화 표시
            st.write(f"1️⃣ 답변 생성 중 (Role: {current_role_name})...")
            
            gemini_prompt = f"System Instruction: {current_role_detail}\n\nQuestion: {user_input}"
            future_g_resp = executor.submit(call_gemini, gemini_prompt)
            
            gpt_messages = [
                {"role": "system", "content": current_role_detail},
                {"role": "user", "content": user_input}
            ]
            future_o_resp = executor.submit(call_gpt, gpt_messages)
            
            turn_data["g_resp"] = future_g_resp.result()
            turn_data["o_resp"] = future_o_resp.result()

            # --- 교차 분석 ---
            st.write("2️⃣ 자유 토론 및 비평 중...")
            
            g_an_prompt = f"""
            [Role]: {current_role_detail}
            Critically review Chat GPT's answer.
            Do NOT use 'Pros/Cons' lists. Be natural and insightful.
            
            [GPT Answer]: {turn_data['o_resp']}
            """
            future_g_an = executor.submit(call_gemini, g_an_prompt)
            
            o_an_messages = [
                {"role": "system", "content": current_role_detail},
                {"role": "user", "content": f"""
                Evaluate Gemini's answer naturally. 
                Do NOT use 'Pros/Cons' lists. Focus on key insights or errors.
                
                [Gemini Answer]: {turn_data['g_resp']}
                """}
            ]
            future_o_an = executor.submit(call_gpt, o_an_messages)
            
            turn_data["g_an"] = future_g_an.result()
            turn_data["o_an"] = future_o_an.result()

            # --- 최종 결론 ---
            st.write("3️⃣ 최종 결론 도출 중...")
            final_prompt = f"""
            Role: {current_role_detail}
            Synthesize the final conclusion based on the discussion.
            Reflect the critiques to provide the best solution.
            
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
    st.caption(f"🕒 기록: {len(chat_history)}건 | 🏷️ {active_session['title']}")
    total_count = len(chat_history)
    
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

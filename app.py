import streamlit as st
import google.generativeai as genai
from openai import OpenAI
from datetime import datetime
import json
import os
import concurrent.futures # 병렬 처리를 위한 핵심 라이브러리

# --- 1. 페이지 설정 (가장 먼저 실행) ---
st.set_page_config(page_title="Dual-AI Hub (Private)", layout="wide")

# ==========================================
# 🔒 [보안] 비밀번호 잠금 장치
# ==========================================
def check_password():
    """비밀번호가 맞는지 확인하는 함수"""
    if st.session_state.get("password_correct", False):
        return True

    st.header("🔒 접속 권한 확인")
    st.write("관리자가 설정한 비밀번호를 입력하세요.")
    
    password_input = st.text_input("비밀번호", type="password")
    
    if st.button("로그인"):
        try:
            if password_input == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 틀렸습니다.")
        except KeyError:
            st.error("🚨 secrets.toml에 APP_PASSWORD 설정이 없습니다.")
    
    return False

# 비밀번호 통과 못하면 여기서 중단
if not check_password():
    st.stop()

# ==========================================
# ⚡ 메인 앱 시작
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

# --- 3. 모델 설정 (속도 최적화) ---
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

# --- 6. 병렬 처리 함수들 ---
def call_gemini(prompt):
    model = genai.GenerativeModel(GEMINI_MODEL)
    return model.generate_content(prompt).text

def call_gpt(messages):
    response = gpt_client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages
    )
    return response.choices[0].message.content

# --- 7. 사이드바 ---
with st.sidebar:
    st.success("🔐 로그인 완료")
    
    st.header("🎭 AI 페르소나 설정")
    input_role = st.text_area(
        "AI들에게 부여할 역할(Role)", 
        value=st.session_state.system_role,
        height=100
    )
    if st.button("💾 역할 적용하기", use_container_width=True):
        st.session_state.system_role = input_role
        st.success("✅ 역할 부여 완료!")

    st.divider()
    
    # 대화방 관리
    st.header("🗂️ 대화 기록")
    
    # 제목 수정 기능
    active_session = get_active_session()
    new_title = st.text_input("🏷️ 방 이름 수정", value=active_session["title"], key=f"title_edit_{st.session_state.active_index}")
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

# --- 8. 메인 로직 (병렬 처리 적용) ---
active_session = get_active_session()
chat_history = active_session["history"]
current_role = st.session_state.system_role

user_input = st.chat_input("질문을 입력하세요...")

if user_input:
    # 첫 질문 시 제목 자동 설정
    if len(chat_history) == 0 and active_session["title"] == "새 대화":
        active_session["title"] = user_input[:20]
        save_data(st.session_state.sessions)
        st.rerun()

    with st.status("⚡ 초고속 병렬 연산 중...", expanded=True) as status:
        turn_data = {"q": user_input, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            
            # --- STEP 1: 답변 생성 ---
            st.write(f"1️⃣ 답변 생성 중 (Role: {current_role[:10]}...)")
            
            gemini_prompt = f"System Instruction: {current_role}\n\nQuestion: {user_input}"
            future_g_resp = executor.submit(call_gemini, gemini_prompt)
            
            gpt_messages = [
                {"role": "system", "content": current_role},
                {"role": "user", "content": user_input}
            ]
            future_o_resp = executor.submit(call_gpt, gpt_messages)
            
            turn_data["g_resp"] = future_g_resp.result()
            turn_data["o_resp"] = future_o_resp.result()

            # --- STEP 2: 교차 분석 ---
            st.write("2️⃣ 자유 토론 및 비평 중...")
            
            g_an_prompt = f"""
            [당신의 역할]: {current_role}
            위 역할로서 Chat GPT의 답변을 검토하라.
            
            [중요 지시사항]:
            1. '강점'이나 '약점' 같은 단어를 사용하여 기계적으로 목록을 만들지 마라.
            2. 대신, 답변을 읽고 전문가로서 느끼는 가장 날카로운 통찰이나, 혹은 치명적인 오류 하나에 집중해서 서술하라.
            3. 대화하듯이 자연스럽게 비평하라.
            
            [Chat GPT 답변]: {turn_data['o_resp']}
            """
            future_g_an = executor.submit(call_gemini, g_an_prompt)
            
            o_an_messages = [
                {"role": "system", "content": current_role},
                {"role": "user", "content": f"""
                다음 Gemini의 답변을 평가하라.
                
                [중요 지시사항]:
                1. '장점/단점' 리스트를 나열하는 식상한 방식은 금지한다.
                2. 이 답변이 {user_input}이라는 문제를 해결하는 데 있어 얼마나 효과적인지, 혹은 어떤 부분이 비현실적인지 핵심만 찔러라.
                3. 동료 전문가에게 피드백을 주듯 구체적이고 실질적인 내용을 말하라.
                
                [Gemini 답변]: {turn_data['g_resp']}
                """}
            ]
            future_o_an = executor.submit(call_gpt, o_an_messages)
            
            turn_data["g_an"] = future_g_an.result()
            turn_data["o_an"] = future_o_an.result()

            # --- STEP 3: 최종 결론 ---
            st.write("3️⃣ 최종 결론 도출 중...")
            final_prompt = f"""
            당신은 {current_role} 역할을 맡은 최종 의사결정권자입니다.
            두 AI의 의견과 상호 비판을 종합하여 최적의 솔루션을 제시하십시오.
            비평에서 지적된 문제점은 반드시 수정하여 반영하십시오.
            
            [질문]: {user_input}
            [Gemini 의견]: {turn_data['g_resp']}
            [GPT 의견]: {turn_data['o_resp']}
            [Gemini 비평]: {turn_data['g_an']}
            [GPT 비평]: {turn_data['o_an']}
            """
            
            turn_data["final_con"] = call_gpt([{"role": "user", "content": final_prompt}])

            active_session["history"].append(turn_data)
            save_data(st.session_state.sessions)
            
            status.update(label="✅ 분석 완료!", state="complete", expanded=False)
            st.rerun()

# --- 9. 화면 출력 ---
if chat_history:
    st.caption(f"🕒 현재 대화: {len(chat_history)}개의 분석 기록 | 🏷️ {active_session['title']}")
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

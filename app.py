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

# --- 3. 모델 자동 탐색 ---
def get_best_available_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority_keywords = ['1.5-flash', '1.5-pro', 'gemini-pro']
        for keyword in priority_keywords:
            for m in models:
                if keyword in m: return m
        return models[0] if models else "models/gemini-pro"
    except: return "models/gemini-pro"

TARGET_MODEL = get_best_available_model()

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

# [NEW] 역할(System Role)을 저장할 변수 초기화
if "system_role" not in st.session_state:
    st.session_state.system_role = "너는 각 분야의 최고 전문가다. 사용자에게 친절하고 명확하게 설명하라."

if "active_index" not in st.session_state:
    st.session_state.active_index = 0

def get_active_session():
    if st.session_state.active_index >= len(st.session_state.sessions):
        st.session_state.active_index = 0
    return st.session_state.sessions[st.session_state.active_index]

# --- 6. 사이드바 (역할 부여 버튼 추가) ---
with st.sidebar:
    st.header("🎭 AI 페르소나 설정")
    
    # [수정됨] 입력창과 확인 버튼 분리
    input_role = st.text_area(
        "AI들에게 부여할 역할(Role)", 
        value=st.session_state.system_role,
        height=100,
        help="예: 너는 냉철한 변호사다. 법적 근거를 들어 설명하라."
    )
    
    # [NEW] 적용 버튼 및 완료 메시지
    if st.button("💾 역할 적용하기", use_container_width=True):
        st.session_state.system_role = input_role
        st.success("✅ 역할 부여 완료! (설정이 저장되었습니다)")

    st.divider()
    
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

# --- 7. 메인 로직 ---
active_session = get_active_session()
chat_history = active_session["history"]
current_role = st.session_state.system_role # 현재 저장된 역할 가져오기

user_input = st.chat_input("질문을 입력하세요...")

if user_input:
    if len(chat_history) == 0:
        active_session["title"] = user_input
        save_data(st.session_state.sessions)

    with st.status("🚀 설정된 역할로 분석 진행 중...", expanded=True) as status:
        turn_data = {"q": user_input, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}

        try:
            # 1. 답변
            st.write(f"1️⃣ 답변 생성 중 (Role: {current_role[:10]}...)")
            
            # 다온 (Gemini)
            model = genai.GenerativeModel(TARGET_MODEL)
            gemini_prompt = f"System Instruction: {current_role}\n\nQuestion: {user_input}"
            turn_data["g_resp"] = model.generate_content(gemini_prompt).text
            
            # 루 (GPT)
            o_res = gpt_client.chat.completions.create(
                model="gpt-4o", 
                messages=[
                    {"role": "system", "content": current_role},
                    {"role": "user", "content": user_input}
                ]
            )
            turn_data["o_resp"] = o_res.choices[0].message.content

            # 2. 분석
            st.write("2️⃣ 자유 토론 및 비평 중...")
            
            # 다온 프롬프트 (강점/약점 금지)
            g_an_prompt = f"""
            [당신의 역할]: {current_role}
            위 역할로서 Chat GPT의 답변을 검토하라.
            
            [중요 지시사항]:
            1. '강점'이나 '약점' 같은 단어를 사용하여 기계적으로 목록을 만들지 마라.
            2. 대신, 답변을 읽고 전문가로서 느끼는 가장 날카로운 통찰이나, 혹은 치명적인 오류 하나에 집중해서 서술하라.
            3. 대화하듯이 자연스럽게 비평하라.
            
            [Chat GPT 답변]: {turn_data['o_resp']}
            """
            turn_data["g_an"] = model.generate_content(g_an_prompt).text
            
            # 루 프롬프트 (강점/약점 금지)
            o_an_res = gpt_client.chat.completions.create(
                model="gpt-4o", 
                messages=[
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
            )
            turn_data["o_an"] = o_an_res.choices[0].message.content

            # 3. 결론
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
            
            final_res = gpt_client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": final_prompt}]
            )
            turn_data["final_con"] = final_res.choices[0].message.content

            # 저장 및 완료
            active_session["history"].append(turn_data)
            save_data(st.session_state.sessions)
            
            status.update(label="✅ 분석 완료!", state="complete", expanded=False)
            time.sleep(1)
            st.rerun()

        except Exception as e:
            st.error(f"❌ 에러 발생: {e}")

# --- 8. 화면 출력 ---
if chat_history:
    st.caption(f"🕒 현재 대화: {len(chat_history)}개의 분석 기록")
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

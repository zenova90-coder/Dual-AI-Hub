import streamlit as st
import google.generativeai as genai
from openai import OpenAI
from datetime import datetime
import json
import os
import concurrent.futures # 병렬 처리를 위한 핵심 라이브러리

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="Dual-AI Hub (Speed)", layout="wide")
st.title("Dual-AI Insight Hub")

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

# --- 6. [핵심] 병렬 처리 함수들 ---
def call_gemini(prompt):
    model = genai.GenerativeModel(GEMINI_MODEL)
    return model.generate_content(prompt).text

def call_gpt(messages):
    response = gpt_client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages
    )
    return response.choices[0].message.content

# --- 7. 사이드바 (UI 수정 적용됨) ---
with st.sidebar:
    st.header("🎭 AI 역할") 
    
    # [수정] 라벨을 숨기고 예시 문구(placeholder) 추가
    input_role = st.text_area(
        "role_input_hidden", # 내부 식별용 라벨
        value=st.session_state.system_role,
        height=100,
        label_visibility="collapsed", # 상단 라벨 문구 숨김
        placeholder="AI가 수행할 원하는 역할을 입력하세요" # 빈 칸일 때 표시될 예시 문구
    )
    
    if st.button("💾 역할 적용하기", use_container_width=True):
        st.session_state.system_role = input_role
        st.success("✅ 역할 부여 완료!")

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

# --- 8. 메인 로직 (기억력 기능 + 병렬 처리) ---
active_session = get_active_session()
chat_history = active_session["history"]
current_role = st.session_state.system_role

user_input = st.chat_input("질문을 입력하세요...")

if user_input:
    if len(chat_history) == 0:
        active_session["title"] = user_input
        save_data(st.session_state.sessions)

    with st.status("⚡ 3단계 작업 진행 중...", expanded=True) as status:
        turn_data = {"q": user_input, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
        
        # [기억력 강화] 이전 대화 내용을 프롬프트에 포함
        messages_for_gpt = [{"role": "system", "content": current_role}]
        prompt_for_gemini = f"System Instruction: {current_role}\n\n"

        # 과거 기록 주입
        for chat in chat_history:
            messages_for_gpt.append({"role": "user", "content": chat['q']})
            prompt_for_gemini += f"User: {chat['q']}\n"
            
            messages_for_gpt.append({"role": "assistant", "content": chat['final_con']})
            prompt_for_gemini += f"Assistant: {chat['final_con']}\n"

        # 현재 질문 추가
        messages_for_gpt.append({"role": "user", "content": user_input})
        prompt_for_gemini += f"User: {user_input}\n"

        # ThreadPoolExecutor를 사용한 병렬 처리
        with concurrent.futures.ThreadPoolExecutor() as executor:
            
            # --- STEP 1: 답변 생성 ---
            st.write("1️⃣ 답변 생성 중...") 
            
            future_g_resp = executor.submit(call_gemini, prompt_for_gemini)
            future_o_resp = executor.submit(call_gpt, messages_for_gpt)
            
            turn_data["g_resp"] = future_g_resp.result()
            turn_data["o_resp"] = future_o_resp.result()

            # --- STEP 2: 교차 분석 ---
            st.write("2️⃣ 자유 토론 및 비평 중...")
            
            g_an_prompt = f"""
            [당신의 역할]: {current_role}
            위 역할로서 상대방 AI(Chat GPT)의 답변을 검토하라.
            
            [현재 질문]: {user_input}
            [Chat GPT 답변]: {turn_data['o_resp']}
            
            [지시사항]:
            1. 이전 대화의 맥락을 고려했을 때 모순되는 점이 있다면 지적하라.
            2. 답변을 읽고 전문가로서 느끼는 가장 날카로운 통찰이나, 치명적인 오류에 집중하라.
            3. 대화하듯이 자연스럽게 비평하라.
            """
            future_g_an = executor.submit(call_gemini, g_an_prompt)
            
            o_an_messages = [
                {"role": "system", "content": current_role},
                {"role": "user", "content": f"""
                다음 Gemini의 답변을 평가하라.
                
                [현재 질문]: {user_input}
                [Gemini 답변]: {turn_data['g_resp']}
                
                [지시사항]:
                1. 이 답변이 '{user_input}'이라는 문제를 해결하는 데 있어 얼마나 효과적인지 비평하라.
                2. 이전 대화 흐름상 어색한 부분이 있다면 지적하라.
                3. 동료 전문가에게 피드백을 주듯 구체적으로 말하라.
                """}
            ]
            future_o_an = executor.submit(call_gpt, o_an_messages)
            
            turn_data["g_an"] = future_g_an.result()
            turn_data["o_an"] = future_o_an.result()

            # --- STEP 3: 최종 결론 ---
            st.write("3️⃣ 최종 결론 도출 중...")
            
            final_prompt = f"""
            당신은 {current_role} 역할을 맡은 최종 의사결정권자입니다.
            지금까지의 대화 흐름을 유지하며, 이번 질문에 대한 최적의 솔루션을 제시하십시오.
            
            [현재 질문]: {user_input}
            [Gemini 의견]: {turn_data['g_resp']}
            [GPT 의견]: {turn_data['o_resp']}
            [Gemini 비평]: {turn_data['g_an']}
            [GPT 비평]: {turn_data['o_an']}
            
            위 내용을 종합하여 결론을 내리십시오.
            """
            
            turn_data["final_con"] = call_gpt([{"role": "user", "content": final_prompt}])

            active_session["history"].append(turn_data)
            save_data(st.session_state.sessions)
            
            status.update(label="✅ 분석 완료!", state="complete", expanded=False)
            st.rerun()

# --- 9. 화면 출력 ---
if chat_history:
    st.caption(f"🕒 현재 대화: {len(chat_history)}개의 분석 기록")
    total_count = len(chat_history)
    
    for i, chat in enumerate(reversed(chat_history)):
        idx = total_count - i
        st.markdown(f"### Q{idx}. {chat['q']}")
        
        tab1, tab2, tab3 = st.tabs(["💬 의견 제시", "⚔️ 교차 검증", "🏆 최종 결론"])
        
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

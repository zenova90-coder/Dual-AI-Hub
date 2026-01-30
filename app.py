import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import json
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="Dual-AI Hub Pro", layout="wide")

# --- [관리자 기능] 사용자 장부 및 기록 관리 ---
USER_DB_FILE = "users.json"
HISTORY_FILE = "chat_history.json"

def load_users():
    if not os.path.exists(USER_DB_FILE):
        default_db = {
            "minju": {"pw": "1234", "credits": 9999, "name": "양민주(Admin)"},
            "guest": {"pw": "0000", "credits": 3, "name": "체험판손님"} 
        }
        with open(USER_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(default_db, f)
        return default_db
    with open(USER_DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def deduct_credit(username):
    users = load_users()
    if users[username]["credits"] > 0:
        users[username]["credits"] -= 1
        with open(USER_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4)
        return True
    return False

# 히스토리: 이번에는 '세션 전체(여러 질문)'를 저장하는 구조로 변경
def save_session_history(username, session_data):
    if not session_data: return
    
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = []
    
    # 저장할 데이터: 첫 번째 질문을 제목으로 사용
    record = {
        "user": username,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": session_data[0]['q'][:15] + "...", # 첫 질문 요약
        "dialogue": session_data # 대화 전체 리스트
    }
    
    history.insert(0, record)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def load_history_list(username):
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            all_history = json.load(f)
            return [h for h in all_history if h.get("user") == username]
    except: return []

# --- API 키 설정 ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
    genai.configure(api_key=gemini_api_key)
    gpt_client = OpenAI(api_key=gpt_api_key)
except:
    st.error("API 키 설정이 필요합니다.")
    st.stop()

# --- 모델 설정 ---
def get_gemini_model():
    return 'gemini-pro' # 안정성 우선

valid_model_name = get_gemini_model()

# ==========================================
# 🔐 로그인 화면
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if not st.session_state.logged_in:
    st.title("🔒 Dual-AI Hub 로그인")
    col1, col2 = st.columns([1, 2])
    with col1:
        input_id = st.text_input("아이디")
        input_pw = st.text_input("비밀번호", type="password")
        if st.button("로그인"):
            users = load_users()
            if input_id in users and users[input_id]["pw"] == input_pw:
                st.session_state.logged_in = True
                st.session_state.username = input_id
                st.rerun()
            else:
                st.error("로그인 실패")
    st.stop()

# ==========================================
# 🏠 메인 서비스 화면
# ==========================================
user_db = load_users()
current_user = st.session_state.username
current_credits = user_db[current_user]["credits"]

# 사이드바 설정
st.sidebar.title(f"👤 {user_db[current_user]['name']}")
st.sidebar.caption(f"잔여 이용권: {current_credits}회")
st.sidebar.progress(min(current_credits / 10, 1.0))

if current_credits <= 0:
    st.error("이용권이 부족합니다.")
    st.stop()

st.title("🤖 Dual-AI Insight Hub")

# --- 세션 상태 관리 (대화 리스트) ---
# current_chat_log: 질문과 답변들이 리스트 형태로 쌓임 [{q:..., a:..., ...}, {q:..., a:..., ...}]
if "current_chat_log" not in st.session_state: 
    st.session_state.current_chat_log = []

# --- 사이드바: 기능 및 기록 ---
with st.sidebar:
    st.divider()
    # [새 대화 시작] 버튼: 현재 화면을 초기화하고 새 질문을 받을 준비
    if st.button("➕ 새 대화 시작 (화면 초기화)", use_container_width=True):
        # 현재 대화 내용이 있다면 파일로 저장하고 초기화
        if st.session_state.current_chat_log:
            save_session_history(current_user, st.session_state.current_chat_log)
            st.toast("이전 대화가 기록에 저장되었습니다.")
        
        st.session_state.current_chat_log = [] # 리스트 비우기
        st.rerun()

    st.subheader("🗂️ 지난 대화 기록")
    history_list = load_history_list(current_user)
    for idx, item in enumerate(history_list):
        if st.button(f"📄 {item['timestamp']} | {item['title']}", key=f"hist_{idx}"):
            # 기록 불러오기 (현재 화면을 덮어씀)
            st.session_state.current_chat_log = item['dialogue']
            st.rerun()
    
    st.divider()
    if st.button("로그아웃"):
        st.session_state.logged_in = False
        st.rerun()

# ==========================================
# 🖥️ 메인 탭 화면 구성 (여기가 핵심!)
# ==========================================

# 탭을 미리 만들어둡니다.
tab1, tab2, tab3 = st.tabs(["💬 1. 답변 (Opinions)", "⚔️ 2. 교차 분석 (Cross-Analysis)", "🏆 3. 최종 결론 (Conclusion)"])

# 데이터가 하나라도 있을 때 렌더링 시작
if st.session_state.current_chat_log:
    
    # [Tab 1] 질문과 각 AI의 답변을 순서대로 출력 (누적)
    with tab1:
        for i, log in enumerate(st.session_state.current_chat_log):
            # 질문 표시 (작은 폰트, 굵게)
            st.markdown(f"**🙋‍♂️ Q{i+1}. {log['q']}**") 
            
            c1, c2 = st.columns(2)
            with c1:
                st.info(f"💎 다온")
                st.write(log['g_resp'])
            with c2:
                st.success(f"🧠 루")
                st.write(log['o_resp'])
            st.divider() # 구분선

    # [Tab 2] 교차 분석 내용 순서대로 출력 (누적)
    with tab2:
        for i, log in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**🙋‍♂️ Q{i+1}. {log['q']}** (에 대한 분석)")
            
            c1, c2 = st.columns(2)
            with c1:
                st.info("💎 다온의 비평 (루를 분석)")
                st.write(log['g_an'])
            with c2:
                st.success("🧠 루의 평가 (다온을 분석)")
                st.write(log['o_an'])
            st.divider()

    # [Tab 3] 최종 결론 순서대로 출력 (누적)
    with tab3:
        for i, log in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**🙋‍♂️ Q{i+1}. {log['q']}** (최종 결론)")
            st.markdown(log['final_con'])
            st.divider()

# ==========================================
# ⌨️ 채팅 입력 및 처리 (하단 고정)
# ==========================================
user_input = st.chat_input(f"질문을 입력하세요. (엔터 치면 1,2,3단계 자동 실행 | 잔여: {current_credits}회)")

if user_input:
    if current_credits > 0:
        # 크레딧 차감
        deduct_credit(current_user)
        
        # 상태창 표시
        with st.status("🚀 3단계 심층 분석 프로세스 가동 중...", expanded=True) as status:
            new_turn = {"q": user_input, "timestamp": datetime.now().strftime("%H:%M")}
            
            # --- STEP 1: 답변 ---
            st.write("1️⃣ 다온과 루가 생각 중입니다...")
            try:
                model = genai.GenerativeModel(valid_model_name)
                new_turn["g_resp"] = model.generate_content(user_input).text
            except: new_turn["g_resp"] = "Gemini 연결 실패"
            
            try:
                res = gpt_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":user_input}])
                new_turn["o_resp"] = res.choices[0].message.content
            except: new_turn["o_resp"] = "GPT 연결 실패"

            # --- STEP 2: 교차 분석 ---
            st.write("2️⃣ 서로의 답변을 검증하고 있습니다...")
            try:
                new_turn["g_an"] = model.generate_content(f"다음은 '루(GPT)'의 답변이다. 논리적 허점을 비판해줘:\n{new_turn['o_resp']}").text
            except: new_turn["g_an"] = "분석 실패"
            
            try:
                res = gpt_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":f"다음은 '다온(Gemini)'의 답변이다. 창의성과 논리성을 평가해줘:\n{new_turn['g_resp']}"}])
                new_turn["o_an"] = res.choices[0].message.content
            except: new_turn["o_an"] = "분석 실패"
            
            # --- STEP 3: 최종 결론 ---
            st.write("3️⃣ 루(GPT)가 최종 결론을 내립니다...")
            try:
                final_prompt = f"""
                질문: {user_input}
                [다온 답변] {new_turn['g_resp']}
                [루 답변] {new_turn['o_resp']}
                [다온 비평] {new_turn['g_an']}
                [루 비평] {new_turn['o_an']}
                
                위 내용을 종합하여 명쾌한 최종 결론을 내려라. 
                이전 대화 맥락이 있다면 그것도 고려해라.
                """
                res = gpt_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":final_prompt}])
                new_turn["final_con"] = res.choices[0].message.content
            except: new_turn["final_con"] = "결론 도출 실패"

            # 결과 리스트에 추가 (누적)
            st.session_state.current_chat_log.append(new_turn)
            
            status.update(label="✅ 분석 완료!", state="complete", expanded=False)
            st.rerun()
            
    else:
        st.error("이용권이 부족합니다. 관리자에게 문의하세요.")

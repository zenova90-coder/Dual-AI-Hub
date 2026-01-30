import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import json
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="Dual-AI Hub Pro", layout="wide")

# --- 1. API 키 설정 (가장 먼저 해야 함!) ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
    
    # 여기서 모델을 미리 설정해야 에러가 안 납니다.
    genai.configure(api_key=gemini_api_key)
    gpt_client = OpenAI(api_key=gpt_api_key)
except Exception as e:
    st.error(f"API 키 설정 오류: {e}")
    st.stop()

# --- 2. 데이터 관리 함수 (회원가입 포함) ---
USER_DB_FILE = "users.json"
HISTORY_FILE = "chat_history.json"

def load_users():
    if not os.path.exists(USER_DB_FILE):
        default_db = {
            "minju": {"pw": "1234", "credits": 9999, "name": "양민주(Admin)"}
        }
        with open(USER_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(default_db, f)
        return default_db
    with open(USER_DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_new_user(user_id, pw, name):
    users = load_users()
    if user_id in users:
        return False # 이미 있는 아이디
    
    # 신규 가입자에게 3회 무료 증정
    users[user_id] = {
        "pw": pw,
        "credits": 3, 
        "name": name
    }
    with open(USER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)
    return True

def deduct_credit(username):
    users = load_users()
    if users[username]["credits"] > 0:
        users[username]["credits"] -= 1
        with open(USER_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4)
        return True
    return False

# 히스토리 저장
def save_session_history(username, session_data):
    if not session_data: return
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    else: history = []
    
    record = {
        "user": username,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": session_data[0]['q'][:15] + "...",
        "dialogue": session_data
    }
    history.insert(0, record)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def load_history_list(username):
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            all = json.load(f)
            return [h for h in all if h.get("user") == username]
    except: return []

# --- 3. 로그인 및 회원가입 화면 ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if not st.session_state.logged_in:
    st.title("🔒 Dual-AI Hub 접속")
    
    # 탭으로 로그인/회원가입 분리
    tab_login, tab_signup = st.tabs(["로그인", "회원가입(무료)"])
    
    with tab_login:
        c1, c2 = st.columns([1, 2])
        with c1:
            input_id = st.text_input("아이디", key="login_id")
            input_pw = st.text_input("비밀번호", type="password", key="login_pw")
            if st.button("로그인", use_container_width=True):
                users = load_users()
                if input_id in users and users[input_id]["pw"] == input_pw:
                    st.session_state.logged_in = True
                    st.session_state.username = input_id
                    st.rerun()
                else:
                    st.error("아이디 또는 비번이 틀렸습니다.")
    
    with tab_signup:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info("가입 시 무료 이용권 3회를 드립니다.")
            new_id = st.text_input("희망 아이디", key="sign_id")
            new_pw = st.text_input("희망 비밀번호", type="password", key="sign_pw")
            new_name = st.text_input("닉네임 (이름)", key="sign_name")
            
            if st.button("가입하기", use_container_width=True):
                if new_id and new_pw and new_name:
                    if save_new_user(new_id, new_pw, new_name):
                        st.success(f"가입 완료! '{new_id}'로 로그인해주세요.")
                    else:
                        st.error("이미 존재하는 아이디입니다.")
                else:
                    st.warning("모든 칸을 채워주세요.")
                    
    st.stop() # 로그인 전에는 아래 코드 실행 막기

# ==========================================
# 🏠 메인 서비스 (로그인 성공 후)
# ==========================================
user_db = load_users()
current_user = st.session_state.username

# 가입 직후 세션 정보가 없을 경우를 대비한 안전장치
if current_user not in user_db:
    st.session_state.logged_in = False
    st.rerun()

current_credits = user_db[current_user]["credits"]

# 사이드바
st.sidebar.title(f"👤 {user_db[current_user]['name']}")
st.sidebar.caption(f"잔여 이용권: {current_credits}회")
st.sidebar.progress(min(current_credits / 10, 1.0))

if current_credits <= 0:
    st.error("이용권을 모두 사용하셨습니다. 관리자(민주님)에게 충전을 요청하세요!")
    st.stop()

st.title("🤖 Dual-AI Insight Hub")

if "current_chat_log" not in st.session_state: 
    st.session_state.current_chat_log = []

# 사이드바 버튼
with st.sidebar:
    st.divider()
    if st.button("➕ 새 대화 시작 (저장 후 초기화)", use_container_width=True):
        if st.session_state.current_chat_log:
            save_session_history(current_user, st.session_state.current_chat_log)
        st.session_state.current_chat_log = []
        st.rerun()

    st.subheader("🗂️ 지난 대화")
    history_list = load_history_list(current_user)
    for idx, item in enumerate(history_list):
        if st.button(f"📄 {item['title']}", key=f"hist_{idx}"):
            st.session_state.current_chat_log = item['dialogue']
            st.rerun()
            
    if st.button("로그아웃"):
        st.session_state.logged_in = False
        st.rerun()

# 탭 구성
tab1, tab2, tab3 = st.tabs(["💬 1. 답변", "⚔️ 2. 교차 분석", "🏆 3. 최종 결론"])

if st.session_state.current_chat_log:
    with tab1:
        for i, log in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1}. {log['q']}**") 
            c1, c2 = st.columns(2)
            c1.info("💎 다온"); c1.write(log['g_resp'])
            c2.success("🧠 루"); c2.write(log['o_resp'])
            st.divider()
    with tab2:
        for i, log in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1} 분석**")
            c1, c2 = st.columns(2)
            c1.info("💎 다온의 비평"); c1.write(log['g_an'])
            c2.success("🧠 루의 평가"); c2.write(log['o_an'])
            st.divider()
    with tab3:
        for i, log in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1} 결론**")
            st.markdown(log['final_con'])
            st.divider()

# 입력창
user_input = st.chat_input(f"질문을 입력하세요. (잔여: {current_credits}회)")

if user_input:
    if current_credits > 0:
        deduct_credit(current_user)
        
        with st.status("🚀 분석 엔진 가동 중...", expanded=True) as status:
            new_turn = {"q": user_input, "timestamp": datetime.now().strftime("%H:%M")}
            
            # 1. 답변
            st.write("1️⃣ 답변 작성 중...")
            try:
                model = genai.GenerativeModel('gemini-pro')
                new_turn["g_resp"] = model.generate_content(user_input).text
            except Exception as e: new_turn["g_resp"] = f"Gemini 오류: {e}"
            
            try:
                res = gpt_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":user_input}])
                new_turn["o_resp"] = res.choices[0].message.content
            except Exception as e: new_turn["o_resp"] = f"GPT 오류: {e}"

            # 2. 분석
            st.write("2️⃣ 교차 검증 중...")
            try:
                new_turn["g_an"] = model.generate_content(f"비판해줘: {new_turn['o_resp']}").text
            except: new_turn["g_an"] = "분석 실패"
            
            try:
                res = gpt_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":f"평가해줘: {new_turn['g_resp']}"}])
                new_turn["o_an"] = res.choices[0].message.content
            except: new_turn["o_an"] = "분석 실패"
            
            # 3. 결론
            st.write("3️⃣ 결론 도출 중...")
            try:
                final_prompt = f"질문: {user_input}\n답변1: {new_turn['g_resp']}\n답변2: {new_turn['o_resp']}\n비평1: {new_turn['g_an']}\n비평2: {new_turn['o_an']}\n종합 결론을 내려줘."
                res = gpt_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":final_prompt}])
                new_turn["final_con"] = res.choices[0].message.content
            except: new_turn["final_con"] = "결론 실패"

            st.session_state.current_chat_log.append(new_turn)
            status.update(label="완료!", state="complete", expanded=False)
            st.rerun()
    else:
        st.error("이용권 부족")

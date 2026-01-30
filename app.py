import streamlit as st
import google.generativeai as genai
from openai import OpenAI
from datetime import datetime
import json
import os
import concurrent.futures
import PyPDF2
from io import StringIO

# --- 1. 페이지 설정 (가장 먼저 실행) ---
st.set_page_config(page_title="Dual-AI Hub (Private)", layout="wide")

# ==========================================
# 🔒 [보안] 비밀번호 잠금 장치 (문지기)
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
            # secrets에 설정된 비밀번호와 비교
            if password_input == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 틀렸습니다.")
        except KeyError:
            st.error("🚨 서버에 비밀번호(APP_PASSWORD) 설정이 안 되어 있습니다.")
    
    return False

# 비밀번호가 틀리면 여기서 코드 실행을 멈춤 (아래 내용 절대 안 보여줌)
if not check_password():
    st.stop()

# ==========================================
# 🔓 로그인 성공 후 실행되는 메인 코드
# ==========================================

st.title("⚡ Dual-AI Insight Hub (Private)")

# --- 2. API 키 설정 ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
except KeyError:
    st.error("🚨 API 키 설정이 필요합니다. (.streamlit/secrets.toml 확인)")
    st.stop()

genai.configure(api_key=gemini_api_key)
gpt_client = OpenAI(api_key=gpt_api_key)

# --- 3. 모델 설정 (자동 탐색) ---
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
GPT_MODEL = "gpt-4o-mini" # 속도와 가성비 최강

# --- 4. 데이터 관리 (파일 저장) ---
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

# --- 5. 파일 처리 함수 (PDF/TXT) ---
def process_uploaded_file(uploaded_file):
    try:
        text = ""
        if uploaded_file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted: text += extracted + "\n"
        else: # 텍스트, 코드, 마크다운 등
            stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
            text = stringio.read()
            
        if not text.strip():
            return None, "⚠️ 파일 내용은 비어있습니다. (이미지 스캔본 PDF일 수 있음)"
        return text, f"✅ 로드 성공! ({len(text)}자)"
    except Exception as e:
        return None, f"❌ 파일 읽기 오류: {e}"

# --- 6. 세션 및 캐시 초기화 ---
if "sessions" not in st.session_state:
    st.session_state.sessions = load_data()
    st.session_state.active_index = 0
if "system_role" not in st.session_state:
    st.session_state.system_role = "너는 각 분야의 최고 전문가다."
if "active_index" not in st.session_state:
    st.session_state.active_index = 0
if "file_cache" not in st.session_state:
    st.session_state.file_cache = {"name": None, "content": None}

def get_active_session():
    if st.session_state.active_index >= len(st.session_state.sessions):
        st.session_state.active_index = 0
    return st.session_state.sessions[st.session_state.active_index]

# --- 7. API 호출 함수 ---
def call_gemini(prompt):
    model = genai.GenerativeModel(GEMINI_MODEL)
    return model.generate_content(prompt).text

def call_gpt(messages):
    response = gpt_client.chat.completions.create(model=GPT_MODEL, messages=messages)
    return response.choices[0].message.content

# --- 8. 사이드바 (컨트롤 패널) ---
with st.sidebar:
    st.success("🔐 로그인 완료") # 로그인 성공 표시
    st.header("🎮 제어 센터")
    
    # [1] 자료 업로드
    st.subheader("📂 자료 업로드")
    uploaded_file = st.file_uploader("파일 선택", type=["pdf", "txt", "csv", "py", "md"])
    
    if uploaded_file:
        if st.session_state.file_cache["name"] != uploaded_file.name:
            with st.spinner("파일 분석 중..."):
                content, msg = process_uploaded_file(uploaded_file)
                if content:
                    st.session_state.file_cache = {"name": uploaded_file.name, "content": content}
                    st.success(msg)
                else:
                    st.error(msg)
        else:
            st.success(f"💾 메모리 유지 중: {uploaded_file.name}")
    else:
        st.session_state.file_cache = {"name": None, "content": None}

    st.divider()

    # [2] 페르소나
    with st.expander("🎭 AI 역할 설정"):
        input_role = st.text_area("역할", value=st.session_state.system_role)
        if st.button("💾 역할 적용"):
            st.session_state.system_role = input_role
            st.success("적용됨")

    st.divider()

    # [3] 대화방 관리
    st.subheader("🗂️ 대화방")
    active_session = get_active_session()
    
    new_title = st.text_input("🏷️ 방 이름 수정", value=active_session["title"], key=f"title_{st.session_state.active_index}")
    if new_title != active_session["title"]:
        active_session["title"] = new_title
        save_data(st.session_state.sessions)
        st.rerun()

    c1, c2 = st.columns(2)
    with c1: 
        if st.button("➕ 새 대화"):
            st.session_state.sessions.insert(0, {"title": "새 대화", "history": []})
            st.session_state.active_index = 0
            save_data(st.session_state.sessions)
            st.rerun()
    with c2:
        if st.button("🗑️ 삭제"):
            st.session_state.sessions = [{"title": "새 대화", "history": []}]
            st.session_state.active_index = 0
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            st.rerun()

    st.markdown("---")
    for i, session in enumerate(st.session_state.sessions):
        label = session["title"][:15] + "..." if len(session["title"]) > 15 else session["title"]
        if i == st.session_state.active_index:
            st.button(f"📂 {label}", key=f"s{i}", disabled=True)
        else:
            if st.button(f"📄 {label}", key=f"s{i}"):
                st.session_state.active_index = i
                st.rerun()

# --- 9. 메인 로직 (병렬 처리 + 파일 분석) ---
active_session = get_active_session()
chat_history = active_session["history"]
current_role = st.session_state.system_role
current_file_content = st.session_state.file_cache["content"]

# 분석 트리거
trigger_analysis = False
auto_prompt = ""

if current_file_content:
    st.info(f"📎 **{st.session_state.file_cache['name']}** 내용을 참조합니다.")
    if st.button("📑 파일 요약 및 분석 실행", use_container_width=True):
        trigger_analysis = True
        auto_prompt = "이 파일의 핵심 내용을 요약하고 분석해줘."

user_input = st.chat_input("질문을 입력하세요...")

if user_input or trigger_analysis:
    final_question = user_input if user_input else auto_prompt

    # 첫 대화면 제목 자동 변경
    if len(chat_history) == 0 and active_session["title"] == "새 대화":
        active_session["title"] = final_question[:20]
        save_data(st.session_state.sessions)
        st.rerun()

    with st.status("⚡ 보안 접속 중... AI가 분석을 시작합니다.", expanded=True) as status:
        try:
            turn_data = {"q": final_question, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
            
            # 파일 내용이 있다면 프롬프트에 결합 (최대 3만자)
            context_input = final_question
            if current_file_content:
                safe_content = current_file_content[:30000]
                context_input = f"""
                [참고 자료 (파일)]:
                {safe_content}
                ...(생략됨)...
                
                [사용자 요청]: {final_question}
                """

            # 병렬 처리 시작
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # 1. 답변
                st.write(f"1️⃣ 답변 생성 중... (Role: {current_role[:10]})")
                f_g = executor.submit(call_gemini, f"System: {current_role}\n\n{context_input}")
                f_o = executor.submit(call_gpt, [{"role": "system", "content": current_role}, {"role": "user", "content": context_input}])
                
                turn_data["g_resp"] = f_g.result()
                turn_data["o_resp"] = f_o.result()

                # 2. 비평
                st.write("2️⃣ 교차 검증 중...")
                f_g_an = executor.submit(call_gemini, f"Role: {current_role}\nEvaluate GPT's answer. Don't use Pros/Cons list.\n\nGPT Answer: {turn_data['o_resp']}")
                f_o_an = executor.submit(call_gpt, [{"role": "system", "content": current_role}, {"role": "user", "content": f"Evaluate Gemini's answer. Don't use Pros/Cons list.\n\nGemini Answer: {turn_data['g_resp']}"}])
                
                turn_data["g_an"] = f_g_an.result()
                turn_data["o_an"] = f_o_an.result()

                # 3. 결론
                st.write("3️⃣ 최종 결론 도출...")
                final_p = f"""
                Role: {current_role}
                Task: Synthesize final conclusion. Fix errors found in review.
                
                Q: {final_question}
                Gemini: {turn_data['g_resp']}
                GPT: {turn_data['o_resp']}
                Review(G): {turn_data['g_an']}
                Review(O): {turn_data['o_an']}
                """
                turn_data["final_con"] = call_gpt([{"role": "user", "content": final_p}])

                active_session["history"].append(turn_data)
                save_data(st.session_state.sessions)
                
                status.update(label="✅ 분석 완료!", state="complete", expanded=False)
                st.rerun()

        except Exception as e:
            st.error(f"❌ 오류 발생: {e}")

# --- 10. 결과 출력 ---
if chat_history:
    st.caption(f"🕒 기록: {len(chat_history)}건 | 현재 방: {active_session['title']}")
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

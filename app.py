import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import json
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="Dual-AI Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# --- 1. API 키 설정 ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
    
    genai.configure(api_key=gemini_api_key)
    gpt_client = OpenAI(api_key=gpt_api_key)
except Exception as e:
    st.error("🚨 API 키 설정 오류: Secrets를 확인해주세요.")
    st.stop()

# --- 2. 모델 설정 (안정성 우선) ---
def get_gemini_model():
    # 가장 에러가 적은 표준 모델명을 사용합니다.
    return 'gemini-pro'

valid_model_name = get_gemini_model()

# --- 3. 히스토리 관리 (파일 저장) ---
HISTORY_FILE = "chat_history.json"

def save_session_to_file(session_data):
    if not session_data: return
    
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = []
    
    # 저장 양식: 시간 + 첫 질문 제목 + 대화 내용 전체
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": session_data[0]['q'][:15] + "...",
        "dialogue": session_data
    }
    
    history.insert(0, record) # 최신순 저장
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def load_history_from_file():
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

# --- 4. 세션 상태 초기화 ---
# 대화 내용이 리스트 형태로 쌓이는 공간입니다.
if "current_chat_log" not in st.session_state: 
    st.session_state.current_chat_log = []

# --- 5. 사이드바 (기록 보관소) ---
with st.sidebar:
    st.header("🗂️ 대화 기록")
    
    # [새 대화 시작] 버튼
    if st.button("➕ 새 대화 시작 (저장 & 초기화)", use_container_width=True):
        if st.session_state.current_chat_log:
            save_session_to_file(st.session_state.current_chat_log)
            st.toast("대화가 저장되었습니다.")
        
        st.session_state.current_chat_log = [] # 화면 비우기
        st.rerun()

    st.divider()
    
    # 저장된 기록 목록 불러오기
    history_list = load_history_from_file()
    if not history_list:
        st.caption("저장된 대화가 없습니다.")
    else:
        for idx, item in enumerate(history_list):
            # 버튼을 누르면 과거의 대화 로그를 현재 화면에 덮어씌움
            if st.button(f"📄 {item['timestamp']} | {item['title']}", key=f"hist_{idx}"):
                st.session_state.current_chat_log = item['dialogue']
                st.rerun()
                
    st.divider()
    if st.button("🗑️ 모든 기록 삭제"):
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
            st.session_state.current_chat_log = []
            st.rerun()

# --- 6. 메인 화면 (탭 구성 & 순환 출력) ---
# 탭을 미리 정의합니다.
tab1, tab2, tab3 = st.tabs(["💬 1. 답변 (Opinions)", "⚔️ 2. 교차 분석 (Cross-Analysis)", "🏆 3. 최종 결론 (Conclusion)"])

# 현재 대화 로그(리스트)에 있는 모든 내용을 '순환'하며 출력합니다.
if st.session_state.current_chat_log:
    
    # [Tab 1] 질문 & 답변 누적 출력
    with tab1:
        for i, log in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1}. {log['q']}**") 
            c1, c2 = st.columns(2)
            c1.info(f"💎 다온")
            c1.write(log['g_resp'])
            c2.success(f"🧠 루")
            c2.write(log['o_resp'])
            st.divider()

    # [Tab 2] 교차 분석 누적 출력
    with tab2:
        for i, log in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1} 분석**")
            c1, c2 = st.columns(2)
            c1.info("💎 다온의 비평")
            c1.write(log['g_an'])
            c2.success("🧠 루의 평가")
            c2.write(log['o_an'])
            st.divider()

    # [Tab 3] 최종 결론 누적 출력
    with tab3:
        for i, log in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1} 결론**")
            st.markdown(log['final_con'])
            st.divider()

# --- 7. 하단 입력창 및 실행 로직 ---
user_input = st.chat_input("질문을 입력하세요. (자동으로 3단계 분석이 진행됩니다)")

if user_input:
    # 진행 상황 표시 (Status Container)
    with st.status("🚀 다온과 루가 분석을 시작합니다...", expanded=True) as status:
        new_turn = {"q": user_input, "timestamp": datetime.now().strftime("%H:%M")}
        
        # --- STEP 1: 답변 생성 ---
        st.write("1️⃣ 답변 작성 중...")
        try:
            model = genai.GenerativeModel('gemini-pro')
            new_turn["g_resp"] = model.generate_content(user_input).text
        except Exception as e:
            new_turn["g_resp"] = f"Gemini 연결 오류: {e}"
        
        try:
            res = gpt_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":user_input}])
            new_turn["o_resp"] = res.choices[0].message.content
        except Exception as e:
            new_turn["o_resp"] = f"GPT 연결 오류: {e}"

        # --- STEP 2: 교차 분석 ---
        st.write("2️⃣ 상호 비판 중...")
        try:
            new_turn["g_an"] = model.generate_content(f"다음은 '루(GPT)'의 답변입니다. 논리적 허점을 비판해주세요:\n{new_turn['o_resp']}").text
        except: new_turn["g_an"] = "분석 실패"
        
        try:
            res = gpt_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":f"다음은 '다온(Gemini)'의 답변입니다. 창의성과 논리성을 평가해주세요:\n{new_turn['g_resp']}"}])
            new_turn["o_an"] = res.choices[0].message.content
        except: new_turn["o_an"] = "분석 실패"
        
        # --- STEP 3: 최종 결론 ---
        st.write("3️⃣ 최종 결론 도출 중...")
        try:
            final_prompt = f"""
            질문: {user_input}
            [다온 답변] {new_turn['g_resp']}
            [루 답변] {new_turn['o_resp']}
            [다온 비평] {new_turn['g_an']}
            [루 비평] {new_turn['o_an']}
            
            위 내용을 종합하여 명쾌한 최종 결론을 내려라.
            """
            res = gpt_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":final_prompt}])
            new_turn["final_con"] = res.choices[0].message.content
        except: new_turn["final_con"] = "결론 도출 실패"

        # 결과 저장 (리스트에 추가 -> 화면에 누적됨)
        st.session_state.current_chat_log.append(new_turn)
        
        status.update(label="✅ 분석 완료!", state="complete", expanded=False)
        st.rerun()

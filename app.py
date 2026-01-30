import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import json
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="Dual-AI Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# --- 1. 파일 기반 히스토리 관리 함수 ---
HISTORY_FILE = "chat_history.json"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except:
        return []

def save_session_history(session_data):
    if not session_data: return
    
    history = load_history()
    
    first_q = session_data[0].get('q', '제목 없음')
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": first_q[:15] + "...", 
        "dialogue": session_data
    }
    
    history.insert(0, record) 
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def delete_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)

# --- 2. API 키 및 모델 설정 ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
except FileNotFoundError:
    st.error("🚨 Secrets 설정이 안 되어 있습니다.")
    st.stop()

genai.configure(api_key=gemini_api_key)
gpt_client = OpenAI(api_key=gpt_api_key)

# --- 3. 세션 상태 초기화 ---
if "current_chat_log" not in st.session_state: 
    st.session_state.current_chat_log = []

# --- 4. 모델 선택 ---
def get_gemini_model():
    return 'gemini-pro'

valid_model_name = get_gemini_model()

# --- 5. 사이드바 (기록 보관소) ---
with st.sidebar:
    st.header("🗂️ 대화 기록")
    
    if st.button("➕ 새 대화 시작 (화면 초기화)", use_container_width=True):
        if st.session_state.current_chat_log:
            save_session_history(st.session_state.current_chat_log)
            st.toast("대화가 저장되었습니다.")
        
        st.session_state.current_chat_log = [] 
        st.rerun()

    st.divider()

    history_data = load_history()
    if not history_data:
        st.caption("저장된 대화가 없습니다.")
    else:
        for idx, item in enumerate(history_data):
            ts = item.get('timestamp', '')
            ti = item.get('title', '제목 없음')
            
            if st.button(f"{ts} | {ti}", key=f"hist_{idx}", use_container_width=True):
                st.session_state.current_chat_log = item.get('dialogue', [])
                st.rerun()

    st.divider()
    if st.button("🗑️ 모든 기록 삭제"):
        delete_history()
        st.session_state.current_chat_log = []
        st.rerun()

# --- 6. 메인 화면 출력 (순환 구조) ---
tab1, tab2, tab3 = st.tabs(["💬 1. 답변 (Opinions)", "⚔️ 2. 교차 분석 (Cross-Analysis)", "🏆 3. 최종 결론 (Conclusion)"])

if st.session_state.current_chat_log:
    with tab1:
        for i, turn in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1}. {turn['q']}**") 
            c1, c2 = st.columns(2)
            c1.info(f"💎 다온"); c1.write(turn.get('g_resp', ''))
            c2.success(f"🧠 루"); c2.write(turn.get('o_resp', ''))
            st.divider()

    with tab2:
        for i, turn in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1} 분석**")
            c1, c2 = st.columns(2)
            c1.info("💎 다온의 비평"); c1.write(turn.get('g_an', ''))
            c2.success("🧠 루의 평가"); c2.write(turn.get('o_an', ''))
            st.divider()

    with tab3:
        for i, turn in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1} 결론**")
            st.markdown(turn.get('final_con', ''))
            st.divider()
else:
    with tab1:
        st.info("하단 입력창에 질문을 입력하면 대화가 시작됩니다.")

# --- 7. 입력 및 자동화 프로세스 ---
user_input = st.chat_input("질문을 입력하세요.")

if user_input:
    with st.status("🚀 다온과 루가 분석 프로세스를 가동합니다...", expanded=True) as status:
        
        new_turn = {
            "q": user_input,
            "timestamp": datetime.now().strftime("%m/%d %H:%M"),
            "model_name": valid_model_name
        }

        # --- STEP 1: 답변 생성 ---
        st.write("1️⃣ 답변 작성 중...")
        try:
            model = genai.GenerativeModel(valid_model_name) 
            g_res = model.generate_content(user_input)
            new_turn["g_resp"] = g_res.text
        except Exception as e: new_turn["g_resp"] = f"에러: {e}"

        try:
            o_res = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": user_input}]
            )
            new_turn["o_resp"] = o_res.choices[0].message.content
        except Exception as e: new_turn["o_resp"] = f"에러: {e}"
            
        # --- STEP 2: 교차 분석 (여기가 핵심!) ---
        st.write("2️⃣ 교차 분석 중...")
        
        # [수정된 부분] 안전 설정 해제 (BLOCK_NONE) -> 비판 허용
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]

        # 다온 -> 루 분석
        try:
            prompt = f"다음은 '루(GPT)'의 답변입니다. 논리적 허점이나 보완할 점을 날카롭게 비판해주세요:\n---\n{new_turn['o_resp']}"
            # safety_settings를 추가해서 '검열' 때문에 멈추지 않게 함
            g_an = model.generate_content(prompt, safety_settings=safety_settings)
            new_turn["g_an"] = g_an.text
        except Exception as e: 
            # 만약 그래도 실패하면 에러 내용을 보여줌 (디버깅용)
            new_turn["g_an"] = f"분석 실패 (상세 사유): {e}"

        # 루 -> 다온 분석
        try:
            prompt = f"다음은 '다온(Gemini)'의 답변입니다. 창의성과 논리성을 평가해주세요:\n---\n{new_turn['g_resp']}"
            o_an = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role":"user","content":prompt}]
            )
            new_turn["o_an"] = o_an.choices[0].message.content
        except: new_turn["o_an"] = "분석 실패"

        # --- STEP 3: 최종 결론 ---
        st.write("3️⃣ 최종 결론 도출 중...")
        try:
            final_prompt = f"""
            질문: {new_turn['q']}
            [다온 답변] {new_turn['g_resp']}
            [루 답변] {new_turn['o_resp']}
            [다온 비평] {new_turn['g_an']}
            [루 비평] {new_turn['o_an']}
            종합 결론을 내려라.
            """
            final_res = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": final_prompt}]
            )
            new_turn["final_con"] = final_res.choices[0].message.content
        except: new_turn["final_con"] = "결론 도출 실패"

        st.session_state.current_chat_log.append(new_turn)
        status.update(label="✅ 분석 완료!", state="complete", expanded=False)
        st.rerun()

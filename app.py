import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import json
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="Dual-AI Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# --- 1. 파일 기반 히스토리 관리 함수 (세션 단위 저장) ---
HISTORY_FILE = "chat_history.json"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 예전 데이터 호환성을 위해 리스트인지 확인
            if isinstance(data, list):
                return data
            return []
    except:
        return []

def save_session_history(session_data):
    if not session_data: return
    
    history = load_history()
    
    # 저장 양식: 시간 + 첫 질문 제목 + 대화 내용 전체(리스트)
    first_q = session_data[0].get('q', '제목 없음')
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": first_q[:15] + "...", 
        "dialogue": session_data
    }
    
    history.insert(0, record) # 최신 글을 맨 위로
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

# --- 3. 세션 상태 초기화 (리스트로 변경) ---
# 대화가 차곡차곡 쌓일 '리스트'를 만듭니다.
if "current_chat_log" not in st.session_state: 
    st.session_state.current_chat_log = []

# --- 4. [닥터 다온] 모델 선택 로직 ---
def get_available_gemini_model():
    try:
        # 사용 가능한 모델 탐색
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferred_order = ['models/gemini-1.5-flash', 'models/gemini-pro', 'models/gemini-1.0-pro']
        for model in preferred_order:
            if model in available_models:
                return model
        if available_models: return available_models[0]
        return None
    except: return None

valid_model_name = get_available_gemini_model()
if not valid_model_name: valid_model_name = "gemini-pro"

# --- 5. 사이드바 (기록 보관소) ---
with st.sidebar:
    st.header("🗂️ 대화 기록 (History)")
    
    # [새 대화 시작] 버튼: 현재 대화를 저장하고 화면을 비웁니다.
    if st.button("➕ 새 대화 시작 (화면 초기화)", use_container_width=True):
        if st.session_state.current_chat_log:
            save_session_history(st.session_state.current_chat_log)
            st.toast("이전 대화가 기록에 저장되었습니다.")
        
        st.session_state.current_chat_log = [] # 리스트 비우기
        st.rerun()

    st.divider()

    # 저장된 기록 불러오기
    history_data = load_history()
    
    if not history_data:
        st.caption("아직 저장된 대화가 없습니다.")
    else:
        for idx, item in enumerate(history_data):
            # 안전하게 데이터 가져오기 (.get 사용)
            ts = item.get('timestamp', '')
            ti = item.get('title', '제목 없음')
            
            btn_label = f"{ts} | {ti}"
            if st.button(btn_label, key=f"hist_{idx}", use_container_width=True):
                # 선택한 기록(대화 전체 리스트)을 메인 화면에 복원
                st.session_state.current_chat_log = item.get('dialogue', [])
                st.rerun()

    st.divider()
    if st.button("🗑️ 모든 기록 삭제"):
        delete_history()
        st.session_state.current_chat_log = []
        st.rerun()

# --- 6. 메인 화면 출력 (순환 구조) ---

# 탭을 미리 만들어둡니다.
tab1, tab2, tab3 = st.tabs(["💬 1. 답변 (Opinions)", "⚔️ 2. 교차 분석 (Cross-Analysis)", "🏆 3. 최종 결론 (Conclusion)"])

# 현재 대화 목록에 있는 모든 내용을 '순환'하며 출력합니다.
if st.session_state.current_chat_log:
    
    # [Tab 1] 질문과 답변 누적 출력
    with tab1:
        for i, turn in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1}. {turn['q']}**") 
            c1, c2 = st.columns(2)
            with c1:
                st.info(f"💎 다온")
                st.write(turn.get('g_resp', ''))
            with c2:
                st.success(f"🧠 루")
                st.write(turn.get('o_resp', ''))
            st.divider()

    # [Tab 2] 교차 분석 누적 출력
    with tab2:
        for i, turn in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1}에 대한 분석**")
            c1, c2 = st.columns(2)
            with c1:
                st.info("💎 다온의 비평")
                st.write(turn.get('g_an', ''))
            with c2:
                st.success("🧠 루의 평가")
                st.write(turn.get('o_an', ''))
            st.divider()

    # [Tab 3] 최종 결론 누적 출력
    with tab3:
        for i, turn in enumerate(st.session_state.current_chat_log):
            st.markdown(f"**Q{i+1} 최종 결론**")
            st.markdown(turn.get('final_con', ''))
            st.divider()
else:
    # 대화가 없을 때 안내 메시지
    with tab1:
        st.info("하단 입력창에 질문을 입력하면 대화가 시작됩니다.")

# --- 7. 입력 및 자동화 프로세스 ---
user_input = st.chat_input("질문을 입력하세요. (자동으로 3단계 분석이 진행되며, 결과는 탭에 누적됩니다)")

if user_input:
    # 진행 상황 중계창
    with st.status("🚀 다온과 루가 분석 프로세스를 가동합니다...", expanded=True) as status:
        
        # 이번 턴의 데이터를 담을 그릇
        new_turn = {
            "q": user_input,
            "timestamp": datetime.now().strftime("%m/%d %H:%M"),
            "model_name": valid_model_name
        }

        # --- STEP 1: 답변 생성 ---
        st.write("1️⃣ 답변 작성 중...")
        
        # 다온
        try:
            model = genai.GenerativeModel(valid_model_name.replace('models/', '')) 
            g_res = model.generate_content(user_input)
            new_turn["g_resp"] = g_res.text
        except Exception as e:
            new_turn["g_resp"] = f"에러: {e}"

        # 루
        try:
            o_res = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "너는 냉철하고 논리적인 전문가 '루'다."},
                    {"role": "user", "content": user_input}
                ]
            )
            new_turn["o_resp"] = o_res.choices[0].message.content
        except Exception as e:
            new_turn["o_resp"] = f"에러: {e}"
            
        # --- STEP 2: 교차 분석 ---
        st.write("2️⃣ 교차 분석 중...")
        
        # 다온 -> 루
        try:
            prompt = f"다음은 '루(GPT)'의 답변이다. 논리적 허점이나 보완할 점을 비판해줘:\n{new_turn['o_resp']}"
            g_an = model.generate_content(prompt)
            new_turn["g_an"] = g_an.text
        except: new_turn["g_an"] = "분석 실패"

        # 루 -> 다온
        try:
            prompt = f"다음은 '다온(Gemini)'의 답변이다. 창의성과 감성, 논리성을 평가해줘:\n{new_turn['g_resp']}"
            o_an = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role":"user","content":prompt}]
            )
            new_turn["o_an"] = o_an.choices[0].message.content
        except: new_turn["o_an"] = "분석 실패"

        # --- STEP 3: 최종 결론 ---
        st.write("3️⃣ 최종 결론 도출 중...")
        
        try:
            # 이전 대화 맥락이 있다면 포함해서 결론을 내리도록 유도 (선택 사항)
            final_prompt = f"""
            너는 최종 의사결정권자다. 아래 내용을 종합하여 사용자에게 명쾌한 결론을 내려라.
            
            [질문] {new_turn['q']}
            [다온 답변] {new_turn['g_resp']}
            [루 답변] {new_turn['o_resp']}
            [다온 비평] {new_turn['g_an']}
            [루 비평] {new_turn['o_an']}
            
            작성 가이드:
            1. 핵심 쟁점 요약
            2. 양측 의견의 장단점 비교
            3. 최종 조언 (구체적으로)
            """
            final_res = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": final_prompt}]
            )
            new_turn["final_con"] = final_res.choices[0].message.content
        except: new_turn["final_con"] = "결론 도출 실패"

        # --- 저장 및 화면 갱신 ---
        # 이번 턴의 데이터를 대화 목록(리스트)에 추가합니다.
        st.session_state.current_chat_log.append(new_turn)
        
        status.update(label="✅ 분석 완료! 결과가 아래에 추가되었습니다.", state="complete", expanded=False)
        st.rerun()

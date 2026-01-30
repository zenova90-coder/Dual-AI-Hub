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
            return json.load(f)
    except:
        return []

def save_history(new_entry):
    history = load_history()
    history.insert(0, new_entry) # 최신 글을 맨 위로
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

# 세션 상태 초기화
if "current_view" not in st.session_state: 
    # 현재 화면에 보여줄 데이터 (질문, 답변, 분석, 결론)
    st.session_state.current_view = {
        "q": "", "g_resp": "", "o_resp": "", 
        "g_an": "", "o_an": "", "final_con": "",
        "model_name": ""
    }

# --- 3. [닥터 다온] 모델 선택 로직 ---
def get_available_gemini_model():
    try:
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

# --- 4. 사이드바 (기록 보관소) ---
with st.sidebar:
    st.header("🗂️ 대화 기록 (History)")
    
    if st.button("➕ 새 대화 시작하기", use_container_width=True):
        st.session_state.current_view = {k: "" for k in st.session_state.current_view}
        st.rerun()

    st.divider()

    # 저장된 기록 불러오기
    history_data = load_history()
    
    if not history_data:
        st.caption("아직 저장된 대화가 없습니다.")
    else:
        for idx, item in enumerate(history_data):
            # 버튼 이름은 질문의 앞 15글자 + 시간
            btn_label = f"{item['timestamp']} | {item['q'][:10]}..."
            if st.button(btn_label, key=f"hist_{idx}", use_container_width=True):
                # 선택한 기록을 메인 화면에 로드
                st.session_state.current_view = item

    st.divider()
    if st.button("🗑️ 모든 기록 삭제"):
        delete_history()
        st.rerun()

# --- 5. 메인 로직 (자동화 프로세스) ---

# 채팅 입력창
user_input = st.chat_input("질문을 입력하면 [답변 -> 분석 -> 결론]이 자동으로 진행됩니다.")

if user_input:
    # 1. 상태창 열기 (진행상황 중계)
    with st.status("🚀 AI 프로세스 가동 중...", expanded=True) as status:
        
        # 데이터 임시 저장소
        current_data = {
            "q": user_input,
            "timestamp": datetime.now().strftime("%m/%d %H:%M"),
            "model_name": valid_model_name
        }

        # --- STEP 1: 답변 생성 ---
        st.write("1️⃣ 1단계: 다온과 루가 답변을 작성하고 있습니다...")
        
        # 다온 (Gemini)
        try:
            model = genai.GenerativeModel(valid_model_name.replace('models/', '')) 
            g_res = model.generate_content(user_input)
            current_data["g_resp"] = g_res.text
        except Exception as e:
            current_data["g_resp"] = f"에러: {e}"

        # 루 (GPT)
        try:
            o_res = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "너는 냉철하고 논리적인 전문가 '루'다."},
                    {"role": "user", "content": user_input}
                ]
            )
            current_data["o_resp"] = o_res.choices[0].message.content
        except Exception as e:
            current_data["o_resp"] = f"에러: {e}"
            
        # --- STEP 2: 교차 분석 ---
        st.write("2️⃣ 2단계: 서로의 답변을 비판적으로 분석 중입니다...")
        
        # 다온 -> 루 분석
        try:
            prompt = f"다음은 '루(GPT)'의 답변이다. 논리적 허점이나 보완할 점을 비판해줘:\n{current_data['o_resp']}"
            g_an = model.generate_content(prompt)
            current_data["g_an"] = g_an.text
        except: current_data["g_an"] = "분석 실패"

        # 루 -> 다온 분석
        try:
            prompt = f"다음은 '다온(Gemini)'의 답변이다. 창의성과 감성, 논리성을 평가해줘:\n{current_data['g_resp']}"
            o_an = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role":"user","content":prompt}]
            )
            current_data["o_an"] = o_an.choices[0].message.content
        except: current_data["o_an"] = "분석 실패"

        # --- STEP 3: 최종 결론 ---
        st.write("3️⃣ 3단계: 루(GPT)가 의사봉을 잡고 최종 결론을 내립니다...")
        
        try:
            final_prompt = f"""
            너는 최종 의사결정권자다. 아래 내용을 종합하여 사용자에게 명쾌한 결론을 내려라.
            
            [질문] {current_data['q']}
            [다온 답변] {current_data['g_resp']}
            [루 답변] {current_data['o_resp']}
            [다온 비평] {current_data['g_an']}
            [루 비평] {current_data['o_an']}
            
            작성 가이드:
            1. 핵심 쟁점 요약
            2. 양측 의견의 장단점 비교
            3. 최종 조언 (구체적으로)
            """
            final_res = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": final_prompt}]
            )
            current_data["final_con"] = final_res.choices[0].message.content
        except: current_data["final_con"] = "결론 도출 실패"

        # --- 저장 및 종료 ---
        save_history(current_data) # 파일에 저장
        st.session_state.current_view = current_data # 화면에 표시
        
        status.update(label="✅ 모든 분석이 완료되었습니다!", state="complete", expanded=False)

# --- 6. 화면 출력 (탭 구성) ---

# 데이터가 있을 때만 화면 표시
if st.session_state.current_view["q"]:
    st.subheader(f"🗣️ 질문: {st.session_state.current_view['q']}")
    
    tab1, tab2, tab3 = st.tabs(["💬 1. 의견 제시", "⚔️ 2. 교차 검증", "🏆 3. 최종 결론"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.info(f"💎 다온 ({st.session_state.current_view['model_name']})")
            st.write(st.session_state.current_view["g_resp"])
        with c2:
            st.success("🧠 루 (GPT-4o)")
            st.write(st.session_state.current_view["o_resp"])

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.info("💎 다온의 비평")
            st.write(st.session_state.current_view["g_an"])
        with c2:
            st.success("🧠 루의 평가")
            st.write(st.session_state.current_view["o_an"])

    with tab3:
        st.markdown("### 📝 종합 결론 보고서")
        st.markdown(st.session_state.current_view["final_con"])
else:
    # 초기 화면 안내
    st.info("👋 사용자님 반갑습니다. 하단 입력창에 질문을 입력하세요. (자동 분석 & 기록 저장)")

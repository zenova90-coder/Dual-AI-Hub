import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import json
import os
from datetime import datetime
import time

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="Dual-AI Hub (Pro)", layout="wide")
st.title("🤖 Dual-AI Insight Hub (Pro Edition)")

# --- 2. API 키 및 클라이언트 설정 ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
except KeyError:
    st.error("🚨 Secrets 설정이 되어 있지 않습니다. .streamlit/secrets.toml 파일을 확인해주세요.")
    st.stop()

genai.configure(api_key=gemini_api_key)
gpt_client = OpenAI(api_key=gpt_api_key)

# --- 3. 세션 상태 초기화 (대화 누적 저장소) ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- 4. [Pro 전용] 고성능 모델 선택 로직 ---
def get_best_gemini_model():
    """
    Pro 모드이므로 성능이 가장 좋은 1.5 Pro 모델을 최우선으로 찾습니다.
    """
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # PRO 사용자를 위한 우선순위: 1.5 Pro (성능) -> 1.5 Flash (속도) -> 1.0 Pro (구버전)
        priority_list = [
            'models/gemini-1.5-pro',        # 최신 고성능
            'models/gemini-1.5-pro-latest', # 최신 고성능
            'models/gemini-1.5-flash',      # 빠름
            'models/gemini-pro'             # 구버전
        ]
        
        for p_model in priority_list:
            if p_model in models:
                return p_model
        
        return models[0] if models else "models/gemini-pro"
    except:
        return "models/gemini-pro"

current_model = get_best_gemini_model()

# --- 5. 사이드바 (컨트롤 패널) ---
with st.sidebar:
    st.header("🗂️ 제어 센터")
    
    if st.button("➕ 새 대화 시작하기 (화면 초기화)", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
    
    st.divider()
    st.success(f"💎 현재 연결된 다온: {current_model}")
    st.caption("Pro 모드가 활성화되어 더 깊이 있는 분석이 가능합니다.")

# --- 6. 메인 로직: 질문 입력 및 3단계 자동화 ---
user_input = st.chat_input("질문을 입력하세요. [답변 -> 교차분석 -> 결론]이 자동으로 진행됩니다.")

if user_input:
    # 진행 상황을 보여주는 상태창
    with st.status("🚀 고성능 AI 프로세스 가동 중...", expanded=True) as status:
        
        # 이번 턴의 데이터를 저장할 딕셔너리
        turn_data = {
            "q": user_input,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "model": current_model
        }

        try:
            # -------------------------------------------------------
            # [STEP 1] 답변 생성 (Generation)
            # -------------------------------------------------------
            st.write("1️⃣ 다온(Gemini Pro)과 루(GPT-4o)가 답변을 작성 중입니다...")
            
            # 다온 (Gemini)
            gemini = genai.GenerativeModel(current_model.replace('models/', ''))
            g_res = gemini.generate_content(user_input)
            turn_data["g_resp"] = g_res.text
            
            # 루 (GPT)
            o_res = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "너는 냉철하고 논리적인 전문가 '루'다."},
                    {"role": "user", "content": user_input}
                ]
            )
            turn_data["o_resp"] = o_res.choices[0].message.content

            # -------------------------------------------------------
            # [STEP 2] 교차 분석 (Critique)
            # -------------------------------------------------------
            st.write("2️⃣ 서로의 답변을 날카롭게 비평하고 있습니다...")

            # 다온이 루를 비평
            g_critique_prompt = f"다음은 '루(GPT)'의 답변이다. 논리적 헛점, 편향성, 혹은 보완할 점을 날카롭게 지적해라:\n\n{turn_data['o_resp']}"
            g_an = gemini.generate_content(g_critique_prompt)
            turn_data["g_an"] = g_an.text

            # 루가 다온을 비평
            o_critique_prompt = f"다음은 '다온(Gemini)'의 답변이다. 창의성, 감성, 그리고 논리적 구조를 평가하고 부족한 점을 지적해라:\n\n{turn_data['g_resp']}"
            o_an = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": o_critique_prompt}]
            )
            turn_data["o_an"] = o_an.choices[0].message.content

            # -------------------------------------------------------
            # [STEP 3] 최종 결론 (Conclusion)
            # -------------------------------------------------------
            st.write("3️⃣ 루(GPT)가 의사봉을 잡고 최종 판결을 내립니다...")

            final_prompt = f"""
            너는 이 토론의 최종 의사결정권자(판사)다.
            아래의 [질문], [두 AI의 답변], [상호 비판] 내용을 모두 종합하여
            사용자가 실행할 수 있는 가장 완벽한 '최종 결론'을 내려라.

            [질문] {turn_data['q']}
            [다온 답변] {turn_data['g_resp']}
            [루 답변] {turn_data['o_resp']}
            [다온 비평] {turn_data['g_an']}
            [루 비평] {turn_data['o_an']}
            
            결론은 명확하고 구체적이어야 한다.
            """
            final_res = gpt_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": final_prompt}]
            )
            turn_data["final_con"] = final_res.choices[0].message.content

            # -------------------------------------------------------
            # [저장] 성공적으로 완료되면 기록에 추가
            # -------------------------------------------------------
            st.session_state.chat_history.append(turn_data)
            status.update(label="✅ 분석 완료! 아래 탭에서 결과를 확인하세요.", state="complete", expanded=False)

        except Exception as e:
            st.error(f"❌ 처리 중 오류가 발생했습니다: {e}")
            status.update(label="⚠️ 오류 발생", state="error")

# --- 7. 화면 출력 (탭 누적 방식) ---
if st.session_state.chat_history:
    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["💬 1. 의견 대립", "⚔️ 2. 교차 검증", "🏆 3. 최종 결론"])

    # 누적된 대화 기록을 순서대로 출력
    for i, chat in enumerate(st.session_state.chat_history):
        # 각 질문마다 구분을 위한 번호와 질문 표시
        idx = i + 1
        
        with tab1:
            st.markdown(f"### Q{idx}. {chat['q']}")
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"💎 다온 ({chat['model']})")
                st.markdown(chat['g_resp'])
            with col2:
                st.success("🧠 루 (GPT-4o)")
                st.markdown(chat['o_resp'])
            st.markdown("---") # 구분선

        with tab2:
            st.markdown(f"### Q{idx}에 대한 분석")
            col1, col2 = st.columns(2)
            with col1:
                st.info("💎 다온의 비평")
                st.markdown(chat['g_an'])
            with col2:
                st.success("🧠 루의 평가")
                st.markdown(chat['o_an'])
            st.markdown("---")

        with tab3:
            st.markdown(f"### 🏆 Q{idx} 최종 판결")
            st.markdown(chat['final_con'])
            st.markdown("---")

else:
    # 대화 기록이 없을 때 초기 화면
    st.info("👋 Pro 모드가 활성화되었습니다. 질문을 입력하면 심층 분석이 시작됩니다.")

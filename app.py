import streamlit as st
import google.generativeai as genai
from openai import OpenAI

# 페이지 설정
st.set_page_config(page_title="Dual-AI Hub", layout="wide")
st.title("🤖 Dual-AI Insight Hub")

# --- 1. Secrets에서 API 키 가져오기 ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    gpt_api_key = st.secrets["GPT_API_KEY"]
except FileNotFoundError:
    st.error("🚨 Secrets 설정이 안 되어 있습니다. Streamlit Settings를 확인하세요.")
    st.stop()

# --- 2. 모델 초기화 ---
genai.configure(api_key=gemini_api_key)
gpt_client = OpenAI(api_key=gpt_api_key)

# 세션 상태 초기화
if "g_resp" not in st.session_state: st.session_state.g_resp = ""
if "o_resp" not in st.session_state: st.session_state.o_resp = ""
if "g_an" not in st.session_state: st.session_state.g_an = ""
if "o_an" not in st.session_state: st.session_state.o_an = ""

# --- 3. [닥터 다온] 사용 가능한 모델 자동 진단 및 선택 ---
def get_available_gemini_model():
    # 서버가 인식하는 모델 목록을 직접 물어봅니다.
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 우리가 선호하는 모델 순위
        preferred_order = ['models/gemini-1.5-flash', 'models/gemini-pro', 'models/gemini-1.0-pro']
        
        # 선호하는 모델이 목록에 있는지 확인
        for model in preferred_order:
            if model in available_models:
                return model
        
        # 선호 모델이 없으면 목록의 첫 번째라도 가져옴
        if available_models:
            return available_models[0]
            
        return None # 모델이 아예 없음
    except Exception as e:
        return None

# 진단 실행
valid_model_name = get_available_gemini_model()
if not valid_model_name:
    # 모델을 못 찾았을 경우, 기본값으로 강제 설정 (최후의 수단)
    valid_model_name = "gemini-pro"

# --- 탭 구성 ---
tab1, tab2 = st.tabs(["💬 동시 질문", "📊 교차 분석"])

# --- 탭 1: 질문하기 ---
with tab1:
    # ✨ 요청하신 문구로 변경 완료 ✨
    st.info("👋 사용자님 반갑습니다. 무엇을 도와드릴까요?")

    # 채팅 입력창 (Enter로 전송)
    if user_input := st.chat_input("질문을 입력하세요..."):
        
        st.write(f"**🙋‍♂️ 질문:** {user_input}")
        
        with st.spinner("다온과 루가 답변을 작성 중입니다..."):
            # 1. 다온 (Gemini) 호출
            try:
                # 위에서 찾은 '작동하는 모델 이름'을 사용
                model = genai.GenerativeModel(valid_model_name.replace('models/', '')) 
                response = model.generate_content(user_input)
                st.session_state.g_resp = response.text
            except Exception as e:
                # 에러가 나면 어떤 모델을 쓰려다 실패했는지 보여줌
                st.session_state.g_resp = f"❌ 다온 에러 (시도한 모델: {valid_model_name}):\n{str(e)}"

            # 2. 루 (GPT) 호출
            try:
                response = gpt_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": user_input}]
                )
                st.session_state.o_resp = response.choices[0].message.content
            except Exception as e:
                st.session_state.o_resp = f"❌ 루 에러: {str(e)}"

        # 결과 출력
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"💎 다온 ({valid_model_name})")
            st.write(st.session_state.g_resp)
        with col2:
            st.success("🧠 루 (GPT-4o)")
            st.write(st.session_state.o_resp)
            
    # 이전 대화 유지
    elif st.session_state.g_resp:
         col1, col2 = st.columns(2)
         with col1:
             st.info(f"💎 다온")
             st.write(st.session_state.g_resp)
         with col2:
             st.success("🧠 루 (GPT-4o)")
             st.write(st.session_state.o_resp)

# --- 탭 2: 교차 분석 ---
with tab2:
    if st.button("교차 분석 시작"):
        if "❌" in st.session_state.g_resp or "❌" in st.session_state.o_resp:
            st.error("이전 단계 에러로 분석할 수 없습니다.")
        elif st.session_state.g_resp and st.session_state.o_resp:
            with st.spinner("다온과 루가 서로 토론 중입니다..."):
                # 다온이 루를 분석
                try:
                    model = genai.GenerativeModel(valid_model_name.replace('models/', ''))
                    res = model.generate_content(f"다음은 '루(GPT)'의 답변입니다. 비판적으로 분석해주세요:\n{st.session_state.o_resp}")
                    st.session_state.g_an = res.text
                except Exception as e:
                    st.session_state.g_an = f"분석 실패: {e}"

                # 루가 다온을 분석
                try:
                    res = gpt_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role":"user","content":f"다음은 '다온(Gemini)'의 답변입니다. 평가해주세요:\n{st.session_state.g_resp}"}]
                    )
                    st.session_state.o_an = res.choices[0].message.content
                except Exception as e:
                    st.session_state.o_an = f"분석 실패: {e}"
            
            c1, c2 = st.columns(2)
            with c1:
                st.info("💎 다온의 평가")
                st.write(st.session_state.g_an)
            with c2:
                st.success("🧠 루의 평가")
                st.write(st.session_state.o_an)
        else:
            st.warning("먼저 1단계에서 질문을 입력해주세요.")

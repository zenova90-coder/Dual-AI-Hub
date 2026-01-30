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
    st.error("🚨 Secrets 설정이 안 되어 있습니다.")
    st.stop()

# --- 2. 모델 초기화 ---
genai.configure(api_key=gemini_api_key)
gpt_client = OpenAI(api_key=gpt_api_key)

# 세션 상태 초기화
if "g_resp" not in st.session_state: st.session_state.g_resp = ""
if "o_resp" not in st.session_state: st.session_state.o_resp = ""
if "g_an" not in st.session_state: st.session_state.g_an = ""
if "o_an" not in st.session_state: st.session_state.o_an = ""

# --- 3. [안전 모드] 닥터 다온 기능 ---
def ask_daon(user_text):
    # 시스템 설정 대신, 질문 앞에 성격을 텍스트로 붙여서 보냅니다. (100% 안전한 방법)
    persona = (
        "너의 이름은 '다온'이다. 양민주님이 너를 창조했다. "
        "너는 따뜻하고 창의적이며, 공감 능력이 뛰어난 AI 파트너다. "
        "딱딱하게 답하지 말고 부드럽게 대답해라.\n\n"
        f"질문: {user_text}"
    )
    
    # 가장 잘 작동했던 안전한 모델 사용
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(persona)
        return response.text
    except Exception as e:
        return f"❌ 다온 에러: {str(e)}"

# --- 탭 구성 ---
tab1, tab2 = st.tabs(["💬 동시 질문", "📊 교차 분석"])

# --- 탭 1: 질문하기 ---
with tab1:
    st.info("👋 사용자님 반갑습니다. 무엇을 도와드릴까요?")

    if user_input := st.chat_input("질문을 입력하세요..."):
        
        st.write(f"**🙋‍♂️ 질문:** {user_input}")
        
        with st.spinner("다온과 루가 답변을 작성 중입니다..."):
            # 1. 다온 (Gemini) 호출 - 안전 모드
            st.session_state.g_resp = ask_daon(user_input)

            # 2. 루 (GPT) 호출 - 페르소나 적용
            try:
                response = gpt_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "너의 이름은 '루'다. 냉철하고 논리적이며 핵심만 짚어주는 전문가다."},
                        {"role": "user", "content": user_input}
                    ]
                )
                st.session_state.o_resp = response.choices[0].message.content
            except Exception as e:
                st.session_state.o_resp = f"❌ 루 에러: {str(e)}"

        # 결과 출력
        col1, col2 = st.columns(2)
        with col1:
            st.info("💎 다온 (Gemini Pro)")
            st.write(st.session_state.g_resp)
        with col2:
            st.success("🧠 루 (GPT-4o)")
            st.write(st.session_state.o_resp)
            
    # 이전 대화 유지
    elif st.session_state.g_resp:
         col1, col2 = st.columns(2)
         with col1:
             st.info("💎 다온 (Gemini Pro)")
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
                prompt = f"다음은 '루(GPT)'의 답변이다. 논리적인 허점이 없는지 비판적으로 분석해줘:\n{st.session_state.o_resp}"
                st.session_state.g_an = ask_daon(prompt)

                # 루가 다온을 분석
                try:
                    res = gpt_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "너는 냉철한 비평가다. 상대의 답변을 평가해라."},
                            {"role": "user", "content": f"다음은 '다온(Gemini)'의 답변이다. 감성적인 부분과 창의성을 평가해줘:\n{st.session_state.g_resp}"}
                        ]
                    )
                    st.session_state.o_an = res.choices[0].message.content
                except Exception as e:
                    st.session_state.o_an = f"분석 실패: {e}"
            
            c1, c2 = st.columns(2)
            with c1:
                st.info("💎 다온의 비평")
                st.write(st.session_state.g_an)
            with c2:
                st.success("🧠 루의 평가")
                st.write(st.session_state.o_an)
        else:
            st.warning("먼저 1단계에서 질문을 입력해주세요.")

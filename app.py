import streamlit as st
import json
import os

st.set_page_config(page_title="RAG 실행", layout="centered")
st.title("RAG 설정 및 실행")

if "run_rag" not in st.session_state:
    st.session_state["run_rag"] = False

# 파일 업로드 섹션
st.subheader("RAG 입력 파일 업로드")
doc_file = st.file_uploader("문서 텍스트 파일 (.txt)", type="txt", key="doc")
query_file = st.file_uploader("Query 목록 파일 (.txt)", type="txt", key="query")

save_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploaded"))
os.makedirs(save_dir, exist_ok=True)

uploaded = False


st.markdown("<hr>", unsafe_allow_html=True)

st.subheader("LLM 모델 정보")
llm_provider = st.selectbox("사용할 LLM 모델 선택", ["OpenAI", "Gemini", "Local"], key="llm_provider")

llm_config = {}
if llm_provider == "OpenAI":
    llm_config["provider"] = "openai"
    llm_config["config"] = {
        "model_name": st.text_input("모델 이름", value="gpt-4", key="openai_llm_model_name"),
        "api_key": st.text_input("API 키", key="openai_llm_api_key")
    }
elif llm_provider == "Gemini":
    llm_config["provider"] = "gemini"
    llm_config["config"] = {
        "model_name": st.text_input("모델 이름", value="gemini-v1", key="gemini_llm_model_name"),
        "api_version": st.text_input("api_version", value="v1beta", key="gmemini_llm_model_version"),
        "api_key": st.text_input("API 키", key="gemini_llm_api_key")
    }
elif llm_provider == "Local":
    llm_config["provider"] = "local"
    llm_config["config"] = {
        "model_name": st.text_input("모델 이름", value="local-llm", key="local_llm_model_name"),
        "api_url": st.text_input("API URL", key="local_llm_api_url")
    }

st.markdown("<hr>", unsafe_allow_html=True)


st.subheader("Embedding 모델 정보")
embedding_provider = st.selectbox("사용할 Embedding 모델 선택", ["OpenAI", "Gemini", "Local"], key="embedding_provider")

embedding_config = {}
if embedding_provider == "OpenAI":
    embedding_config["provider"] = "openai"
    embedding_config["config"] = {
        "model_name": st.text_input("모델 이름", value="text-embedding-ada-002", key="openai_embedding_model_name"),
        "api_key": st.text_input("API 키", key="openai_embedding_api_key")
    }
elif embedding_provider == "Gemini":
    embedding_config["provider"] = "gemini"
    embedding_config["config"] = {
        "model_name": st.text_input("모델 이름", value="embedding-001", key="gemini_embedding_model_name"),
        "api_version": st.text_input("api_version", value="v1beta", key="gemini_embedding_model_version"),
        "api_key": st.text_input("API 키", key="gemini_embedding_api_key")
    }
elif embedding_provider == "Local":
    embedding_config["provider"] = "local"
    embedding_config["config"] = {
        "model_name": st.text_input("모델 이름", value="local-embedding", key="local_embedding_model_name"),
        "api_url": st.text_input("API URL", key="local_embedding_api_url")
    }


st.markdown("<hr>", unsafe_allow_html=True)
cold1, col2, col3 = st.columns([3, 1, 3])
with col2:
    file_upload = st.button("Save")

if file_upload:
    api_config = {
        "llm": llm_config,
        "embedding": embedding_config
    }

    json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploaded", "api_config.json"))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(api_config, f, indent=2, ensure_ascii=False)
    st.session_state["llm_config"] = llm_config
    st.session_state["embedding_config"] = embedding_config

    if doc_file and query_file:
        with open(os.path.join(save_dir, "document.txt"), "w", encoding="utf-8") as f:
            f.write(doc_file.read().decode("utf-8"))
        with open(os.path.join(save_dir, "queries.txt"), "w", encoding="utf-8") as f:
            f.write(query_file.read().decode("utf-8"))
        uploaded = True

    if uploaded:
        st.session_state["run_rag"] = False
        st.success("모든 파일이 업로드되었습니다.")
        st.session_state["file_upload"] = True
        st.switch_page("pages/choose_metrics.py")
    else:
        st.warning("모든 파일을 업로드해주세요.")

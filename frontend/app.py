import streamlit as st
import json
import os

st.set_page_config(page_title="RAG 실행", layout="centered")
st.title("RAG 설정 및 실행")

st.header("RAG 입력 파일 업로드")
doc_file = st.file_uploader("문서 텍스트 파일 (.txt)", type="txt", key="doc")
api_file = st.file_uploader("API 설정 파일 (.json)", type="json", key="api")
query_file = st.file_uploader("Query 목록 파일 (.txt)", type="txt", key="query")

save_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploaded"))
os.makedirs(save_dir, exist_ok=True)

uploaded = False

if doc_file and api_file and query_file:
    with open(os.path.join(save_dir, "document.txt"), "w", encoding="utf-8") as f:
        f.write(doc_file.read().decode("utf-8"))

    api_json = json.load(api_file)
    with open(os.path.join(save_dir, "api_config.json"), "w", encoding="utf-8") as f:
        json.dump(api_json, f, indent=2, ensure_ascii=False)

    with open(os.path.join(save_dir, "queries.txt"), "w", encoding="utf-8") as f:
        f.write(query_file.read().decode("utf-8"))

    uploaded = True

run_rag = st.button("Run RAG")

if run_rag:
    if uploaded:
        st.success("모든 파일이 업로드되었습니다.")
        st.session_state["run_rag"] = True
        st.switch_page("pages/choose_metrics.py")
    else:
        st.warning("모든 파일을 업로드해주세요.")

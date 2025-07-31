import streamlit as st
import json
import os

st.set_page_config(page_title="RAG 평가 도구", layout="centered")
st.title("RAG 평가 결과 보기")

st.header("1. RAG 실행 설정")
doc_file = st.file_uploader("문서 텍스트 파일 (.txt)", type="txt")
api_file = st.file_uploader("API 설정 파일 (.json)", type="json")
query_file = st.file_uploader("Query 목록 파일 (.txt)", type="txt")

if doc_file and api_file and query_file:
    st.success("모든 파일이 업로드되었습니다.")
    if st.button("RAG 실행"):
        st.info("RAG 실행 중입니다... (이후 결과가 아래에 표시됩니다.)")
else:
    st.warning("세 가지 파일을 모두 업로드해주세요.")


st.header("2. RAG 결과 요약")

current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, "metric_summary.json")

if os.path.exists(json_path):
    with open(json_path, "r", encoding="utf-8") as storage:
        data = json.load(storage)

    for state in data:
        with st.expander(f"Query {state['qid']}: {state['query']}"):
            st.markdown(f"**Answer:** {state['answer']}")
            st.markdown(f"**E2E Score:** `{state['e2e_score']}`")
            st.markdown(f"**Total Time:** `{state['total_time_ms']} ms`")

            for module, metrics in state["modulers"].items():
                st.markdown(f"**모듈: `{module}`**")
                st.table([{
                    "Metric": m["metric"],
                    "Score": f"{m['score']} {m.get('unit', '')}",
                    "Time (ms)": m["time_ms"]
                } for m in metrics])
else:
    st.info("metric_summary.json 파일을 불러올 수 없습니다. 먼저 RAG 실행을 완료해주세요.")

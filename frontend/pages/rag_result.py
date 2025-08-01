import streamlit as st
import json
import os

st.set_page_config(page_title="RAG 결과", layout="wide")
st.title("RAG result about Query")

if "run_rag" not in st.session_state or not st.session_state["run_rag"]:
    st.warning("먼저 파일 업로드 후, RAG 실행 버튼을 눌러주세요.")
    st.stop()
if "metric_config_saved" not in st.session_state or not st.session_state["metric_config_saved"]:
    st.warning("먼저 Metric 설정을 저장해주세요.")
    st.stop()

json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "metric_summary.json"))

if not os.path.exists(json_path):
    st.error("metric_summary.json 파일을 찾을 수 없습니다. 먼저 RAG 실행을 완료해주세요.")
    st.stop()

with open(json_path, "r", encoding="utf-8") as rag_result:
    data = json.load(rag_result)

st.subheader("Query Summary")
summary_rows = [{
    "Query ID": entry["qid"],
    "Query": entry["query"],
    "E2E Score": entry["e2e_score"],
    "Total Time (ms)": entry["total_time_ms"]
} for entry in data]

st.dataframe(summary_rows, use_container_width=True)

st.markdown("\n")
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("\n")
st.subheader("Query 상세 보기")
query_options = [f"[Query{entry['qid']}] {entry['query']}" for entry in data]
selected = st.selectbox("상세 내용을 보고 싶은 Query를 선택하세요:", ["선택 안함"] + query_options)

if "selected_qid" not in st.session_state:
    st.session_state.selected_qid = None

if selected != "선택 안함":
    current_qid = int(selected.split("]")[0].replace("[Query", ""))
    if st.session_state.selected_qid != current_qid:
        st.session_state.selected_qid = current_qid
if selected == "선택 안함":
    st.session_state.selected_qid = None


if st.session_state.selected_qid is not None:
    entry = next(e for e in data if e["qid"] == st.session_state.selected_qid)
    st.markdown(f"Query {entry['qid']}")

    module_items = []
    for module, item in entry["modulers"].items():
        for m in item:
            module_items.append({
                "Module": module,
                "Metric": m["metric"],
                "Score": f"{m['score']} {m.get('unit', '')}",
                "Time (ms)": m["time_ms"]
            })

    st.table(module_items)
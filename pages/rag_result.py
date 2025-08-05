import streamlit as st
import json
import os
from application.run_rag import RunRag

st.set_page_config(page_title="RAG 결과", layout="wide")
st.title("RAG result about Query")

if "file_upload" not in st.session_state or not st.session_state["file_upload"]:
    st.warning("먼저 파일 업로드 후, RAG 실행 버튼을 눌러주세요.")
    st.stop()
if "metric_config_saved" not in st.session_state or not st.session_state["metric_config_saved"]:
    st.warning("먼저 Metric 설정을 저장해주세요.")
    st.stop()
if "run_rag" not in st.session_state or not st.session_state["run_rag"]:
    st.warning("아직 RAG가 실행 중 입니다.")
    st.stop()


json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "Rag_summary.json"))

if not os.path.exists(json_path):
    st.error("Rag_summary.json 파일을 찾을 수 없습니다. 먼저 RAG 실행을 완료해주세요.")
    st.stop()

with open(json_path, "r", encoding="utf-8") as rag_result:
    data = json.load(rag_result)


st.subheader("단일 Query 입력 및 실행")
st.markdown("\n")

col1, col2, col3, col4 = st.columns([2, 6, 2, 1])
with col2:
    user_query = st.text_input("Query를 입력하세요", key="single_query_input")

with col3:
    st.markdown("<br>", unsafe_allow_html=True)
    query_button = st.button("Run RAG with Query")

if query_button:
    if user_query.strip() == "":
        st.warning("Query를 입력해주세요.")
    else:
        save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploaded", "test_query.json"))
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump({"query": user_query.strip()}, f, ensure_ascii=False, indent=2)

        with st.spinner("RAG 실행 중입니다. 잠시만 기다려주세요..."):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.normpath(os.path.join(base_dir, "..", "public", "Test_Rag_summary.json"))

            test_rag = RunRag(st.session_state["test_rag"])
            test_query_result = test_rag.run_test(save_path=file_path, query=[user_query.strip()])
            st.session_state["test_query_result"] = test_query_result

            cold1, col2, col3 = st.columns([1, 1, 1])

            test_query_result = open(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "Test_Rag_summary.json")), "r", encoding="utf-8")
            test_query_result = json.load(test_query_result)
            entry_test = next(e for e in test_query_result if e["qid"] == st.session_state["test_num"] - 1)
            with col2:
                st.markdown(f"Answer: {entry_test['answer']}")
            module_items = []
            for module, item in entry_test["modulers"].items():
                for m in item:
                    module_items.append({
                        "Module": module,
                        "Metric": m["metric"],
                        "Score": f"{m['score']} {m.get('unit', '')}",
                        "Time (ms)": m["time_ms"]
                    })

            st.table(module_items)



st.markdown("\n")
st.markdown("<hr>", unsafe_allow_html=True)


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


st.markdown("\n")
st.markdown("<hr>", unsafe_allow_html=True)


st.subheader("사용자 사전입력 Query Summary")
summary_rows = [{
    "Query ID": entry["qid"],
    "Query": entry["query"],
    "E2E Score": entry["e2e_score"],
    "Total Time (ms)": entry["total_time_ms"]
} for entry in data]

st.dataframe(summary_rows, use_container_width=True)

st.markdown("\n")
st.markdown("<hr>", unsafe_allow_html=True)


st.subheader("Test Query Summary")
test_summary_rows = [{
    "Query ID": entry["qid"],
    "Query": entry["query"],
    "E2E Score": entry["e2e_score"],
    "Total Time (ms)": entry["total_time_ms"]
} for entry in test_query_result]

st.dataframe(test_summary_rows, use_container_width=True)
import streamlit as st
import os
import json

st.set_page_config(page_title="Moduler 분석", layout="wide")
st.title("Moduler 분석")

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
    st.error("metric_summary.json 파일을 찾을 수 없습니다. 먼저 RAG 실행을 완료해주세요.")
    st.stop()

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

module_scores = {}

for entry in data:
    for module, metrics in entry["modulers"].items():
        for m in metrics:
            score = float(m["score"])
            unit = m.get("unit", "")
            if unit == "":
                score *= 100
            if module not in module_scores:
                module_scores[module] = []
            module_scores[module].append(score)

st.subheader("Module 평균 Score")
avg_table = []
for module, scores in module_scores.items():
    avg_table.append({
        "Module": module,
        "Average Score": f"{sum(scores) / len(scores):.2f} %"
    })
st.table(avg_table)

st.markdown("<hr>", unsafe_allow_html=True)
st.subheader("Module 상세 보기")

module_options = [f"[Module: {module}] score: {sum(scores) / len(scores):.2f} %" for module, scores in module_scores.items()]
selected_module = st.selectbox("상세 내용을 볼 모듈을 선택하세요:", ["선택 안함"] + module_options)

if "selected_module" not in st.session_state:
    st.session_state.selected_module = None
if selected_module != "선택 안함":
    current_module = selected_module.split("]")[0].replace("[Module: ", "")
    if st.session_state.selected_module != current_module:
        st.session_state.selected_module = current_module
if selected_module == "선택 안함":
    st.session_state.selected_module = None


if st.session_state.selected_module is not None:
    detailed_rows = []
    for entry in data:
        qid = entry["qid"]
        for module, metrics in entry["modulers"].items():
            if module == st.session_state.selected_module:
                for m in metrics:
                    detailed_rows.append({
                        "Query": qid,
                        "Metric": m["metric"],
                        "Score": f"{m['score']} {m.get('unit', '')}",
                        "Time (ms)": m["time_ms"]
                    })

    st.table(detailed_rows)

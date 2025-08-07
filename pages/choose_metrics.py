import streamlit as st
import json
import os
from application.build_rag import buildRag
from application.run_rag import RunRag



st.set_page_config(page_title="Metric 선택", layout="wide")
st.title("Metric 선택")

if "file_upload" not in st.session_state or not st.session_state["file_upload"]:
    st.warning("먼저 파일 업로드 후, RAG 실행 버튼을 눌러주세요.")
    st.stop()

available_metrics = {
    "E2E LLM Based Metic" : ["E2ESYNRelevancyMetric", "E2EScoringRelevancyMetric", "E2EQGenRelevancyMetric"],
    "E2E Non-LLM Based Metric": ["AnswerQuerySimilarity"],
    "Generator LLM Based Metric": ["A2RYNFaithfulnessMetric", "A2RSimpleScoringFaithfulnessMetric", "A2RTruthfulFaithfulnessMetric", "A2RHybridFaithfulnessMetric", ],
    "Generator Non-LLM Based Metric": ["AnswerContextSimilarity", "AnswerCentricSimilarityVariance", "MutualInformation_KSG", "RetrievalDeviationfromAnswer"],
    "Retriever LLM Based Metric": [],
    "Retriever Non-LLM Based Metric": ["KeywordMatchingMetric", "JaccardSimilarityMetric", "CosineSimilarityMetric", "EuclideanDistanceMetric", "ManhattanDistanceMetric", "NegativeRejectionRateMetric", "DiversityMetric", "GeneralizedEmbeddingCoverageError", "EmbeddingCosineSimilarityEvaluation", "PairwiseCosineSimilarityVariance"]
}

selected_metrics = {}

st.subheader("모듈러별 Metric 선택")

for module, metrics in available_metrics.items():
    selected = st.multiselect(
        f"{module}을 선택하세요:",
        options=metrics,
        key=f"{module}_metrics"
    )
    selected_metrics[module] = selected


if st.button("Metric 설정 저장"):
    st.session_state["selected_metrics"] = selected_metrics
    st.success("Metric 설정이 저장되었습니다. 이제 RAG 실행에서 이 Metric으로 평가됩니다.")
    st.session_state["metric_config_saved"] = True

    with st.spinner("RAG 실행 중입니다. 잠시만 기다려주세요..."):
        my_rag = buildRag()
        st.session_state["my_rag"] = my_rag.buildRag()
        test_rag = buildRag()
        st.session_state["test_rag"] = test_rag.buildRag()
        st.session_state["test_num"] = 0
        st.session_state["run_rag"] = False
        rag_runner = RunRag(my_rag.rag)
        rag_history = rag_runner.run()

    if st.session_state.get("run_rag"):
        st.success("RAG 실행이 완료되었습니다.")
        st.switch_page("pages/rag_result.py")


if "selected_metrics" in st.session_state:
    st.markdown("### 현재 설정된 Metric 목록")
    for module, metrics in st.session_state["selected_metrics"].items():
        st.markdown(f"**{module}**: {', '.join(metrics) if metrics else '선택 안됨'}")

st.markdown("<hr>", unsafe_allow_html=True)

save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "metric_config.json"))

if "selected_metrics" in st.session_state:
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(st.session_state["selected_metrics"], f, indent=2, ensure_ascii=False)
    st.success(f"Metric 설정이 '{save_path}' 에 저장되었습니다.")
else:
    st.warning("저장된 Metric 설정이 없습니다.")
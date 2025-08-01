import streamlit as st
import json
import os

st.set_page_config(page_title="Metric 선택", layout="wide")
st.title("Metric 선택")

if "run_rag" not in st.session_state or not st.session_state["run_rag"]:
    st.warning("먼저 파일 업로드 후, RAG 실행 버튼을 눌러주세요.")
    st.stop()

available_metrics = {
    "E2E LLM Based Metic" : ["E2ESYNRelevancyMetric", "E2EScoringRelevancyMetric", "E2EQGenRelevancyMetric"],
    "E2E Non-LLM Based Metric": ["AnswerQuerySimilarity", "e2eCosineConsistencyMetric", "e2eCovarianceConsistencyMetric"],
    "Generator LLM Based Metric": ["A2RYNFaithfulnessMetric", "A2RSimpleScoringFaithfulnessMetric", "A2RHallucinationFaithfulnessMetric", "A2RTruthfulFaithfulnessMetric", "A2RYNFaithfulnessMetricSingleCall", "A2RHybridFaithfulnessMetric"],
    "Generator Non-LLM Based Metric": ["AnswerContextSimilarity", "AnswerCentricSimilarityVariance", "MutualInformation_KSG", "RetrievalDeviationfromAnswer", "RetrievaltopkMeanAnswerSimilarity"],
    "Retriever LLM Based Metric": ["RandomDocumentInjectionEffect"],
    "Retriever Non-LLM Based Metric": ["KeywordMatchingMetric", "JaccardSimilarityMetric", "CosineSimilarityMetric", "EuclideanDistanceMetric", "ManhattanDistanceMetric", "NegativeRejectionRateMetric", "PrecisionMetric", "RankingConsistencyKendallTau", "DiversityMetric", "GeneralizedEmbeddingCoverageError", "EmbeddingCosineSimilarityEvaluation", "PairwiseCosineSimilarityVariance"]
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
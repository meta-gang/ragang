from common.bases.datas.linker import Linker
from container import RAGContainer
from metrics.builtin.e2eMetric_LLMBased import E2ESYNRelevancyMetric, E2EScoringRelevancyMetric, E2EQGenRelevancyMetric
from metrics.builtin.e2eMetric_nonLLMBased import AnswerQuerySimilarity, e2eCosineConsistencyMetric, e2eCovarianceConsistencyMetric
from metrics.builtin.generatorMetric_LLMBased import A2RYNFaithfulnessMetric, A2RSimpleScoringFaithfulnessMetric, A2RHallucinationFaithfulnessMetric, A2RTruthfulFaithfulnessMetric, A2RYNFaithfulnessMetricSingleCall, A2RHybridFaithfulnessMetric
from metrics.builtin.generatorMetric_NonLLMBased import AnswerContextSimilarity, AnswerCentricSimilarityVariance, MutualInformation_KSG, RetrievalDeviationfromAnswer, RetrievaltopkMeanAnswerSimilarity
from metrics.builtin.retriever_LLMBased import RandomDocumentInjectionEffect
from metrics.builtin.retriever_NonLLMBased import KeywordMatchingMetric, JaccardSimilarityMetric, CosineSimilarityMetric, EuclideanDistanceMetric, ManhattanDistanceMetric, NegativeRejectionRateMetric, PrecisionMetric, RankingConsistencyKendallTau, DiversityMetric, GeneralizedEmbeddingCoverageError, EmbeddingCosineSimilarityEvaluation, PairwiseCosineSimilarityVariance
from usage.linear_graph.metrics.impls import MyGenerationMetric, MyRetrievalMetric, MyE2EMetric, MyPostRetrievalMetric
from metrics.builtin.getMetrics import metric_class
from usage.linear_graph.modules.impls import AcceptorModule, MyRetrievalModule, MyGenerationModule
from adapters.api_adapter import api_adapter
import streamlit as st


class buildRag:
    def __init__(self):
        self.metric = None
        self.rag = None

    def load_metrics(self) -> dict:
        selected_metrics = st.session_state.get("selected_metrics", {})
        api_adapter_instance = api_adapter()
        #llm_adapter, embedding_adapter = api_adapter_instance.create_adapters()
        metric_instances = {}
        for module_name, metric_names in selected_metrics.items():
            metric_instances[module_name] = []
            for name in metric_names:
                cls = metric_class.get(name)
                if cls is not None:
                    metric_instances[module_name].append(cls())
                else:
                    raise ValueError(f"Metric '{name}' not found in registry")
        
        self.metric = metric_instances
        return metric_instances


    def buildRag(self) -> RAGContainer:
        metric_instances = self.load_metrics()

        RetrievalMetrics = metric_instances.get("Retriever Non-LLM Based Metric", [None]) + metric_instances.get("Retriever LLM Based Metric", [None])
        GenerationMetrics = metric_instances.get("Generator Non-LLM Based Metric", [None]) + metric_instances.get("Generator LLM Based Metric", [None])
        E2EMetrics = metric_instances.get("E2E Non-LLM Based Metric", [None]) + metric_instances.get("E2E LLM Based Metric", [None])

        rag = RAGContainer(
            u_fid='unique_flow_id',
            modules=[
                AcceptorModule('starter', metrics=None, is_starter=True),
                MyRetrievalModule(
                    'ret',
                    linker=Linker('starter'),
                    #metric=RetrievalMetrics[0]
                    metrics=RetrievalMetrics
                ),
                MyGenerationModule(
                    'gen',
                    linker=Linker('ret'),
                    metrics=GenerationMetrics
                ),
            ],
            e2e_metric=E2EMetrics
        )
        
        self.rag = rag
        return rag

"""
# 테스트용 임시 main
if __name__=="__main__":
    st.session_state["selected_metrics"] = {
        "Retriever Non-LLM Based Metric": ["KeywordMatchingMetric", "JaccardSimilarityMetric"],
        #"Retriever LLM Based Metric": ["RandomDocumentInjectionEffect"],
        "Generator Non-LLM Based Metric": ["AnswerContextSimilarity"],
        #"Generator LLM Based Metric": ["A2RYNFaithfulnessMetric"],
        "E2E Non-LLM Based Metric": ["AnswerQuerySimilarity"],
        #"E2E LLM Based Metric": ["E2EQGenRelevancyMetric"]
    }
    
    build=buildRag()
    test_rag=build.buildRag()

    # 테스트 쿼리 실행
    test_query = "What is machine learning?"
    
    # 결과 확인
    for module in test_rag.modules:
        if hasattr(module, '_BaseModule__metrics') and module.storage and module.storage.state.snapshots.get(module.module_id):
            latest_snapshot = module.storage.state.snapshots[module.module_id][-1]
            print(f"\nModule {module.module_id} metrics results:")
            for metric_name, [score, unit] in latest_snapshot.performances.items():
                print(f"{metric_name}: {score:.2f}{unit}")
"""
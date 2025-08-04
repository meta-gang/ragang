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
import streamlit as st


class buildRag:
    def __init__(self):
        self.metric = None
        self.rag = None

    def load_metrics(self) -> dict:
        selected_metrics = st.session_state.get("selected_metrics", {})
        
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
        
        rag = RAGContainer(
            u_fid='unique_flow_id',
            modules=[
                AcceptorModule('starter', metric=None, is_starter=True),
                MyRetrievalModule(
                    'ret',
                    linker=Linker('starter'),
                    metric=metric_instances.get("Retriever Non-LLM Based Metric", [None])[0]
                ),
                MyGenerationModule(
                    'gen',
                    linker=Linker('ret'),
                    metric=metric_instances.get("Generator Non-LLM Based Metric", [None])[0]
                ),
            ],
            e2e_metric=metric_instances.get("E2E Non-LLM Based Metric", [None])[0]
        )
        
        self.rag = rag
        return rag

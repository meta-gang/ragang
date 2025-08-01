from common.bases.datas.linker import Linker
from container import RAGContainer
from metrics.builtin.e2eMetric_LLMBased import E2ESYNRelevancyMetric, E2EScoringRelevancyMetric, E2EQGenRelevancyMetric
from metrics.builtin.e2eMetric_nonLLMBased import AnswerQuerySimilarity, e2eCosineConsistencyMetric, e2eCovarianceConsistencyMetric
from metrics.builtin.generatorMetric_LLMBased import A2RYNFaithfulnessMetric, A2RSimpleScoringFaithfulnessMetric, A2RHallucinationFaithfulnessMetric, A2RTruthfulFaithfulnessMetric, A2RYNFaithfulnessMetricSingleCall, A2RHybridFaithfulnessMetric
from metrics.builtin.generatorMetric_NonLLMBased import AnswerContextSimilarity, AnswerCentricSimilarityVariance, MutualInformation_KSG, RetrievalDeviationfromAnswer, RetrievaltopkMeanAnswerSimilarity
from metrics.builtin.retriever_LLMBased import RandomDocumentInjectionEffect
from metrics.builtin.retriever_NonLLMBased import KeywordMatchingMetric, JaccardSimilarityMetric, CosineSimilarityMetric, EuclideanDistanceMetric, ManhattanDistanceMetric, NegativeRejectionRateMetric, PrecisionMetric, RankingConsistencyKendallTau, DiversityMetric, GeneralizedEmbeddingCoverageError, EmbeddingCosineSimilarityEvaluation, PairwiseCosineSimilarityVariance
from metrics.builtin.getMetrics import metric_class
from usage.linear_graph.modules.impls import AcceptorModule, MyPreRetrievalModule, MyRetrievalModule, \
    MyPostRetrievalModule, MyGenerationModule
from usage.linear_graph.result_save import MetricVisualizer
import json
import os


def load_metrics(matric_savefile_path: str) -> dict:
    with open(matric_savefile_path, "r", encoding="utf-8") as f:
        metric_saved = json.load(f)

    with open(metric_saved, "r", encoding="utf-8") as f:
        metric_config = json.load(f)
    
    metric_instances = {}
    for module_name, metric_names in metric_config.items():
        metric_instances[module_name] = []
        for name in metric_names:
            cls = metric_class.get(name)
            if cls is not None:
                metric_instances[module_name].append(cls()) 
            else:
                raise ValueError(f"Metric '{name}' not found in registry")

    return metric_instances


def buildRag() -> RAGContainer:
    metric_config_path = "../../frontend/public/metric_config.json"
    metric_instances = load_metrics(metric_config_path)

    rag = RAGContainer(
        u_fid='unique_flow_id',
        modules=[
            AcceptorModule('starter', metric=None, is_starter=True),
            MyPreRetrievalModule(
                'pre',
                linker=Linker('starter'),
                metric=metric_instances.get("PreRetrieval", [None])[0]
            ),

            MyRetrievalModule(
                'ret',
                linker=Linker('pre'),
                metric=metric_instances.get("Retriever Non-LLM Based Metric", [None])[0]
            ),

            MyPostRetrievalModule(
                'post',
                linker=Linker('ret'),
                metric=None
            ),

            MyGenerationModule(
                'gen',
                linker=Linker('post'),
                metric=metric_instances.get("Generator Non-LLM Based Metric", [None])[0]
            ),
        ],
        e2e_metric=metric_instances.get("E2E LLM Based Metic", [None])[0]
    )

    return rag
from e2eMetric_LLMBased import E2ESYNRelevancyMetric, E2EScoringRelevancyMetric, E2EQGenRelevancyMetric
from e2eMetric_nonLLMBased import AnswerQuerySimilarity, e2eCosineConsistencyMetric, e2eCovarianceConsistencyMetric
from generatorMetric_LLMBased import A2RYNFaithfulnessMetric, A2RSimpleScoringFaithfulnessMetric, A2RHallucinationFaithfulnessMetric, A2RTruthfulFaithfulnessMetric, A2RYNFaithfulnessMetricSingleCall, A2RHybridFaithfulnessMetric
from generatorMetric_NonLLMBased import AnswerContextSimilarity, AnswerCentricSimilarityVariance, MutualInformation_KSG, RetrievalDeviationfromAnswer, RetrievaltopkMeanAnswerSimilarity
from retriever_LLMBased import RandomDocumentInjectionEffect
from retriever_NonLLMBased import KeywordMatchingMetric, JaccardSimilarityMetric, CosineSimilarityMetric, EuclideanDistanceMetric, ManhattanDistanceMetric, NegativeRejectionRateMetric, PrecisionMetric, RankingConsistencyKendallTau, DiversityMetric, GeneralizedEmbeddingCoverageError, EmbeddingCosineSimilarityEvaluation, PairwiseCosineSimilarityVariance

metric_class = {
    "E2ESYNRelevancyMetric": E2ESYNRelevancyMetric,
    "E2EScoringRelevancyMetric": E2EScoringRelevancyMetric,
    "E2EQGenRelevancyMetric": E2EQGenRelevancyMetric,
    "AnswerQuerySimilarity": AnswerQuerySimilarity,
    "e2eCosineConsistencyMetric": e2eCosineConsistencyMetric,
    "e2eCovarianceConsistencyMetric": e2eCovarianceConsistencyMetric,
    "A2RYNFaithfulnessMetric": A2RYNFaithfulnessMetric,
    "A2RSimpleScoringFaithfulnessMetric": A2RSimpleScoringFaithfulnessMetric,
    "A2RHallucinationFaithfulnessMetric": A2RHallucinationFaithfulnessMetric,
    "A2RTruthfulFaithfulnessMetric": A2RTruthfulFaithfulnessMetric,
    "A2RYNFaithfulnessMetricSingleCall": A2RYNFaithfulnessMetricSingleCall,
    "A2RHybridFaithfulnessMetric": A2RHybridFaithfulnessMetric,
    "AnswerContextSimilarity": AnswerContextSimilarity,
    "AnswerCentricSimilarityVariance": AnswerCentricSimilarityVariance,
    "MutualInformation_KSG": MutualInformation_KSG,
    "RetrievalDeviationfromAnswer": RetrievalDeviationfromAnswer,
    "RetrievaltopkMeanAnswerSimilarity": RetrievaltopkMeanAnswerSimilarity,
    "RandomDocumentInjectionEffect": RandomDocumentInjectionEffect,
    "KeywordMatchingMetric": KeywordMatchingMetric,
    "JaccardSimilarityMetric": JaccardSimilarityMetric,
    "CosineSimilarityMetric": CosineSimilarityMetric,
    "EuclideanDistanceMetric": EuclideanDistanceMetric,
    "ManhattanDistanceMetric": ManhattanDistanceMetric,
    "NegativeRejectionRateMetric": NegativeRejectionRateMetric,
    "PrecisionMetric": PrecisionMetric,
    "RankingConsistencyKendallTau": RankingConsistencyKendallTau,
    "DiversityMetric": DiversityMetric,
    "GeneralizedEmbeddingCoverageError": GeneralizedEmbeddingCoverageError,
    "EmbeddingCosineSimilarityEvaluation": EmbeddingCosineSimilarityEvaluation,
    "PairwiseCosineSimilarityVariance": PairwiseCosineSimilarityVariance
}
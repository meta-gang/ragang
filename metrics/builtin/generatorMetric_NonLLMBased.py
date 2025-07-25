import numpy as np
from common.bases.datas.performance_dataclass import Performance
from common.bases.abstracts.base_metric import BaseMetric
from adapters.embedding_adapter import BaseEmbeddingAdapter
from common.utils.tools import CosineSimilarity


"""
Answer Context Similarity (ACS)
답변과 Retrieval Chunk 간 평균 유사도
"""
class AnswerContextSimilarity(BaseMetric):
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        self.embedding_adapter = embedding_adapter

    def evaluate(self, context: list, gen: str) -> Performance:
        ans_vec = self.embedding_adapter.create_embedding([gen])[0]
        chunk_vecs = self.embedding_adapter.create_embedding(context)
        similarity = []
        for chunk_vec in chunk_vecs:
            sim = CosineSimilarity.compute(chunk_vec, ans_vec)
            similarity.append(abs(sim))
        acs_score = float(np.mean(similarity))
        return Performance(score=acs_score, unit='', metric='ACS')




"""
Answer Centric Similarity Variance (ACSV)
답변 기준 Retrieval의 각도 분산
"""
class AnswerCentricSimilarityVariance(BaseMetric):
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        self.embedding_adapter = embedding_adapter

    def evaluate(self, context: list, gen: str):
        ans_vec = self.embedding_adapter.create_embedding([gen])[0]
        chunk_vecs = self.embedding_adapter.create_embedding(context)
        angles = []
        for chunk_vec in chunk_vecs:
            cos_sim = CosineSimilarity.compute(chunk_vec, ans_vec)
            angle = np.arccos(np.clip(cos_sim, -1.0, 1.0))
            angles.append(angle)
        mean_angle = np.mean(angles)
        angle_variance = np.mean((np.array(angles) - mean_angle) ** 2)
        acsv_score = 1 - angle_variance
        return Performance(score=acsv_score, unit='', metric='ACSV')

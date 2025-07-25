import numpy as np
from common.bases.datas.performance_dataclass import Performance
from common.bases.abstracts.base_metric import BaseMetric
from adapters.embedding_adapter import BaseEmbeddingAdapter

"""
Cosine Similarity를 계산하기 위한 함수
"""
def cosine_similarity(vec1, vec2):
    vec1 = np.asarray(vec1)
    vec2 = np.asarray(vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))




"""
Name : Answer Query Similarity
Target : Answer-Query Similarity
Type: Non-LLM Metric, cosine-similarity, E2E Metric
Explanation: 생성된 답변과 Query 간 cosine 유사도를 계산
"""
class AnswerQuerySimilarity(BaseMetric):
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        self.embedding_adapter = embedding_adapter
    
    def evaluate(self, query: str, gen: str) -> Performance:
        embeddings = self.embedding_adapter.create_embedding([query, gen])
        query_vec, ans_vec = embeddings[0], embeddings[1]
        aqs_score = cosine_similarity(query_vec, ans_vec)
        return Performance(score=aqs_score, unit='', metric='AQS')
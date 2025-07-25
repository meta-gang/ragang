import numpy as np
from common.bases.datas.performance_dataclass import Performance
from common.bases.abstracts.base_metric import BaseMetric

"""
Cosine Similarity를 계산하기 위한 class
"""
class cosine_similarity:
    def __init__(self, vec1, vec2):
        self.vec1 = vec1
        self.vec2 = vec2
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return np.dot(vec1, vec2) / (norm1 * norm2)


"""
Name : Answer Query Similarity
Target : Answer-Query Similarity
Type: Non-LLM Metric, cosine-similarity, E2E Metric
Explanation: 생성된 답변과 Query 간 cosine 유사도를 계산
"""
class AnswerQuerySimilarity(BaseMetric):
    def __init__(self, data: list, ans: str, query: str, model):
        self.data = data
        self.ans = ans
        self.query = query
        self.EmvbeddingModel = model
    
    def evaluate(self, ip, op) -> Performance:
        quer_vec = self.EmvbeddingModel.encode([self.query])[0]
        ans_vec = self.EmvbeddingModel.encode([self.ans])[0]
        quer_vec = quer_vec.reshape(1, -1)
        ans_vec = ans_vec.reshape(1, -1)
        aqs_score = cosine_similarity(quer_vec, ans_vec)
        return Performance(score=aqs_score, unit='', metric='AQS')
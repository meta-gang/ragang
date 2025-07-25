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
Name : Answer Context Similarity
Target : Answer-Retreival Similarity
Type: Non-LLM Metric, cosine-similarity
Explanation: 생성된 답변과 Retrieval이 검색을 통해 선정한 Chunk들 간 cosine 유사도를 계산
"""
class AnswerContextSimilarity(BaseMetric):
    def __init__(self, data: list, ans: str, model):
        self.data = data
        self.ans = ans
        self.EmvbeddingModel = model

    def evaluate(self, ip, op) -> Performance:
        ans_vec = self.EmvbeddingModel.encode([self.ans])[0]
        ans_vec = ans_vec.reshape(1, -1)
        similarity = []
        for chunk in self.data:
            chunk_vec = self.EmvbeddingModel.encode([chunk])[0]
            sim = cosine_similarity(chunk_vec, ans_vec)
            similarity.append(np.abs(sim))
        acs_score = np.mean(similarity)
        return Performance(score=acs_score, unit='', metric='ACS')


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



"""
Name : Answer Centric Similarity Variance
Target : Answer-Retreival Variance
Type: Non-LLM Metric, cosine-similarity, Variance
Explanation: 생성된 답변과 Retrieval이 검색을 통해 선정한 Chunk들 간 cosine 유사도를 계산
계산된 유사도 간 분산을 통해 Anser기준 REtreival들의 분산 값을 구한다.
"""
class AnswerCentricSimilarityVariance(BaseMetric):
    def __init__(self, data: list, ans: str, model):
        self.data = data
        self.ans = ans
        self.EmbeddingModel = model
    
    def evaluate(self, ip, op):
        ans_vec = self.EmbeddingModel.encode([self.ans])[0]
        angles = []
        for chunk in self.data:
            cos_sim = cosine_similarity(chunk, ans_vec)
            angle = np.arccos(np.clip(cos_sim, -1.0, 1.0))
            angles.append(angle)
        mean_angle = np.mean(angles)
        angle_variance = np.mean((np.array(angles) - mean_angle) ** 2)
        acsv_score = 1 - angle_variance
        return Performance(score=acsv_score, unit='', metric='ACSV')


"""
Name : Pairwise Cosine Similarity Variance
Target : Retreival Variance
Type: Non-LLM Metric, cosine-similarity, Variance
Explanation: 모든 Retrieval간 각도를 cosine유사도를 통해 구하고 각도들의 분산을 통해 Retrieval의 응집도를 계산
"""
class PairwiseCosineSimilarityVariance(BaseMetric):
    def __init__(self, data: list, ans: str):
        self.data = data
        self.ans = ans
    
    def evaluate(self, ip, op) -> Performance:
        similarity = []
        for i in range(len(self.data)):
            for j in range(i+1, len(self.data)):
                sim = cosine_similarity(self.data[i], self.data[j])
                similarity.append(sim)
        mean = sum(similarity) / len(similarity)
        variance = sum((x - mean)**2 for x in similarity) / len(similarity)
        return Performance(score=variance, unit='', metric='PCSV')



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

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
Name : Pairwise Cosine Similarity Variance
Target : Retreival Variance
Type: Non-LLM Metric, cosine-similarity, Variance
Explanation: 모든 Retrieval간 각도를 cosine유사도를 통해 구하고 각도들의 분산을 통해 Retrieval의 응집도를 계산
"""
class PairwiseCosineSimilarityVariance(BaseMetric):
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        self.embedding_adapter = embedding_adapter

    def evaluate(self, context: list) -> Performance:
        embeddings = self.embedding_adapter.create_embedding(context)
        similarity = []
        for i in range(len(embeddings)):
            for j in range(i+1, len(embeddings)):
                sim = cosine_similarity(embeddings[i], embeddings[j])
                similarity.append(sim)
        mean = np.mean(similarity)
        variance = np.mean((np.array(similarity) - mean) ** 2)
        return Performance(score=variance, unit='', metric='PCSV')

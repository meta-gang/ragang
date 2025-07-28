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
        ans_vec = self.embedding_adapter.create_embeddings([gen])[0]
        chunk_vecs = self.embedding_adapter.create_embeddings(context)
        similarity = []
        for chunk_vec in chunk_vecs:
            sim = CosineSimilarity.compute(chunk_vec, ans_vec)
            similarity.append(abs(sim))
        acs_score = float(np.mean(similarity))
        return Performance(score=acs_score, unit="", metric="ACS")




"""
Answer Centric Similarity Variance (ACSV)
답변 기준 Retrieval의 각도 분산
"""
class AnswerCentricSimilarityVariance(BaseMetric):
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        self.embedding_adapter = embedding_adapter

    def evaluate(self, context: list, gen: str):
        ans_vec = self.embedding_adapter.create_embeddings([gen])[0]
        chunk_vecs = self.embedding_adapter.create_embeddings(context)
        angles = []
        for chunk_vec in chunk_vecs:
            cos_sim = CosineSimilarity.compute(chunk_vec, ans_vec)
            angle = np.arccos(np.clip(cos_sim, -1.0, 1.0))
            angles.append(angle)
        mean_angle = np.mean(angles)
        angle_variance = np.mean((np.array(angles) - mean_angle) ** 2)
        acsv_score = 1 - angle_variance
        return Performance(score=acsv_score, unit="", metric="ACSV")



"""
Mutual Information
생성된 답변과 Retrieval간 임베딩의 평균 유사도를 통해 정보량의 공유 정도를 측정
원래의 MI값은 확률분포를 구하기 위해 추가 import가 필요하여 KSG근사 방식 사용
"""
class MutualInformation_KSG(BaseMetric):
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter, k=3):
        self.embedding_adapter = embedding_adapter
        self.k = k

    def evaluate(self, context: list, generation: str) -> Performance:
        context_embeddings = self.embedding_adapter.create_embeddings(context)
        gen_embedding = self.embedding_adapter.create_embeddings([generation])[0]

        N = len(context_embeddings)
        if N == 0:
            return Performance(score=0.0, unit="", metric="MI_GC_KSG")

        joint_vectors = []
        for ctx_vec in context_embeddings:
            joint = np.concatenate([gen_embedding, ctx_vec])
            joint_vectors.append(joint)

        epsilons = []
        for i in range(N):
            distances = []
            for j in range(N):
                if i == j:
                    continue
                dist = np.max(np.abs(joint_vectors[i] - joint_vectors[j]))
                distances.append(dist)
            distances.sort()
            epsilons.append(distances[self.k - 1])

        n_x = []
        n_y = []
        for i in range(N):
            eps = epsilons[i]
            count_x = 0
            count_y = 0
            for j in range(N):
                if i == j:
                    continue
                dist_x = np.max(np.abs(gen_embedding - gen_embedding))
                dist_y = np.max(np.abs(context_embeddings[i] - context_embeddings[j]))
                if dist_x < eps:
                    count_x += 1
                if dist_y < eps:
                    count_y += 1
            n_x.append(count_x)
            n_y.append(count_y)

        log_k = np.log(self.k)
        log_N = np.log(N)
        avg_term = np.mean(np.log(np.array(n_x) + 1) + np.log(np.array(n_y) + 1))
        mi = log_k + log_N - avg_term

        return Performance(score=float(mi), unit="", metric="MI_GC_KSG")


"""
Retrieval Deviation from Answer
생성된 답변을 기준으로 Retrieval Embedding들이 얼마나 균일하게 가까운 방향으로 응집되어 있는지를 확인
백터 차이를 기반으로 분산 계산
"""
class RetrievalDeviationfromAnswer(BaseMetric):
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        self.embedding_adapter = embedding_adapter
    
    def evaluate(self, context: list, gen: str) -> Performance:
        chunk_vecs = self.embedding_adapter.create_embeddings(context)
        ans_vec = self.embedding_adapter.create_embeddings([gen])[0]

        chunk_vecs = chunk_vecs / np.linalg.norm(chunk_vecs, axis=1, keepdims=True)
        ans_vec = ans_vec / np.linalg.norm(ans_vec)

        diff_vecs = chunk_vecs - ans_vec

        mean_diff = np.mean(diff_vecs, axis=0)

        dispersion = np.mean(np.linalg.norm(diff_vecs - mean_diff, axis=1) ** 2)
        acd_score = 1 / (1 + dispersion)

        return Performance(score=acd_score, unit="", metric="ACD")

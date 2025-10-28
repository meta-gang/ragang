import numpy as np
from core.bases.datas.performance import Performance
from core.bases.abstracts.base_metric import BaseMetric
from core.utils.tools import CosineSimilarity
from adapters.llm_adapter import BaseLLMAdapter
from adapters.embedding_adapter import BaseEmbeddingAdapter


class BaseBuiltinMetric(BaseMetric):
    def __init__(self, param_src: list[str], llm_adapter: BaseLLMAdapter = None, embedding_adapter: BaseEmbeddingAdapter = None):
        super().__init__(param_src)
        self.llm_adapter = llm_adapter
        self.embedding_adapter = embedding_adapter


class AnswerContextSimilarity(BaseBuiltinMetric):
    """
    Average of cosine similarity between the generated answer and retrieval chunks

    :param embedding_adapter: The embedding model to use
    :type: BaseEmbeddingAdapter
    :ivar embedding_adapter: Stores the embedding model
    :vartype embedding_adapter: BaseEmbeddingAdapter
    """

    def evaluate(self, ret_docs: list[str], gen: str) -> Performance:
        """
        Compute average cosine similarity between embedded retrieval chunks and generator's answer

        :param ret_docs: retrieval chunks
        :type ret_docs: list[str]
        :param gen: Genrator's answer
        :type gen: str
        :returns: mean of cosine similarities between gen and each retrieval chunks
        :rtype: Performance
        """
        ans_vec = self.embedding_adapter.create_embeddings([gen])[0]
        chunk_vecs = self.embedding_adapter.create_embeddings(ret_docs)

        similarity = []
        for chunk_vec in chunk_vecs:
            sim = CosineSimilarity.compute(chunk_vec, ans_vec)
            similarity.append(abs(sim))

        acs_score = float(np.mean(similarity))

        return Performance(score=acs_score, unit="", metric="ACS")


class AnswerCentricSimilarityVariance(BaseBuiltinMetric):
    """
    Veriance of angles beteween embedded generator's answer and each retrieval chunks

    :param embedding_adapter: The embedding model to use
    :type embedding_adapter: BaseEmbeddingAdapter
    :ivar embedding_adapter: Stores the embedding model
    :vartype embedding_adapter: BaseEmbeddingAdapter
    """

    def evaluate(self, ret_docs: list[str], gen: str):
        """
        Compute veriance of angles between generator's answer and each retrieval chunks

        :param ret_docs: Retrieval text chunks
        :type ret_docs: list[str]
        :param gen: Generator's text answer
        :type gen: str
        :returns: Veriance of angles beteween gen_vec and each chunk_vecs
        :rtype: Performance
        """
        ans_vec = self.embedding_adapter.create_embeddings([gen])[0]
        chunk_vecs = self.embedding_adapter.create_embeddings(ret_docs)
        angles = []
        for chunk_vec in chunk_vecs:
            cos_sim = CosineSimilarity.compute(chunk_vec, ans_vec)
            angle = np.arccos(np.clip(cos_sim, -1.0, 1.0))
            angles.append(angle)
        mean_angle = np.mean(angles)
        angle_variance = np.mean((np.array(angles) - mean_angle) ** 2)
        acsv_score = 1 - angle_variance
        return Performance(score=acsv_score, unit="", metric="ACSV")


class MutualInformation_KSG(BaseBuiltinMetric):
    """
    Estimates mutual information between the generated answer and context using KSG estimator.

    :param embedding_adapter: The embedding model to use
    :type embedding_adapter: BaseEmbeddingAdapter
    :param k: Number of nearest neighbors
    :type k: int
    :ivar embedding_adapter: Stores the embedding model
    :vartype embedding_adapter: BaseEmbeddingAdapter
    :ivar k: Number of nearest neighbors used in the KSG estimation
    :vartype k: int
    """

    def __init__(self, embedding_adapter: BaseEmbeddingAdapter = None, llm_adapter: BaseLLMAdapter = None, k=3):
        super().__init__(llm_adapter, embedding_adapter)
        self.k = k

    def evaluate(self, ret_docs: list[str], generation: str) -> Performance:
        """
        Estimate how much mutual information exists between the generated answer and the retrieval context by measuring statistical dependency using the KSG(Kraskov Stögbauer Grassberger) method, which approximates mutual information based on neighbor distances in joint and marginal embedding spaces.

        :param ret_docs: Retrieval chunks
        :type ret_docs: list[str]
        :param generation: Generated answer
        :type generation: str
        :returns: Estimated mutual information score
        :rtype: Performance
        """
        context_embeddings = self.embedding_adapter.create_embeddings(ret_docs)
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


class RetrievalDeviationfromAnswer(BaseBuiltinMetric):
    """
    Measure how much the generated answer deviates from the retrieved context embeddings by computing the average embedding dispersion

    :param embedding_adapter: The embedding model to use
    :type embedding_adapter: BaseEmbeddingAdapter
    :ivar embedding_adapter: Stores the embedding model
    :vartype embedding_adapter: BaseEmbeddingAdapter
    """

    def evaluate(self, ret_docs: list[str], gen: str) -> Performance:
        """
        Compute how closely the retrieved context vectors align with the generated answer by computing the average deviation and dispersion of their embeddings, then converting this deviation into a bounded score using inverse scaling.

        :param ret_docs: Retrieval chunks
        :type ret_docs: list[str]
        :param gen: Generator's answer
        :type gen: str
        :returns: Inverse of dispersion score indicating deviation of answer from retrieval embeddings
        :rtype: Performance
        """
        chunk_vecs = self.embedding_adapter.create_embeddings(ret_docs)
        ans_vec = self.embedding_adapter.create_embeddings([gen])[0]

        chunk_vecs = chunk_vecs / np.linalg.norm(chunk_vecs, axis=1, keepdims=True)
        ans_vec = ans_vec / np.linalg.norm(ans_vec)

        diff_vecs = chunk_vecs - ans_vec

        mean_diff = np.mean(diff_vecs, axis=0)

        dispersion = np.mean(np.linalg.norm(diff_vecs - mean_diff, axis=1) ** 2)
        acd_score = 1 / (1 + dispersion)

        return Performance(score=acd_score, unit="", metric="RDA")


class RetrievaltopkMeanAnswerSimilarity(BaseBuiltinMetric):
    """
    Measure how well the generated answer aligns with the most relevant subset of retrieved chunks based on cosine similarity with the query, using dynamic top-k selection and centroid comparison

    :param embedding_adapter: The embedding model to use
    :type embedding_adapter: BaseEmbeddingAdapter
    :ivar embedding_adapter: Stores the embedding model
    :vartype embedding_adapter: BaseEmbeddingAdapter
    """

    def evaluate(self, ret_docs: list[str], gen: str, query: str):
        """
        Compute the similarity score by selecting top-k retrieved chunks based on query similarity drop-off, comparing centroids of the top-k and full set against the generated answer, and applying a sigmoid-based adjustment using z-score to account for uniformly relevant or noise-free retrievals.

        :param ret_docs: Retrieved chunks
        :type ret_docs: list[str]
        :param gen: Generator's answer
        :type gen: str
        :param query: User query
        :type query: str
        :returns: Adjusted similarity score emphasizing top-k retrieval relevance
        :rtype: Performance
        """
        chunk_vecs = self.embedding_adapter.create_embeddings(ret_docs)
        gen_vec = self.embedding_adapter.create_embeddings([gen])[0]
        query_vec = self.embedding_adapter.create_embeddings([query])[0]

        similarities = [CosineSimilarity.compute(query_vec, vec) for vec in chunk_vecs]

        sorted_indices = sorted(range(len(similarities)), key=lambda i: similarities[i], reverse=True)
        sorted_similarities = [similarities[i] for i in sorted_indices]

        drops = [sorted_similarities[i] - sorted_similarities[i + 1] for i in range(len(sorted_similarities) - 1)]
        drop_index = drops.index(max(drops)) + 1
        k = min(max(1, drop_index), len(chunk_vecs) - 1)

        topk_vecs = [chunk_vecs[sorted_indices[i]] for i in range(k)]
        topk_centroid = np.mean(topk_vecs, axis=0)
        r_centroid = np.mean(chunk_vecs, axis=0)

        cos_topk = max(CosineSimilarity.compute(gen_vec, topk_centroid), 0)
        cos_all = max(CosineSimilarity.compute(gen_vec, r_centroid), 0)
        base_score = 1 - (cos_all / (cos_topk + 1e-6))

        mean_sim = np.mean(similarities)
        std_sim = np.std(similarities) + 1e-6
        norm_sim = CosineSimilarity.compute(topk_centroid, r_centroid)
        z_score = (norm_sim - mean_sim) / std_sim
        adjustment_weight = 1 / (1 + np.exp(-z_score))

        final_score = base_score * adjustment_weight

        return Performance(score=final_score, unit="", metric="RMAS")

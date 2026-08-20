import numpy as np
from ragang.core.bases.datas.performance import Performance
from ragang.core.bases.abstracts.base_metric import BaseMetric
from ragang.core.utils.tools import CosineSimilarity
from ragang.adapters.llm_adapter import BaseLLMAdapter
from ragang.adapters.embedding_adapter import BaseEmbeddingAdapter

_EULER_MASCHERONI = 0.5772156649015329


def _digamma_int(n: int) -> float:
    """Digamma psi(n) for a positive integer n.

    The KSG estimator only ever evaluates psi at positive integers, where it has the
    closed form psi(n) = -gamma + sum_{m=1}^{n-1} 1/m. Computing it directly keeps the
    estimator free of any special-function library.
    """
    value = -_EULER_MASCHERONI
    for m in range(1, n):
        value += 1.0 / m
    return value


def _ksg_mutual_information(xs: list[float], ys: list[float], k: int) -> float:
    """KSG (Kraskov-Stoegbauer-Grassberger) estimator of I(X;Y) for paired 1-D samples.

        I(X;Y) = psi(k) + psi(N) - <psi(n_x + 1) + psi(n_y + 1)>

    For each sample i, eps_i is the distance to its k-th nearest neighbour in the joint
    space under the max-norm; n_x and n_y count the neighbours strictly inside eps_i
    along each marginal. Both lists must be the same length and paired by index.
    """
    n = len(xs)
    total = 0.0
    for i in range(n):
        dx = [abs(xs[i] - xs[j]) for j in range(n) if j != i]
        dy = [abs(ys[i] - ys[j]) for j in range(n) if j != i]
        eps = sorted(max(a, b) for a, b in zip(dx, dy))[k - 1]
        if eps == 0:
            # the k-th neighbour coincides with the sample (duplicate chunks). counting
            # nothing here would make such degenerate input score as maximal dependency,
            # so count the coincident points instead
            n_x = sum(1 for d in dx if d == 0)
            n_y = sum(1 for d in dy if d == 0)
        else:
            n_x = sum(1 for d in dx if d < eps)
            n_y = sum(1 for d in dy if d < eps)
        total += _digamma_int(n_x + 1) + _digamma_int(n_y + 1)
    return _digamma_int(k) + _digamma_int(n) - total / n


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
        ans_vecs = self.embedding_adapter.create_embeddings([gen])
        chunk_vecs = self.embedding_adapter.create_embeddings(ret_docs)
        if ans_vecs.size == 0 or chunk_vecs.size == 0:  # embedding api failed
            return Performance(unit="0 to 1", metric="ACS", _eval=False)
        ans_vec = ans_vecs[0]

        similarity = []
        for chunk_vec in chunk_vecs:
            sim = CosineSimilarity.compute(chunk_vec, ans_vec)
            similarity.append(abs(sim))

        acs_score = float(np.mean(similarity))

        return Performance(score=acs_score, unit="0 to 1", metric="ACS")


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
        ans_vecs = self.embedding_adapter.create_embeddings([gen])
        chunk_vecs = self.embedding_adapter.create_embeddings(ret_docs)
        if ans_vecs.size == 0 or chunk_vecs.size == 0:  # embedding api failed
            return Performance(unit="1 - angle variance", metric="ACSV", _eval=False)
        ans_vec = ans_vecs[0]
        angles = []
        for chunk_vec in chunk_vecs:
            cos_sim = CosineSimilarity.compute(chunk_vec, ans_vec)
            angle = np.arccos(np.clip(cos_sim, -1.0, 1.0))
            angles.append(angle)
        mean_angle = np.mean(angles)
        angle_variance = np.mean((np.array(angles) - mean_angle) ** 2)
        acsv_score = 1 - angle_variance
        return Performance(score=acsv_score, unit="1 - angle variance", metric="ACSV")


class MutualInformation_KSG(BaseBuiltinMetric):
    """
    Estimates the mutual information between how much the answer reflects each retrieved
    chunk and how relevant that chunk is to the query, using the KSG estimator.

    One paired sample is taken per retrieved chunk:

    - ``x_i = cos(generation, chunk_i)`` -- how much the answer reflects that chunk
    - ``y_i = cos(query, chunk_i)``      -- how relevant that chunk is to the query

    A high score means the generator drew on chunks in proportion to their relevance to
    the query. A low score means the answer's content is unrelated to which chunks were
    actually relevant, which is a hallucination signal.

    .. note:: The sample size equals the number of retrieved chunks, so the estimate is
        high-variance at small ``top_k``. Raise ``top_k`` for a more stable reading.

    :param embedding_adapter: The embedding model to use
    :type embedding_adapter: BaseEmbeddingAdapter
    :param k: Number of nearest neighbors. Shrunk automatically when fewer chunks are retrieved.
    :type k: int
    :ivar embedding_adapter: Stores the embedding model
    :vartype embedding_adapter: BaseEmbeddingAdapter
    :ivar k: Number of nearest neighbors used in the KSG estimation
    :vartype k: int
    """

    def __init__(self, param_src: list[str], embedding_adapter: BaseEmbeddingAdapter = None, llm_adapter: BaseLLMAdapter = None, k=3):
        super().__init__(param_src, llm_adapter, embedding_adapter)
        self.k = k

    def evaluate(self, ret_docs: list[str], generation: str, query: str) -> Performance:
        """
        Estimate the statistical dependency between the answer's use of each retrieved chunk
        and that chunk's relevance to the query, using the KSG(Kraskov Stoegbauer Grassberger)
        method over one paired sample per chunk.

        :param ret_docs: Retrieval chunks
        :type ret_docs: list[str]
        :param generation: Generated answer
        :type generation: str
        :param query: User query
        :type query: str
        :returns: Estimated mutual information score
        :rtype: Performance
        """
        chunk_vecs = self.embedding_adapter.create_embeddings(ret_docs)
        gen_vecs = self.embedding_adapter.create_embeddings([generation])
        query_vecs = self.embedding_adapter.create_embeddings([query])
        if chunk_vecs.size == 0 or gen_vecs.size == 0 or query_vecs.size == 0:  # embedding api failed
            return Performance(unit="nats", metric="MI_GC_KSG", _eval=False)

        n = len(chunk_vecs)
        # each point has n-1 neighbours, so k cannot exceed that. shrink k to whatever the
        # retrieved set allows rather than refusing to evaluate
        k_eff = min(self.k, n - 1)
        if k_eff < 1:  # a single chunk has no neighbour to measure against
            return Performance(unit="nats", metric="MI_GC_KSG", _eval=False)

        gen_vec, query_vec = gen_vecs[0], query_vecs[0]
        # one paired sample per chunk: (how much the answer reflects it, how relevant it is)
        xs = [CosineSimilarity.compute(gen_vec, vec) for vec in chunk_vecs]
        ys = [CosineSimilarity.compute(query_vec, vec) for vec in chunk_vecs]

        mi = _ksg_mutual_information(xs, ys, k_eff)
        # mutual information is non-negative; the estimator can dip below zero on small samples
        return Performance(score=max(float(mi), 0.0), unit="nats", metric="MI_GC_KSG")


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
        ans_vecs = self.embedding_adapter.create_embeddings([gen])
        if chunk_vecs.size == 0 or ans_vecs.size == 0:  # embedding api failed
            return Performance(unit="0 to 1", metric="RDA", _eval=False)
        ans_vec = ans_vecs[0]

        chunk_vecs = chunk_vecs / np.linalg.norm(chunk_vecs, axis=1, keepdims=True)
        ans_vec = ans_vec / np.linalg.norm(ans_vec)

        diff_vecs = chunk_vecs - ans_vec

        mean_diff = np.mean(diff_vecs, axis=0)

        dispersion = np.mean(np.linalg.norm(diff_vecs - mean_diff, axis=1) ** 2)
        acd_score = 1 / (1 + dispersion)

        return Performance(score=acd_score, unit="0 to 1", metric="RDA")


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
        gen_vecs = self.embedding_adapter.create_embeddings([gen])
        query_vecs = self.embedding_adapter.create_embeddings([query])
        if chunk_vecs.size == 0 or gen_vecs.size == 0 or query_vecs.size == 0:  # embedding api failed
            return Performance(unit="heuristic score", metric="RMAS", _eval=False)
        if len(chunk_vecs) < 2:  # top-k split needs at least two chunks to compare
            return Performance(unit="heuristic score", metric="RMAS", _eval=False)
        gen_vec = gen_vecs[0]
        query_vec = query_vecs[0]

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

        return Performance(score=final_score, unit="heuristic score", metric="RMAS")

import numpy as np
from ragang.core.bases.datas.performance import Performance
from ragang.core.bases.abstracts.base_metric import BaseMetric
from ragang.adapters.llm_adapter import BaseLLMAdapter
from ragang.adapters.embedding_adapter import BaseEmbeddingAdapter
from ragang.core.utils.tools import CosineSimilarity
from sklearn.metrics.pairwise import cosine_similarity


class BaseBuiltinMetric(BaseMetric):
    def __init__(self, param_src: list[str], llm_adapter: BaseLLMAdapter = None, embedding_adapter: BaseEmbeddingAdapter = None):
        super().__init__(param_src)
        self.llm_adapter = llm_adapter
        self.embedding_adapter = embedding_adapter


class AnswerQuerySimilarity(BaseBuiltinMetric):
    """
    Cosine similarity between the genrated anser and user

    :param embedding_adapter: The embedding model to use
    :type: BaseEmbeddingAdapter
    :ivar embedding_adapter: Stores the embedding model
    :vartype embedding_adapter: BaseEmbeddingAdapter
    """

    def evaluate(self, query: str = None, gen: str = None) -> Performance:
        """
        Compute cosine similarity between the embedded genrated anser and user query

        :param query: User query
        :type query: str
        :param gen: Genrateor's answer
        :type gen: str
        :returns: Cosine similarity between query_vec and ans_vec
        :rtype: Performance
        """
        embeddings = self.embedding_adapter.create_embeddings([query, gen])
        if len(embeddings) < 2:  # embedding api failed
            return Performance(unit="-1 to 1", metric="AQS", _eval=False)
        query_vec, ans_vec = embeddings[0], embeddings[1]

        aqs_score = CosineSimilarity.compute(query_vec, ans_vec)

        return Performance(score=aqs_score, unit="-1 to 1", metric="AQS")


class e2eCosineConsistencyMetric(BaseBuiltinMetric):
    """
    End to end consistency metric via mean cosine-similarity.

    :param embedding_adapter: The embedding model to use
    :type embedding_adapter: BaseEmbeddingAdapter
    :ivar embedding_adapter: Stores the embedding model to use
    :vartype embedding_adapter: BaseEmbeddingAdapter
    """

    def evaluate(self, query: str = None, gens: list[str] = None) -> Performance:
        """
        Calculates the mean cosine similarity between each pair of generated answers.

        :param gens: list of generated answers
        :type gens: list[str]
        :returns: Performance object with the mean cosine similarity score
        :rtype: Performance
        """
        # the engine passes a single generated answer (str); consistency needs several
        if isinstance(gens, str):
            gens = [gens]
        if not gens or len(gens) < 2:
            return Performance(unit="-1 to 1", metric="E2E Consistency", _eval=False)

        try:
            gen_vectors = self.embedding_adapter.create_embeddings(gens)
            if len(gen_vectors) < 2:  # embedding api failed
                return Performance(unit="-1 to 1", metric="E2E Consistency", _eval=False)
            similarity_matrix = cosine_similarity(gen_vectors)

            num_gens = len(gens)
            indices = np.triu_indices(num_gens, k=1)
            total_cos = np.sum(similarity_matrix[indices])
            num_pairs = len(indices[0])

            if num_pairs == 0:
                return Performance(score=1.0, unit="-1 to 1", metric="E2E Consistency")

            score = total_cos / num_pairs
        except Exception as exc:
            return Performance(
                unit="-1 to 1",
                metric="E2E Consistency",
                _eval=False,
                failure={
                    "type": type(exc).__name__,
                    "message": "Consistency calculation failed.",
                },
            )

        return Performance(score=float(score), unit="-1 to 1", metric="E2E Consistency")


class e2eCovarianceConsistencyMetric(BaseBuiltinMetric):
    """
    End to end consistency metric via variance of cosine-similarity.

    :param embedding_adapter: The embedding model to use
    :type embedding_adapter: BaseEmbeddingAdapter
    :ivar embedding_adapter: Stores the embedding model to use
    :vartype embedding_adapter: BaseEmbeddingAdapter
    """

    def evaluate(self, query: str = None, gens: list[str] = None) -> Performance:
        """
        Calculates the variance of cosine similarities between the query and each generated answer.

        :param query: input query string
        :type query: str
        :param gens: list of generated answers
        :type gens: list[str]
        :returns: Performance object with the variance of cosine similarities
        :rtype: Performance
        """
        # the engine passes a single generated answer (str); variance needs several
        if isinstance(gens, str):
            gens = [gens]
        if not gens or len(gens) < 2:
            return Performance(unit="variance", metric="E2E Query-Answer Consistency Variance", _eval=False)

        try:
            all_texts = [query] + gens
            embeddings = self.embedding_adapter.create_embeddings(all_texts)
            if len(embeddings) != len(all_texts):  # embedding api failed
                return Performance(unit="variance", metric="E2E Query-Answer Consistency Variance", _eval=False)

            query_vector = embeddings[0:1]
            gen_vectors = embeddings[1:]

            if gen_vectors.shape[0] == 0:
                return Performance(
                    unit="variance",
                    metric="E2E Query-Answer Consistency Variance",
                    _eval=False,
                )

            cos_sims = cosine_similarity(query_vector, gen_vectors)[0]
            consistency_score = float(np.var(cos_sims))
        except Exception as exc:
            return Performance(
                unit="variance",
                metric="E2E Query-Answer Consistency Variance",
                _eval=False,
                failure={
                    "type": type(exc).__name__,
                    "message": "Consistency variance calculation failed.",
                },
            )

        return Performance(score=consistency_score, unit="variance", metric="E2E Query-Answer Consistency Variance")

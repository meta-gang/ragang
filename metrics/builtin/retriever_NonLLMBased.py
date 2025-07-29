import numpy as np
from common.bases.datas.performance_dataclass import Performance
from common.bases.abstracts.base_metric import BaseMetric
from adapters.embedding_adapter import BaseEmbeddingAdapter
from common.utils.tools import CosineSimilarity



class PairwiseCosineSimilarityVariance(BaseMetric):
    """
    Evaluate the semantic diversity of retrieval chunks by measuring the variance of pairwise cosine similarities
    
    :param embedding_adapter: The embedding model to use
    :type embedding_adapter: BaseEmbeddingAdapter
    :ivar embedding_adapter: Stores the embedding model
    :vartype embedding_adapter: BaseEmbeddingAdapter
    """

    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        self.embedding_adapter = embedding_adapter

    def evaluate(self, context: list) -> Performance:
        """
        Compute the semantic diversity among retrieval chunks by computing the variance of pairwise cosine similarities between their embeddings.
        
        :param context: Retrieved chunks
        :type context: list[str]
        :returns: Variance score of pairwise cosine similarities indicating semantic spread
        :rtype: Performance
        """
        embeddings = self.embedding_adapter.create_embeddings(context)
        similarity = []
        for i in range(len(embeddings)):
            for j in range(i+1, len(embeddings)):
                sim = CosineSimilarity.compute(embeddings[i], embeddings[j])
                similarity.append(sim)
        mean = np.mean(similarity)
        variance = np.mean((np.array(similarity) - mean) ** 2)
        return Performance(score=variance, unit="", metric="PCSV")

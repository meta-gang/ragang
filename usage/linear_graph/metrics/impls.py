from common.bases.abstracts.base_metric import BaseMetric
from common.bases.datas.performance_dataclass import Performance


class MyPreRetrievalMetric(BaseMetric):
    def evaluate(self, query: str) -> Performance:
        return Performance(score=100, unit='%', metric='Accuracy')


class MyRetrievalMetric(BaseMetric):
    def evaluate(self, context: list[str]) -> Performance:
        return Performance(score=0.6, unit='', metric='f1')


class MyPostRetrievalMetric(BaseMetric):
    def evaluate(self, context: list[str]) -> Performance:
        return Performance(score=0.8, unit='', metric='Cosine Similarity')


class MyGenerationMetric(BaseMetric):
    def __init__(self, llm_adaptor: object):
        self.llm_adaptor = llm_adaptor

    def evaluate(self, answer: str) -> Performance:
        return Performance(score=100, unit='', metric='LLMBased')


class MyE2EMetric(BaseMetric):
    def evaluate(self, *args, **kwargs) -> Performance:
        return Performance(score=85, unit='%', metric='Accuracy')

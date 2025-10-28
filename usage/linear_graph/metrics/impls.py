from core.bases.abstracts.base_metric import BaseMetric
from core.bases.datas.performance import Performance


class MyPreRetrievalMetric(BaseMetric):
    def __init__(self, param_refs: list[str]):
        super().__init__(param_refs)

    def evaluate(self, query: str) -> Performance:
        return Performance(score=100, unit='%', metric='Accuracy')


class MyRetrievalMetric(BaseMetric):
    def __init__(self, param_refs: list[str]):
        super().__init__(param_refs)

    def evaluate(self, context: list[str]) -> Performance:
        return Performance(score=0.6, unit='', metric='f1')


class MyPostRetrievalMetric(BaseMetric):
    def __init__(self, param_refs: list[str]):
        super().__init__(param_refs)

    def evaluate(self, context: list[str]) -> Performance:
        return Performance(score=0.8, unit='', metric='Cosine Similarity')


class MyGenerationMetric(BaseMetric):
    def __init__(self, param_src: list[str], llm_adaptor: object):
        super().__init__(param_src)
        self.llm_adaptor = llm_adaptor

    def evaluate(self, gen: str) -> Performance:
        return Performance(score=100, unit='', metric='LLMBased')


class MyE2EMetric(BaseMetric):
    def __init__(self, param_refs: list[str]):
        super().__init__(param_refs)

    def evaluate(self, *args, **kwargs) -> Performance:
        return Performance(score=85, unit='%', metric='Accuracy')

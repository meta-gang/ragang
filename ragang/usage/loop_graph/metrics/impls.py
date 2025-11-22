from ragang.core.bases.abstracts.base_metric import BaseMetric
from ragang.core.bases.datas.performance import Performance


class MyRetrievalMetric(BaseMetric):
    def __init__(self, param_src: list[str]):
        super().__init__(param_src)

    def evaluate(self, context: list[str]) -> Performance:
        return Performance(score=0.6, unit='', metric='f1')


class MyPostRetrievalMetric(BaseMetric):
    def __init__(self, param_src: list[str]):
        super().__init__(param_src)

    def evaluate(self, retrieved: list[str]) -> Performance:
        return Performance(score=0.8, unit='', metric='cosim')

class MySecondPostRetrievalMetric(BaseMetric):
    def __init__(self, param_src: list[str]):
        super().__init__(param_src)

    def evaluate(self, ret_docs: list[str]) -> Performance:
        return Performance(score=0.2, unit='', metric='std')

class MyGenerationMetric(BaseMetric):
    def __init__(self, param_src: list[str], llm_adaptor: object):
        super().__init__(param_src)
        self.llm_adaptor = llm_adaptor

    def evaluate(self, gen: str) -> Performance:
        return Performance(score=100, unit='', metric='LLMBased')


class MyE2EMetric(BaseMetric):
    def __init__(self, param_src: list[str]):
        super().__init__(param_src)

    def evaluate(self, *args, **kwargs) -> Performance:
        return Performance(score=85, unit='%', metric='Accuracy')

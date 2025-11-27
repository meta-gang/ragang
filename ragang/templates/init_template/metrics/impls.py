from ragang.core.bases.abstracts.base_metric import BaseMetric
from ragang.core.bases.datas.performance import Performance


class MySampleMetric(BaseMetric):
    def __init__(self, param_src: list[str]):
        super().__init__(param_src)

    def evaluate(self, context: list[str]) -> Performance:
        return Performance(score=0.6, unit='', metric='f1')
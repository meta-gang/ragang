from common.bases.datas.performance_dataclass import Performance
from metrics.custom import CustomMetric


class MyAccuracyMetric(CustomMetric):
    def evaluate(self, ip, op) -> Performance:
        return Performance(score=100, unit='%', metric='Accuracy')

class MyF1ScoreMetric(CustomMetric):
    def evaluate(self, ip, op) -> Performance:
        return Performance(score=1, unit='', metric='F1Score')
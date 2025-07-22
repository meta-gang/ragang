from common.bases.datas.performance_dataclass import Performance
from metrics.custom import CustomMetric


class MyAccuracyMetric(CustomMetric):
    def evaluate(self, ip, op) -> Performance:
        return Performance(score=100, unit='%', metric='Accuracy')

class MyF1ScoreMetric(CustomMetric):
    def evaluate(self, ip, op) -> Performance:
        return Performance(score=1, unit='', metric='F1Score')

class MyLLMAsAJudgeMetric(CustomMetric):
    def __init__(self, llm_adaptor):
        self.llm_adaptor = llm_adaptor

    def evaluate(self, query: str, gen: str) -> Performance:
        """
        그 클래스에 LLM api, credentials 등을 받아 저장하도록 인터페이스를 포함하고
        request() 등의 메서드를 만들어 프롬프트나 쿼리를 보내 원하는 작업을 수행할 수 있는 형태로
        LLMAdaptor 클래스를 구현해두고,
        여기서 또 가져와서 llm as a judge 에 활용이 가능하도록 pre-built metric을 구성해도 될 것 같음
        예를 들어 아래와 같이 llm_adaptor를 이용
        return llm_adaptor.request(prompt="쿼리와 해당 쿼리에 대한 응답을 줄테니 그 응답이 쿼리의 의도에 맞는 답변인지 0~1 사이의 float 값만 대답", query=f"query: {query}, answer: {gen}")
        """
        return Performance(score=1, unit='', metric='LLM as a judge')
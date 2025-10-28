from core.bases.abstracts.base_metric import BaseMetric


class CustomMetric(BaseMetric):
    # 우리의 프레임워크가 정해둔 틀 안에서 자유롭세 스스로 custom metric을 만들어 사용할 수 있도록
    def __init__(self, param_src: list[str]):
        super().__init__(param_src)

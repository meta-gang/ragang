from common.bases.abstracts.base_module import BaseModule
from common.bases.abstracts.base_metric import BaseMetric
from common.bases.datas.performance_dataclass import Performance
from common.utils.ansi_styler import ANSIStyler


class LinearRagContainer:
    def __init__(self, modules: list[BaseModule], e2e_metric: BaseMetric = None):
        self.__head_module: BaseModule = self.__connect_modules(modules)
        self.__metric: BaseMetric | None = e2e_metric
        self.performance: Performance | None = None
        """
        modules: list[BaseModule]
        connections: dict[str | int, list[str | int]]
        이렇게 받아서 module 들을 가져와 connection 을 기반으로 연결을 만들고, 연결 구조도 저장 해두고 써 먹을까
        str 로 들어올 거라면 각 모듈을 정의할 때 만들어 둔 모듈 이름이 되어야 함
        기존 >> 을 이용해 정의 되던 연결 구조를 +(>>) 를 이용해 각 모듈에서 연결 되는 인접 모듈들을 추가, -(<<) 를 이용해 모듈 연결 제거도 가능 하도록
        이런 그래프 구조로 만들어 두면 따로 process control module 을 정하지 않아도 될 것으로 보임
        다만 이런 구조 라고 하면 각 모듈의 output 이 destination module 을 명시해 특정 데이터를 전달 하는 형태로 구성 되어야 할 듯
        """

    def __connect_modules(self, modules: list[BaseModule]) -> BaseModule:
        # return first module
        for i in range(len(modules) - 1):
            modules[i] = modules[i] >> modules[i + 1]
        return modules[0]

    def run(self, query: str) -> str:
        result = self.__head_module._BaseModule__execute(query)  # private method 강제 호출보단 다른 방식으로 접근하는 방식 고안
        if self.__metric:
            self.performance = self.__metric.evaluate(query, result)
        else:
            self.performance = Performance(_eval=False)
        return result

    def print_eval(self):
        piv: BaseModule = self.__head_module
        while piv:
            print(ANSIStyler.style(f"{piv.__class__.__name__}", fore_color='yellow'))
            print(ANSIStyler.style(f"\t{piv.performance}", fore_color='blue'))
            piv = piv._BaseModule__next_module  # private method 강제 호출보단 다른 방식으로 접근하는 방식 고안

        print(ANSIStyler.style(f"End to End RAG performance", fore_color='light-yellow', font_style='bold'))
        print(ANSIStyler.style(f"\t{self.performance}", fore_color='light-blue'))

    def show(self):
        # TODO: after GUI design
        pass

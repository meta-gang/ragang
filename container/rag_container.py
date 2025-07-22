from common.bases.abstracts.base_module import BaseModule
from common.bases.abstracts.base_metric import BaseMetric
from common.bases.datas.performance_dataclass import Performance
from common.utils.ansi_styler import ANSIStyler


class LinearRagContainer:
    def __init__(self, modules: list[BaseModule], e2e_metric: BaseMetric = None):
        self.__head_module: BaseModule = self.__connect_modules(modules)
        self.__metric: BaseMetric | None = e2e_metric
        self.performance: Performance | None = None

    def __connect_modules(self, modules: list[BaseModule]) -> BaseModule:
        # return first module
        for i in range(len(modules) - 1):
            modules[i] = modules[i] >> modules[i + 1]
        return modules[0]

    def run(self, query: str) -> str:
        result = self.__head_module._BaseModule__execute(query)
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
            piv = piv._BaseModule__next_module

        print(ANSIStyler.style(f"End to End RAG performance", fore_color='light-yellow', font_style='bold'))
        print(ANSIStyler.style(f"\t{self.performance}", fore_color='light-blue'))

    def show(self):
        # TODO: after GUI design
        pass

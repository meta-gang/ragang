from functools import reduce

from common.bases.abstracts.base_module import BaseModule


class LinearRagContainer:
    def __init__(self, modules: list[BaseModule]):
        self.__head_module: BaseModule = self.__connect_modules(modules)

    def __connect_modules(self, modules: list[BaseModule]) -> BaseModule:
        # return first module
        for i in range(len(modules) - 1):
            modules[i] = modules[i] >> modules[i + 1]
        return modules[0]

    def run(self, query: str) -> str:
        return self.__head_module._BaseModule__execute(query)

    def print_eval(self):
        piv: BaseModule = self.__head_module
        while piv:
            print(f"{piv.__class__.__name__}\n\t{piv.performance}")
            piv = piv._BaseModule__next_module

    def show(self):
        # TODO: after GUI design
        pass

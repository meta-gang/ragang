from abc import ABCMeta, abstractmethod

from common.bases.abstracts.base_metric import BaseMetric
from common.bases.abstracts.base_module import BaseModule
from common.bases.datas.flow_storage import FlowStorage
from common.bases.datas.performance_dataclass import Performance
from exceptions.frameworks.modules import DuplicateModuleIdException, FlowOutputException, \
    MultipleStarterModuleException
from common.utils.ansi_styler import ANSIStyler


class BaseContainer(metaclass=ABCMeta):
    def __init__(self, u_fid: str, modules: list[BaseModule], e2e_metric: BaseMetric = None):
        self.modules: list[BaseModule] = self.__validate_module_id(modules)
        self.starter: BaseModule | None = None
        self.__metric: BaseMetric | None = e2e_metric
        self.storage: FlowStorage = FlowStorage(u_fid)
        self.__connect_dependencies()

    def __validate_module_id(self, modules: list[BaseModule]) -> list[BaseModule]:
        ids: list[str] = [module.module_id for module in modules]
        u_ids: set[str] = set(ids)
        if len(ids) != len(u_ids):
            duplicate_ids: set[str] = u_ids.difference(set(ids))
            raise DuplicateModuleIdException(duplicate_ids)
        return modules

    def __connect_dependencies(self):
        for module in self.modules:
            self.storage.subscription[module.module_id] = []  # init subscription
            module.storage = self.storage  # inject dependency
            self.__set_starter_module(module)  # set flow starter
            for dep_mid in module.dependency.get_dependent_mids():
                self.storage.subscribe(module, dep_mid)

    def __set_starter_module(self, module: BaseModule):
        if module.is_starter:
            if self.starter is not None:
                raise MultipleStarterModuleException(self.starter.module_id, module.module_id)
            self.starter = module

    def invoke_batch(self, queries: list[str]) -> list[tuple[str, str]]:
        answers: list[tuple[str, str]] = []
        for idx, query in enumerate(queries):
            answers.append((query, self.invoke(query, idx)))
        return answers

    def invoke(self, query: str, query_id: int = 0) -> str:
        self.storage.construct(query_id, query)
        self.starter.trigger_chain_execution(query)
        answer: str = self.storage.state.answer
        if answer is None:
            raise FlowOutputException()

        if self.__metric is None:
            performance: Performance = Performance(_eval=False)
        else:
            performance: Performance = self.__metric.evaluate(query=query, gen=answer)
        self.storage.destruct(performance)
        return answer

    def print_eval(self):
        for query_idx, state in self.storage.history.items():
            tot_x_time: float = 0  # ms
            print()
            print(ANSIStyler.style(f'Query: {state.query}', font_style='bold', fore_color='light-green'))  # query
            print(ANSIStyler.style(f"Answer: {state.answer}", font_style='bold', fore_color='light-green'))  # answer

            for mid, packet_list in state.snapshots.items():  # print by packets
                print(ANSIStyler.style(f"\t'{mid}' Performance:", font_style='normal', fore_color='blue'))
                for packet in packet_list:  # TODO: update after multi metric usage available
                    x_time = packet.x_time * 1000
                    print(ANSIStyler.style(f"\t\t{packet.performance} ({x_time:.4f}ms)", font_style='normal', fore_color='yellow'))
                    tot_x_time += x_time

            print(ANSIStyler.style(f"E2E Performance:", font_style='bold', fore_color='light-blue'))
            print(ANSIStyler.style(f"\t{state.performance} ({tot_x_time:.4f}ms)", font_style='bold', fore_color='light-yellow'))

    @abstractmethod
    def show(self):
        raise NotImplementedError(f"Please implement '{self.__class__.__name__}.show()'")

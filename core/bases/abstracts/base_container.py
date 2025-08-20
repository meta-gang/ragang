import re
from abc import ABCMeta, abstractmethod

from core.bases.abstracts.base_metric import BaseMetric
from core.bases.abstracts.base_module import BaseModule
from core.bases.datas.flow_storage import FlowStorage
from core.bases.datas.performance import Performance
from exceptions.frameworks.modules import DuplicateModuleIdException, FlowOutputException, \
    MultipleStarterModuleException, InvalidModuleIdException
from core.utils.ansi_styler import ANSIStyler


class BaseContainer(metaclass=ABCMeta):
    def __init__(self, u_fid: str, modules: list[BaseModule], e2e_metrics: list[BaseMetric] = None):
        self.modules: list[BaseModule] = self.__validate_module_id(modules)
        self.starter: BaseModule | None = None
        self.__metrics: list[BaseMetric] | None = e2e_metrics
        self.storage: FlowStorage = FlowStorage(u_fid)
        self.__connect_dependencies()

    def __validate_module_id(self, modules: list[BaseModule]) -> list[BaseModule]:
        ids: list[str] = []
        for module in modules:  # check id format
            if re.fullmatch(r'^[A-Za-z0-9_]+$', module.module_id) is None:  # only allows alphabet, number, underscore
                raise InvalidModuleIdException(module.module_id,
                                               "Only combination of alphabets, numbers, and underscores are allowed.")
            if module.module_id in ['gen', 'metric']:
                raise InvalidModuleIdException(module.module_id,
                                               "'gen', 'metric' are reserved. Use the other one instead.")
            ids.append(module.module_id)
        u_ids: set[str] = set(ids)

        if len(ids) != len(u_ids):  # check dup
            duplicate_ids: set[str] = u_ids.difference(set(ids))
            raise DuplicateModuleIdException(duplicate_ids)
        return modules

    def __connect_dependencies(self):
        for module in self.modules:  # initialization
            self.storage.subscription[module.module_id] = []  # init subscription
            module.storage = self.storage  # inject dependency
            self.__set_starter_module(module)  # set flow starter

        for module in self.modules:
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
        gen: str = self.storage.state.gen
        if gen is None:
            raise FlowOutputException()

        if self.__metrics is None:
            performances: list[Performance] = [Performance(_eval=False)]
        else:
            # parameters for the e2e metrics' evaluate() are limited to 'query' and 'gen'
            performances: list[Performance] = [metric.evaluate(query=query, gen=gen) for metric in self.__metrics]
        self.storage.destruct(performances)
        return gen

    def print_eval(self):
        for query_idx, state in self.storage.history.items():
            tot_x_time: float = 0  # ms
            print()
            print(ANSIStyler.style(f'Query: {state.query}', font_style='bold', fore_color='light-green'))  # query
            print(ANSIStyler.style(f"Generated Answer: {state.gen}", font_style='bold',
                                   fore_color='light-green'))  # answer

            for mid, packet_list in state.snapshots.items():  # per modules
                print(ANSIStyler.style(f"\t'{mid}' Performances:", font_style='normal', fore_color='blue'))
                for idx, packet in enumerate(packet_list):  # per executions (for loop graph or sth)
                    x_time = packet.x_time * 1000
                    print(ANSIStyler.style(f"\t\texecution {idx} ({x_time:.4f}ms)", font_style='normal',
                                           fore_color='yellow'))
                    for perf in packet.performances:  # per metrics
                        print(ANSIStyler.style(f"\t\t\t{perf}", font_style='normal',
                                               fore_color='yellow'))
                    tot_x_time += x_time

            print(ANSIStyler.style(f"E2E Performances:", font_style='bold', fore_color='light-blue'))
            for perf in state.performances:
                print(ANSIStyler.style(f"\t{perf} ({tot_x_time:.4f}ms)", font_style='bold',
                                       fore_color='light-yellow'))

    @abstractmethod
    def show(self):
        raise NotImplementedError(f"Please implement '{self.__class__.__name__}.show()'")

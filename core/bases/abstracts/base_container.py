import re
from abc import ABCMeta

from core.bases.abstracts.base_metric import BaseMetric
from core.bases.abstracts.base_module import BaseModule
from core.bases.datas.flow_storage import FlowStorage
from exceptions.frameworks.modules import DuplicateModuleIdException, \
    MultipleStarterModuleException, InvalidModuleIdException
from core.utils.ansi_styler import ANSIStyler


class BaseContainer(metaclass=ABCMeta):
    def __init__(self, modules: list[BaseModule], e2e_metrics: list[BaseMetric] = None):
        self.modules: dict[str, BaseModule] = {m.module_id: m for m in self.__validate_module_id(modules)}
        self.starter: BaseModule | None = None
        self.metrics: list[BaseMetric] | None = e2e_metrics
        self.storage: FlowStorage = FlowStorage(self.__class__.__name__, self.__init_graph(modules))
        self.__set_starter_module()
        self.__set_directions()

    def get_module_by_id(self, m_id: str) -> BaseModule:
        return self.modules[m_id]

    def __validate_module_id(self, modules: list[BaseModule]) -> list[BaseModule]:
        ids: list[str] = []
        for module in modules:  # check id format
            if re.fullmatch(r'^[A-Za-z0-9_]+$', module.module_id) is None:  # only allows alphabet, number, underscore
                raise InvalidModuleIdException(module.module_id,
                                               "Only combination of alphabets, numbers, and underscores are allowed.")
            # if module.module_id in ['gen']:  # next도 없게해야할까
            #     raise InvalidModuleIdException(module.module_id,
            #                                    "'gen' is reserved. Use the other one instead.")
            ids.append(module.module_id)
        u_ids: set[str] = set(ids)

        if len(ids) != len(u_ids):  # check dup
            duplicate_ids: set[str] = u_ids.difference(set(ids))
            raise DuplicateModuleIdException(duplicate_ids)
        return modules

    def __init_graph(self, modules: list[BaseModule]) -> list[tuple[str, str]]:
        # gather all links from modules
        res: list[tuple[str, str]] = []
        for module in modules:
            res.extend(module.dependency.dependencies)
        return res

    def __set_starter_module(self):
        for _, module in self.modules.items():
            if module.is_starter:
                if self.starter is not None:
                    raise MultipleStarterModuleException(self.starter.module_id, module.module_id)
                self.starter = module

    def __set_directions(self) -> None:
        for _, module in self.modules.items():
            dependencies: list[tuple[str, str]] = module.dependency.dependencies
            for link in dependencies:
                self.modules[link[0]].direction.add_direction(link)

    def print_eval(self):
        for query_idx, state in self.storage.results.items():
            tot_x_time: float = 0  # ms
            print()
            print(ANSIStyler.style(f"[{self.__class__.__name__}]", font_style='bold',
                                   fore_color='light-green'))  # flow name
            print(ANSIStyler.style(f'Query({state.x_id}): {state.query}', font_style='bold',
                                   fore_color='light-green'))  # query
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

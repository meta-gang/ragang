import re
from abc import ABCMeta
from asyncio import Lock

from ragang.core.bases.abstracts.base_metric import BaseMetric
from ragang.core.bases.abstracts.base_module import BaseModule
from ragang.core.bases.datas.flow_storage import FlowStorage
from ragang.core.bases.datas.state import State
from ragang.core.decorators.use_lock import use_async_lock
from ragang.exceptions.user.module import DuplicateModuleIdException, \
    MultipleStarterModuleException, InvalidModuleIdException
from ragang.exceptions.user.structure import RagangStructureException
from ragang.core.utils.ansi_styler import ANSIStyler


class BaseContainer(metaclass=ABCMeta):
    def __init__(self, flow_id: str, modules: list[BaseModule], e2e_metrics: list[BaseMetric] = None,
                 max_steps: int = 1000):
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        self.flow_id: str = flow_id
        self.max_steps: int = max_steps
        self.modules: dict[str, BaseModule] = {m.module_id: m for m in self.__validate_module_id(modules)}
        self.starter: BaseModule | None = None
        self.metrics: list[BaseMetric] | None = e2e_metrics
        self.storage: FlowStorage = FlowStorage(flow_id, self.__init_graph(modules))
        self._storage_state_lock: Lock = Lock()
        self.__set_starter_module()
        self.__set_directions()

    def get_module_by_id(self, m_id: str) -> BaseModule:
        return self.modules[m_id]

    async def save_state(self, q_id: str, state: State) -> None:
        @use_async_lock(self._storage_state_lock)
        async def run():
            self.storage.set_result(q_id, state)
        await run()

    def get_result(self, q_id: str) -> State:
        return self.storage.get_result(q_id)

    def __validate_module_id(self, modules: list[BaseModule]) -> list[BaseModule]:
        ids: list[str] = []
        for module in modules:  # check id format
            if re.fullmatch(r'^[A-Za-z0-9_]+$', module.module_id) is None:  # only allows alphabet, number, underscore
                raise InvalidModuleIdException(module.module_id,
                                               "Only combination of alphabets, numbers, and underscores are allowed.")
            # if module.module_id in ['gen']:
            #     raise InvalidModuleIdException(module.module_id,
            #                                    "'gen' is reserved. Use the other one instead.")
            ids.append(module.module_id)
        u_ids: set[str] = set(ids)

        if len(ids) != len(u_ids):  # check dup
            duplicate_ids: set[str] = {i for i in u_ids if ids.count(i) > 1}
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
        if self.starter is None:
            raise RagangStructureException(
                f"Container '{self.flow_id}' has no starter module. "
                f"Set 'is_starter=True' on exactly one module to define where the flow begins.")

    def __set_directions(self) -> None:
        for _, module in self.modules.items():
            dependencies: list[tuple[str, str]] = module.dependency.dependencies
            for link in dependencies:
                self.modules[link[0]].direction.add_direction(link)

    def print_eval(self):
        print(ANSIStyler.style(f"[{self.flow_id}]", font_style='bold', fore_color='light-magenta'))  # flow name
        for query_idx, state in self.storage.results.items():
            tot_x_time: float = 0  # ms
            print(ANSIStyler.style(f'Query({state.q_id}): {state.query}', font_style='bold',
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
            print()

import warnings
from abc import ABCMeta, abstractmethod
from typing import Any
import inspect

from core.bases.abstracts.base_metric import BaseMetric
from core.bases.datas.linker import Direction, Dependency, Linker
from core.bases.datas.packet import Packet
from core.bases.datas.performance import Performance
from core.bases.datas.state import State


class BaseModule(metaclass=ABCMeta):  # observer
    def __init__(self, module_id: str, linker: Linker = None, metrics: list[BaseMetric] | None = None,
                 is_starter: bool = False):
        self.module_id: str = module_id
        self.dependency: Dependency = linker.build(module_id) if linker else Dependency([], False)
        self.direction: Direction = Direction()
        self.metrics: list[BaseMetric] | None = metrics
        self.is_starter: bool = is_starter
        self.param_keys: list[str] = self.__required_params()
        self.lazy_state: State = None  # lazy injection, inject when call execute()

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "direction": self.direction.directions,
            "dependency": self.dependency.dependencies,
            "metrics": [m.__class__.__name__ for m in self.metrics],
            "is_starter": self.is_starter,
        }

    def __required_params(self) -> list[str]:
        return list(inspect.signature(self.execute).parameters.keys())

    # callable in execute only
    def get_performance(self, target_mid: str) -> list[Performance]:
        if self.lazy_state is not None:
            if (packet := self.lazy_state.get_latest_packet(target_mid)) is not None:
                return packet.performances
            warnings.warn(f"Trying to get performance for module '{target_mid}' which is not yet executed or not exists", RuntimeWarning)
        return None

    @abstractmethod
    def execute(self, *args, **kwargs):
        """ TODO: Define this module's responsibility """
        raise NotImplementedError(f"Please implement '{self.__class__.__name__}.execute()'")

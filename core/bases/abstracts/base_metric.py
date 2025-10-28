from abc import ABCMeta, abstractmethod

from core.bases.datas.performance import Performance
from exceptions.user.metric import MetricParamSourceException


class BaseMetric(metaclass=ABCMeta):
    def __init__(self, param_src: list[str]):
        if param_src is None:
            raise MetricParamSourceException(f"Metric '{self.__class__.__name__}' parameter source is not defined.")
        for r in param_src:
            if '.' not in r:  # TODO: use pattern match via regex
                raise MetricParamSourceException(
                    f"{self.__class__.__name__} got invalid ref '{r}'. Expected 'module_id.key'")
        self.param_refs: list[str] = param_src

    @abstractmethod
    def evaluate(self, *args, **kwargs) -> Performance:
        raise NotImplementedError(f"Please implement '{self.__class__.__name__}.evaluate()'")

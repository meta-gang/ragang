from abc import ABCMeta, abstractmethod

from core.bases.datas.performance import Performance


class BaseMetric(metaclass=ABCMeta):
    @abstractmethod
    def evaluate(self, *args, **kwargs) -> Performance:
        raise NotImplementedError(f"Please implement '{self.__class__.__name__}.evaluate()'")

from abc import ABCMeta, abstractmethod

from core.bases.datas.performance import Performance


class BaseMetric(metaclass=ABCMeta):
    def __init__(self, param_src: tuple[str, ...] | None = None):
        refs = tuple(param_src)
        if not refs:
            raise ValueError(f"{self.__class__.__name__} have no param_src")
        for r in refs:
            if '.' not in r:  # TODO: use pattern match via regex
                raise ValueError(f"{self.__class__.__name__} got invalid ref '{r}'. Expected 'module_id.key'")
        self.param_refs: tuple[str, ...] = refs

    @abstractmethod
    def evaluate(self, *args, **kwargs) -> Performance:
        raise NotImplementedError(f"Please implement '{self.__class__.__name__}.evaluate()'")

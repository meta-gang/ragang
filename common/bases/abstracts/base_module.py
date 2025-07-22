from abc import ABCMeta, abstractmethod

from .base_metric import BaseMetric
from exceptions.frameworks.types import ModuleConnectionException
from ..datas.performance_dataclass import Performance


class BaseModule(metaclass=ABCMeta):
    def __init__(self, metric: BaseMetric = None):
        self.__next_module: BaseModule | None = None
        self.__metric: BaseMetric | None = metric  # 여러 metric을 모두 적용한 결과를 볼 수 있게 하고 싶다면 얘랑 아래 performance를 리스트로 만들기
        self.performance: Performance | None = None

    def __execute(self, *args, **kwargs):
        result = self.execute(*args, **kwargs)
        if self.__metric is None:
            self.performance = Performance(_eval=False)
        else:
            self.performance = self.__metric.evaluate(result, *args, **kwargs)
        return self.__chain_call(result) or result
        # 최종 결과가 빈 문자열 등 0을 의미하는 값이라면 그 중간 결과가 결과로 return 될 수 있으니 윗 라인이 타당한 코드인지 더 생각해보기
        # 지금은 우리가 각 metric을 구현할 때 여러 형태로 들어올 in/out data에서 적절한 것들을 뽑아서 평가하도록 만들어야 하니 이걸 사용자가 좀 우리가 정한 interface에 맞게 변형해 metric에 반영할 수 있도록 할 수 없을까?
        # 지금은 metric의 입력이 각 모듈이 실행 되는 과정에서의 그 데이터 흐름에 너무 의존해있는 느낌임 이걸 좀 개선하자

    def __rshift__(self, _next: 'BaseModule'):
        # connect modules by using '>>' operator
        # TODO: type checking
        # TODO: connect to the next module
        if not isinstance(_next, BaseModule):
            raise ModuleConnectionException(str(type(_next)))

        if self.__next_module:
            # if this module is already connected with some module, insert new module
            _next.__next_module = self.__next_module
        self.__next_module = _next

        # piv: BaseModule = self
        # while piv.__next_module:
        #     piv = piv.__next_module
        # or head에 >> 로 여러개 연결지을 수 있도록 여기서 next_module을 쭉 들어가서 마지막 뒤에 새로운 모듈 연결되게 만들까? 그러면 컨테이너에서 모듈 연결할 때 reduce도 사용 가능해보임
        # 근데 이렇게 하면 이미 구축해둔 sequence의 중간에 모듈을 끼워 넣는게 불가
        return self

    def __chain_call(self, *args, **kwargs):
        if not self.__next_module is None:
            return self.__next_module.__execute(*args, **kwargs)
        return None

    @abstractmethod
    def execute(self, *args, **kwargs):
        """ TODO: Define this module's responsibility """
        raise NotImplementedError(f"Please implement '{self.__class__.__name__}.execute()'")

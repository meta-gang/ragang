import time
import inspect
from abc import ABCMeta, abstractmethod
from typing import Any

from common.bases.abstracts.base_metric import BaseMetric
from common.bases.datas.flow_storage import Packet, FlowStorage
from common.bases.datas.linker import Dependency, Linker
from common.bases.datas.performance_dataclass import Performance
from exceptions.frameworks.datas import MissingMetricDataException, MissingMetricArgumentException, \
    ModuleOutputException
from exceptions.frameworks.modules import StarterModuleException

# metric: BaseMetric = None -> metrics: list[BaseMetric] | BaseMetric | None = None
class BaseModule(metaclass=ABCMeta):  # observer
    def __init__(self, module_id: str, linker: Linker = None, metrics: list[BaseMetric] | BaseMetric | None = None, is_starter: bool = False):
        self.module_id: str = module_id
        self.dependency: Dependency = linker.build(module_id) if linker else Dependency([], False)
        #self.__metric: BaseMetric | None = metric
        # metrics를 항상 리스트로 관리
        self.__metrics: list[BaseMetric] = []
        if isinstance(metrics, list):
            self.__metrics.extend(metrics)
        elif metrics is not None:
            self.__metrics.append(metrics)
        self.storage: FlowStorage | None = None
        self.is_starter: bool = is_starter

    def trigger_chain_execution(self, query: str):
        if not self.is_starter:
            raise  StarterModuleException(f"Trying to call trigger method at '{self.module_id}'.\n"
                                          f"Only starter modules can use trigger method.")

        signature: list[str] = list(inspect.signature(self.execute).parameters.keys())
        if signature != ['query']:
            raise StarterModuleException(f"Method execute() of starter module '{self.module_id}' can only accept 'query' parameter.\n"
                                         f"But received {signature}.")

        args: dict[str, Any] = {'query': query}
        self.__execute(args)


    def update(self, packet: Packet) -> None:  # event handler
        """
        우선 지금은 모듈의 return이 아래와 같다고 가정
        {
            'd1': object,
            'd2': object,
            'metric': {
                'param1': object,
                'param2': object,
            }
        }
        Data class로 만들어 사용할 것
        """
        if not self.__satisfy_dependency(packet):
            return

        # parse module input
        args: dict[str, Any] = self.__retrieve_parameter(packet)

        self.__execute(args)

    def __satisfy_dependency(self, packet: Packet) -> bool:
        if self.module_id not in packet.destinations:
            return False
        return self.dependency.check_dependencies(self.storage.state.x_status)

    def __retrieve_parameter(self, packet: Packet) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if self.dependency.is_or:  # for cond, loop module
            for dep_mid in self.dependency.get_dependent_mids():
                if packet.src == dep_mid:
                    args[dep_mid] = packet.data[self.module_id]  # TODO: Data 객체 만들고 수정
                else:
                    args[dep_mid] = None
        else:  # for merge module
            dep_mids: list[str] = self.dependency.get_dependent_mids()
            for dep_mid in dep_mids:
                args[dep_mid] = self.storage.state.snapshots[dep_mid][-1].data[self.module_id]
        return args

    def __execute(self, args: dict[str, Any]):
        # call self.execute()
        x_start: float = time.time()
        new_result: dict[str, Any] = self.execute(**args)
        x_time: float = time.time() - x_start

        # validate output data
        self.__validate_output(new_result)

        # evaluation
        eval_data: dict[str, Any] | None = new_result.pop('metric', None)
        performance: dict[str, list] = self.__evaluate_performance(eval_data)

        # build packet
        new_packet = Packet(self, new_result, performance, x_time)

        # send packet
        self.storage.send_packet(new_packet)

    def __validate_output(self, output: dict[str, Any]) -> dict[str, Any]:
        # metrics가 있는데 metric 데이터가 없으면 예외 발생
        if self.__metrics is not None and 'metric' not in output.keys():
            raise MissingMetricDataException(self.module_id, [metric.__class__.__name__ for metric in self.__metrics])
        # metrics가 없는데 metric 데이터가 있는 경우 metric 데이터 제거
        if self.__metrics is None and 'metric' in output.keys():
            output.pop('metric')
        """
        # 기존 코드
        if self.__metrics is not None and 'metric' not in output.keys():
            raise MissingMetricDataException(self.module_id, self.__metric.__class__.__name__)
        if self.__metric is None and 'metric' in output.keys():
            output.pop('metric')
        """

        subscribers: list[str] = [module.module_id for module in self.storage.subscription[self.module_id]]
        dest_mids: list[str] = [dest_mid for dest_mid in output.keys() if dest_mid not in ['metric', 'answer']]
        for mid in dest_mids:
            if mid not in subscribers:
                raise ModuleOutputException(f"Destination module '{mid}' is not depends on module '{self.module_id}'.\n"
                                            f"But '{self.module_id}' is trying to send packet to '{mid}'.")

        return output

    def __evaluate_performance(self, eval_data: dict[str, Any]) -> dict[str, list]:
        # or not self.__metrics 추가
        if eval_data is None or not self.__metrics:
            return {"Not evaluated": [0.0, '%']}
            #return Performance(_eval=False)

        # 8/7 수정 부분
        metric_results = {}
        for metric in self.__metrics:
            metric_name = metric.__class__.__name__
            # 8/8 수정 부분
            try:
                signature: dict[str, inspect.Parameter] = dict(
                    inspect.signature(metric.evaluate).parameters)
                req_params: list[str] = list(signature.keys())

                if any([rp not in eval_data.keys() for rp in req_params]):
                    raise MissingMetricArgumentException(
                        self.module_id, metric_name, req_params)

                args = {rp: eval_data[rp] for rp in req_params}
                # 각 metric의 결과인 Performance 객체를 result에 임시 저장 / evaluate 함수는 Performance 객체 리턴
                result = metric.evaluate(**args)

                # metric_recults 딕셔너리에 metric_name 키: [점수, unit] 저장
                metric_results[metric_name] = [result.score, result.unit]

            except Exception as e:
                # --- 오류 발생 시, 결과에 에러 메시지를 기록 ---
                metric_results[metric_name] = {"error": str(e)}

        # metric_results 딕셔너리를 execute 함수로 리턴하고 패킷에 딕셔너리 형태로 저장
        return metric_results
        """
        # parse arg names via signature of metric.evaluate()
        signature: dict[str, inspect.Parameter] = dict(inspect.signature(self.__metric.evaluate).parameters)
        req_params: list[str] = list(signature.keys())

        if any([rp not in eval_data.keys() for rp in req_params]):
            raise MissingMetricArgumentException(self.module_id, self.__metric.__class__.__name__, req_params)

        args = {rp: eval_data[rp] for rp in req_params}
        return self.__metric.evaluate(**args)
        """

    @abstractmethod
    def execute(self, *args, **kwargs):
        """ TODO: Define this module's responsibility """
        raise NotImplementedError(f"Please implement '{self.__class__.__name__}.execute()'")

# if __name__ == '__main__':
#     class M(BaseModule):
#         def execute(self, query: str, he):
#             pass
#
#     m = M('hello', None, None, True)
#     m.trigger_chain_execution('dd')


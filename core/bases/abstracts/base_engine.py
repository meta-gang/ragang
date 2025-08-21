from core.bases.datas.performance import Performance
from core.bases.datas.flow_storage import FlowStorage
from core.bases.abstracts.base_metric import BaseMetric
from core.bases.datas.packet import Packet 

from exceptions.user.keyname import NotCorrectModuleId, NotCorrectDataKey
from exceptions.frameworks.datas import NotCorrectStorage, NoOutputData

class FlowEngine:
    def __init__(self, storage: FlowStorage):
        self.storage = storage

    def run(self, metrics: list[BaseMetric]):
        performances: list[Performance] = self.__eval(metrics)
        return performances

    def __eval(self, metrics: list[BaseMetric]) -> list[Performance]:
        results = []
        for metric in metrics:
            args = [self._resolve_param(ref) for ref in metric.param_refs]
            performance = metric.evaluate(*args)
            results.append(performance)
        return results

    def _resolve_param(self, ref: str):
        try:
            module_id, key = ref.split('.', 1)

            state = getattr(self.storage, "state", None)
            if state is None:
                raise NotCorrectStorage()
            snapshots = getattr(state, "snapshots", None)
            if snapshots is None:
                raise NotCorrectStorage()

            snapshot: list[Packet] = snapshots.get(module_id, None)
            if not snapshot:
                raise NotCorrectModuleId(module_id=module_id)
            
            last_packet = snapshot[-1]
            output = getattr(last_packet, "data", None)
            if output is None:
                raise NoOutputData(module_id=module_id, output=output)
            
            value = output.get(key)
            if value is None:
                raise NotCorrectDataKey(module_id=module_id, key=key)
            
            return value
        except Exception as e:
            raise ValueError(f"Failed to resolve param '{ref}': {e}")

from core.bases.datas.performance import Performance
from core.bases.datas.flow_storage import FlowStorage
from core.bases.abstracts.base_metric import BaseMetric
from core.bases.datas.packet import Packet 

from exceptions.user.keyname import NotCorrectModuleId, NotCorrectDataKey  # TODO: rename exception classes
from exceptions.frameworks.datas import NotCorrectStorage, NoOutputData  # TODO: rename exception classes

class FlowEngine:
    def __init__(self, storage: FlowStorage):
        self.storage = storage

    def run(self, metrics: list[BaseMetric]):
        self._prepare_storage_from_metrics(metrics)
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
            raise ValueError(f"Failed to resolve param '{ref}': {e}")  # TODO: replace with custom exception class

    def _prepare_storage_from_metrics(self, metrics: list[BaseMetric]) -> None:
        state = getattr(self.storage, "state", None)
        if state is None:
            return

        if getattr(self.storage, "subscription", None) is None:
            self.storage.subscription = {}

        if getattr(state, "snapshots", None) is None:
            state.snapshots = {}

        mids: set[str] = set()
        for m in metrics:
            for ref in m.param_refs:
                if '.' in ref:
                    mid, _ = ref.split('.', 1)
                    mids.add(mid)

        for mid in mids:
            if mid not in self.storage.subscription:
                self.storage.subscription[mid] = []
            if mid not in state.snapshots or state.snapshots[mid] is None:
                state.snapshots[mid] = []

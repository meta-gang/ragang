from ragang.core.bases.datas.packet import Packet
from ragang.core.bases.datas.performance import Performance
from ragang.core.decorators.serializable import serializable


@serializable
class State:
    def __init__(self, q_id: str, query: str):
        self.query: str = query
        self.q_id: str = q_id  # any distinguishable id for each query
        self.snapshots: dict[str, list[Packet]] = dict()  # module output packet snapshots
        self.performances: list[Performance] = None
        self.gen: str | None = None
        self.run_metadata: dict = {}
        self.diagnosis: dict | None = None
        self.execution_trace: list[dict] = []
        self.execution_summary: dict = {
            "total_executions": 0,
            "completed_executions": 0,
            "failed_executions": 0,
            "module_revisits": 0,
            "repeated_modules": [],
            "total_latency_seconds": 0.0,
            "terminated": False,
            "termination_reason": None,
        }

    def save_snapshots(self, packet: Packet):
        if self.snapshots.get(packet.src, None) is None:
            self.snapshots[packet.src] = [packet]
        else:
            self.snapshots[packet.src].append(packet)

        # save gen (for output module)
        if packet.is_answer:
            self.gen = packet.data.get('gen', None)

    def get_latest_packet(self, mid: str) -> Packet:
        if (snapshot := self.snapshots.get(mid, None)) is None:
            return None  # no packet
        return snapshot[-1]  # latest packet

    def next_execution_identity(self, module_id: str) -> tuple[str, int]:
        execution_index = 1 + sum(
            event.get("module_id") == module_id for event in self.execution_trace
        )
        return f"exec-{len(self.execution_trace) + 1}", execution_index

    def latest_execution_id(self, module_id: str) -> str | None:
        for event in reversed(self.execution_trace):
            if event.get("module_id") == module_id and event.get("status") == "completed":
                return event.get("execution_id")
        return None

    def record_execution(self, *, execution_id: str, module_id: str, execution_index: int,
                         parent_execution_ids: list[str], dependency_modules: list[str],
                         status: str, latency_seconds: float, input_keys: list[str],
                         output_keys: list[str], next_modules: list[str],
                         failure: dict | None = None) -> None:
        event = {
            "execution_id": execution_id,
            "module_id": module_id,
            "execution_index": execution_index,
            "revisit_count": execution_index - 1,
            "parent_execution_ids": list(parent_execution_ids),
            "dependency_modules": list(dependency_modules),
            "status": status,
            "latency_seconds": latency_seconds,
            "input_keys": sorted(input_keys),
            "output_keys": sorted(output_keys),
            "next_modules": list(next_modules),
        }
        if failure is not None:
            event["failure"] = failure
        self.execution_trace.append(event)
        self.refresh_execution_summary()

    def refresh_execution_summary(self, *, terminated: bool | None = None,
                                  termination_reason: str | None = None) -> None:
        module_counts: dict[str, int] = {}
        for event in self.execution_trace:
            module_id = event.get("module_id")
            module_counts[module_id] = module_counts.get(module_id, 0) + 1
        repeated_modules = [
            {
                "module_id": module_id,
                "executions": count,
                "revisits": count - 1,
            }
            for module_id, count in sorted(module_counts.items())
            if count > 1
        ]
        if terminated is None:
            terminated = bool(self.execution_summary.get("terminated"))
        if termination_reason is None:
            termination_reason = self.execution_summary.get("termination_reason")
        self.execution_summary = {
            "total_executions": len(self.execution_trace),
            "completed_executions": sum(
                event.get("status") == "completed" for event in self.execution_trace
            ),
            "failed_executions": sum(
                event.get("status") == "failed" for event in self.execution_trace
            ),
            "module_revisits": sum(item["revisits"] for item in repeated_modules),
            "repeated_modules": repeated_modules,
            "total_latency_seconds": sum(
                float(event.get("latency_seconds") or 0.0) for event in self.execution_trace
            ),
            "terminated": terminated,
            "termination_reason": termination_reason,
        }

    def finalize_execution(self, termination_reason: str, *, success: bool) -> None:
        self.refresh_execution_summary(
            terminated=not success,
            termination_reason=termination_reason,
        )

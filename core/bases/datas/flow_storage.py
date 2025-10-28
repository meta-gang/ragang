from core.bases.datas.state import State
from core.decorators.serializable import serializable


@serializable
class FlowStorage:
    def __init__(self, flow_id: str, flow_graph: list[tuple[str, str]]) -> None:
        self.flow_id: str = flow_id
        self.flow_graph: list[tuple[str, str]] = flow_graph
        self.results: dict[str, State] = {}

    def set_result(self, q_id: str, result: State) -> None:
        self.results[q_id] = result
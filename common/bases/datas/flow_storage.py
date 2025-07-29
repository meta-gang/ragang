# from common.bases.abstracts.base_module import BaseModule
from dataclasses import dataclass
from typing import Any

from common.bases.datas.performance_dataclass import Performance


class FlowStorage:
    def __init__(self, flow_id: str):
        self.flow_id: str = flow_id
        self.subscription: dict[str, list['BaseModule']] = dict()
        self.state: State | None = None
        self.history: dict[int, State] = {}

    def subscribe(self, subscriber: 'BaseModule', src_mid: str):
        self.subscription[src_mid].append(subscriber)

    def unsubscribe(self, subscriber: 'BaseModule', src_mid: str):
        if subscriber not in self.subscription[src_mid]:
            return
        self.subscription[src_mid].remove(subscriber)

    def notify_all(self, packet: 'Packet'):
        for subscriber in self.subscription[packet.src]:
            subscriber.update(packet)

    def construct(self, x_id: int, query: str):
        self.state = State(x_id=x_id, query=query)

    def destruct(self, performance: Performance):
        self.state.performance = performance
        self.history[self.state.x_id] = self.state
        self.state = None

    def send_packet(self, packet: 'Packet'):
        # 1. add execution status == link
        self.state.add_x_status(packet.src, packet.destinations)
        # 2. refresh execution status
        self.state.refresh_x_status(packet.src)
        # 3. store packet into snapshots
        self.state.save_snapshots(packet)
        # 4. notify listeners
        self.notify_all(packet)

class State:
    def __init__(self, x_id: int, query: str):
        self.query: str = query
        self.x_id: int = x_id  # query index or any distinguishable id for each query
        self.x_status: list[tuple[str, str]] = list()  # execution status (for dependency checking)
        self.snapshots: dict[str, list['Packet']] = dict()  # module output packet snapshots
        self.performance: Performance = Performance()
        self.answer: str | None = None

    def save_snapshots(self, packet: 'Packet'):
        if self.snapshots.get(packet.src, None) is None:
            self.snapshots[packet.src] = [packet]
        else:
            self.snapshots[packet.src].append(packet)

        # save answer (for output module)
        if packet.is_answer:
            self.answer = packet.data.get('answer', None)

    def add_x_status(self, src_mid: str, dest_mids: list[str]):
        if len(dest_mids) == 0:
            self.x_status.append((src_mid, None))
        for dest in dest_mids:
            self.x_status.append((src_mid, dest))

    def refresh_x_status(self, src_mid: str):
        current_x: tuple[str, str] = self.x_status[-1]
        self.__refresh_x_status(src_mid, 0)
        self.x_status.append(current_x)

    def __refresh_x_status(self, src_mid: str, idx: int):
        if idx >= len(self.x_status):
            return

        if self.x_status[idx][0] == src_mid:
            n_mid: str = self.x_status[idx][1]
            self.x_status.pop(idx)
            self.__refresh_x_status(src_mid, idx)  # find next src
            self.__refresh_x_status(n_mid, 0)  # for chain reaction
            return

        self.__refresh_x_status(src_mid, idx + 1)


class Packet:
    def __init__(self, src_m: 'BaseModule', data: dict[str, object], performance: Performance, x_time: float):
        self.src: str = src_m.module_id  # src_mid
        self.data: dict[str, Any] = data  # {dest_mid: data} TODO: Data 객체 만들고 수정
        self.performance: Performance = performance
        self.x_time: float = x_time  # sec
        self.destinations: list[str] = list(key for key in data.keys() if key not in ['metric', 'answer'])
        self.is_answer: bool = 'answer' in data.keys()

# if __name__ == '__main__':
#     state: State = State(0, 'hello')
#     state.x_status = [('1', '2'), ('1', '3'), ('3', '7'), ('7', '8'), ('8', '1')]
#     print(state.x_status)
#     state.refresh_x_status('8')
#     print(state.x_status)

from common.bases.abstracts.base_module import BaseModule
from common.bases.datas.packet import Packet
from common.bases.datas.performance import Performance
from common.bases.datas.state import State
from common.decorators.serialize import serializable


@serializable
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
            subscriber.chain_react(packet)

    def construct(self, x_id: int, query: str):
        self.state = State(x_id=x_id, query=query)

    def destruct(self, performance: Performance):
        self.state.performance = performance
        self.history[self.state.x_id] = self.state
        self.state = None

    def send_packet(self, packet: 'Packet'):
        # 1. add execution status == link
        status_cnt: int = self.state.add_x_status(packet.src, packet.destinations)
        # 2. refresh execution status
        self.state.refresh_x_status(packet.src, status_cnt)  # TODO: status_cnt로 추가된 status 관리하는 로직 수정
        # 3. store packet into snapshots
        self.state.save_snapshots(packet)
        # 4. notify listeners
        self.notify_all(packet)

# if __name__ == '__main__':
#     state: State = State(0, 'hello')
#     state.x_status = [('1', '2'), ('1', '3'), ('3', '7'), ('7', '8'), ('8', '1')]
#     print(state.x_status)
#     state.refresh_x_status('8')
#     print(state.x_status)

from ragang.core.bases.datas.packet import Packet
from ragang.core.bases.datas.performance import Performance
from ragang.core.decorators.serializable import serializable


@serializable
class State:
    def __init__(self, x_id: str, query: str):
        self.query: str = query
        self.x_id: str = x_id  # any distinguishable id for each query
        self.snapshots: dict[str, list[Packet]] = dict()  # module output packet snapshots
        self.performances: list[Performance] = None
        self.gen: str | None = None

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

from core.bases.datas.packet import Packet
from core.bases.datas.performance import Performance
from core.decorators.serializable import serializable


@serializable
class State:
    def __init__(self, x_id: int, query: str):
        self.query: str = query
        self.x_id: int = x_id  # query index or any distinguishable id for each query
        self.x_status: list[tuple[str, str]] = list()  # execution status (for dependency checking)
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

    def add_x_status(self, src_mid: str, dest_mids: list[str]) -> int:
        status_cnt: int = 0
        if len(dest_mids) == 0:
            self.x_status.append((src_mid, None))
            status_cnt += 1
        for dest in dest_mids:
            self.x_status.append((src_mid, dest))
            status_cnt += 1
        return status_cnt

    def refresh_x_status(self, src_mid: str, status_cnt: int):
        current_x: list[tuple[str, str]] = self.x_status[-status_cnt:]
        self.__refresh_x_status(src_mid, 0)
        self.x_status.extend(current_x)

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
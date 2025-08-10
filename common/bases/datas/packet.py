from typing import Any

from common.bases.datas.performance import Performance
from common.decorators.serialize import serializable


@serializable
class Packet:
    def __init__(self, src_mid: str, data: dict[str, object], performances: list[Performance], x_time: float):
        self.src: str = src_mid  # src_mid
        self.data: dict[str, Any] = data  # {dest_mid: data} TODO: Data 객체 만들고 수정
        self.performances: list[Performance] = performances
        self.x_time: float = x_time  # sec
        self.destinations: list[str] = list(key for key in data.keys() if key not in ['metric', 'gen'])
        self.is_answer: bool = 'gen' in data.keys()
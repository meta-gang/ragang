import asyncio
import json
import time
from collections import defaultdict
from typing import Dict, Set, Any, Callable, Awaitable, Optional
from websockets.server import WebSocketServerProtocol


def _ts() -> float:
    return time.time()


class SocketHandler:
    """
    - topic 구독형식
    - subscribers: { topic(str) -> set(websocket) }
    - broadcast(topic, payload) -> 해당 topic 구독자에게 전송
    - handle_connection(): subscribe/unsubscribe는 자체 처리, 나머지는 runner.topic_map을 통해 실행 함수 호출
    """
    def __init__(self):
        self.subscribers: Dict[str, Set[WebSocketServerProtocol]] = defaultdict(set)
        self.on_message: Optional[Callable[[dict, WebSocketServerProtocol, "SocketHandler"], Awaitable[None]]] = None

    def _normalize_topics(self, topics: Any) -> Set[str]:
        if isinstance(topics, str):
            return {topics}
        if isinstance(topics, (list, tuple, set)):
            return {t for t in topics if isinstance(t, str)}
        return set()

    async def subscribe(self, ws: WebSocketServerProtocol, topics: Any):
        for t in self._normalize_topics(topics):
            self.subscribers[t].add(ws)

    async def unsubscribe(self, ws: WebSocketServerProtocol, topics: Any):
        for t in self._normalize_topics(topics):
            self.subscribers[t].discard(ws)

    def _purge_ws(self, ws: WebSocketServerProtocol):
        for t in list(self.subscribers.keys()):
            self.subscribers[t].discard(ws)

    async def broadcast(self, topic: str, payload: dict):
        msg = {"topic": topic, "ts": _ts(), **payload}
        dead = []
        for ws in list(self.subscribers.get(topic, set())):
            try:
                await ws.send(json.dumps(msg, ensure_ascii=False))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.subscribers[topic].discard(ws)

    async def handle_connection(self, ws: WebSocketServerProtocol):
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue

                t = msg.get("topic")
                if not t or not isinstance(t, str):
                    continue

                if t == "subscribe":
                    await self.subscribe(ws, msg.get("topics") or [])
                    continue

                if t == "unsubscribe":
                    await self.unsubscribe(ws, msg.get("topics") or [])
                    continue

                if callable(self.on_message):
                    await self.on_message(msg, ws, self)

        finally:
            self._purge_ws(ws)

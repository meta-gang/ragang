import asyncio
import datetime as dt
import traceback
from typing import Dict, Tuple, List

from core.utils.query_generator import generate_query_from_data

def _ts_str() -> str:
    kst = dt.timezone(dt.timedelta(hours=9))
    return dt.datetime.now(tz=kst).strftime("%Y%m%d-%H:%M")


class Runner:
    """
    - 실제 실행 함수만 보관
    - topic_map: {topic: handler_func}
    - 모듈 상태 및 결과 브로드캐스트는 handler.broadcast 사용
    """
    def __init__(self, handler, rag_container):
        self.handler = handler
        self.rag = rag_container
        self._query_store: Dict[str, str] = {}

        self._install_status_callback()

        # topic 매핑
        self.topic_map = {
            "run-rag-file-query": self._on_run_rag_file_query,
            "run-rag-llm-query": self._on_run_rag_llm_query,
            "test-query": self._on_test_query,
        }

    def _install_status_callback(self):
        async def on_status_async(module_id: str, statu: str):
            await self.handler.broadcast("module-statu", {
                "module": module_id,
                "statu": statu
            })
        setattr(self.rag.storage, "_on_module_status", on_status_async)

    async def setup_handlers(self):
        await self._broadcast_container_topology()

    async def _broadcast_rag_result_from_history(self):
        hist = {qid: st.serialize() for qid, st in self.rag.storage.history.items()}
        await self.handler.broadcast("rag-result-data", {
            "ts": _ts_str(),
            "storage": {
                "flow_id": self.rag.storage.flow_id,
                "history": hist
            }
        })

    async def _broadcast_container_topology(self):
        edges: List[Tuple[str, str]] = []
        for m in getattr(self.rag, "modules", []): # TODO: self.rag.modules에 리스트로 모듈 저장
            dep = getattr(m, "dependency", None)
            if dep and hasattr(dep, "directions"):
                edges.extend(dep.directions)
        await self.handler.broadcast("rag-container", {"rag-container": edges})

    async def dispatch(self, msg: dict, ws):
        topic = msg.get("topic")
        fn = self.topic_map.get(topic)
        if not fn:
            return
        try:
            await fn(msg, ws)
        except Exception as e:
            await self.handler.broadcast("error", {
                "module": "runner",
                "message": str(e),
                "traceback": traceback.format_exc()
            })

    async def _on_run_rag_file_query(self, msg: dict, ws):
        files = msg.get("files") or []
        if not isinstance(files, list):
            files = []
        queries = [f"file:{name}" for name in files]

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.rag.invoke_batch, queries)

        await self._broadcast_rag_result_from_history()

    async def _on_run_rag_llm_query(self, msg: dict, ws):
        settings = msg.get("settings") or {}
        llm_option = (settings.get("llm_option") or "").lower()
        query_id = settings.get("query_id") or "query_1"

        if llm_option in ("새 질문 생성", "make-query"):
            file_path = settings.get("file_path", "./data/default.txt") # TODO: 기본 파일 경로 설정
            
            query = generate_query_from_data(
                getattr(self.rag, "llm_adapter", None),
                file_path
            )

        elif llm_option in ("기존 질문 사용", "made-query"):
            query = self._query_store.get(query_id, "Default query")
        else:
            query = settings.get("query", "Default query")

        self._query_store[query_id] = query

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.rag.invoke, query)

        await self._broadcast_rag_result_from_history()

    async def _on_test_query(self, msg: dict, ws):
        query = msg.get("query", "Hello?")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.rag.invoke, query)
        await self._broadcast_rag_result_from_history()
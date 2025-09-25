import asyncio
import datetime as dt
import traceback
from typing import Dict

from core.utils.query_generator import generate_query_from_chunks

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

    async def _broadcast_rag_result_from_history(self):
        hist = {qid: st.serialize() for qid, st in self.rag.storage.history.items()}
        await self.handler.broadcast("rag-result-data", {
            "ts": _ts_str(),
            "storage": {
                "flow_id": self.rag.storage.flow_id,
                "history": hist
            }
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
            chunks = ["chunk 1", "chunk 2"]  # TODO: 실제 청크 데이터로 교체
            query = generate_query_from_chunks(
                getattr(self.rag, "llm_adapter", None),
                chunks
            )
        elif llm_option in ("기존 질문 사용", "made-query"):
            query = self._query_store.get(query_id)
        else:
            query = settings.get("query")

        self._query_store[query_id] = query

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.rag.invoke, query)

        await self._broadcast_rag_result_from_history()

    async def _on_test_query(self, msg: dict, ws):
        query = msg.get("query")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.rag.invoke, query)
        await self._broadcast_rag_result_from_history()
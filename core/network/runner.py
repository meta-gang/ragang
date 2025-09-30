import datetime as dt
import traceback
from typing import Dict, Tuple, List

from core.utils.query_generator import generate_query_from_data

def _ts_str() -> str:
    kst = dt.timezone(dt.timedelta(hours=9))
    return dt.datetime.now(tz=kst).strftime("%Y%m%d-%H:%M")


class Runner:
    """
    - rag container와 socket handler를 연결
    - topic_map: { topic(str) -> handler(async fn) }
    - dispatch(msg, ws): topic_map을 통해 msg 처리
    - rag container의 상태 변화(start, end)를 socket handler로 브로드캐스트
    - rag container의 storage 변화(history 추가 등)를 socket handler로 브로드캐스트
    """
    def __init__(self, handler, rag_container):
        self.handler = handler
        self.rag = rag_container
        self._query_store: Dict[str, str] = {}

        self._install_status_callback()

        self.topic_map = {
            "run-rag-file-query": self._on_run_rag_file_query,
            "run-rag-llm-query": self._on_run_rag_llm_query,
            "test-query": self._on_test_query,
        }

    # rag 모듈 상태(start, end) 브로드캐스트 -> engine에서 호출
    def _install_status_callback(self):
        async def on_status_async(module_id: str, statu: str):
            await self.handler.broadcast("module-statu", {
                "module": module_id,
                "statu": statu
            })
        setattr(self.rag.storage, "_on_module_status", on_status_async)

    async def setup_handlers(self):
        await self._broadcast_container_topology()

    # query_id list로 storage 내용 브로드캐스트
    async def _broadcast_rag_result(self, query_ids: List[str]):
        hist = {
            qid: st.serialize()
            for qid, st in self.rag.storage.history.items()
            if qid in query_ids
        }
        await self.handler.broadcast("rag-result-data", {
            "ts": _ts_str(),
            "storage": {
                "flow_id": self.rag.storage.flow_id,
                "history": hist
            }
        })

    # rag container topology 브로드캐스트
    async def _broadcast_container_topology(self):
        edges: List[Tuple[str, str]] = []
        for m in getattr(self.rag, "modules", []):
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

    # query 파일
    async def _on_run_rag_file_query(self, msg: dict, ws):
        files = msg.get("files") or []
        if not isinstance(files, list):
            files = []

        queries = []
        for file_path in files:
            with open(file_path, "r", encoding="utf-8") as f:
                queries.extend([line.strip() for line in f if line.strip()])

        if not queries:
            raise ValueError("No queries extracted from files.")

        self.rag.invokes(queries)
        recent_items = list(self.rag.storage.history.items())[-len(queries):]
        query_ids = [qid for qid, _ in recent_items]
        await self._broadcast_rag_result(query_ids)

    # LLM 생성 query
    async def _on_run_rag_llm_query(self, msg: dict, ws):
        settings = msg.get("settings") or {}
        llm_option = (settings.get("llm_option") or "").lower()

        if llm_option in ("새 질문 생성", "make-query"):
            file_path = settings.get("file_path", "./data/default.txt")
            queries = generate_query_from_data(
                getattr(self.rag, "llm_adapter", None),
                file_path
            )
            if not isinstance(queries, list):
                queries = [queries]
            for idx, q in enumerate(queries, 1):
                qid = f"llm_query_{idx}"
                self._query_store[qid] = q
        elif llm_option in ("기존 질문 사용", "made-query"):
            file_path = settings.get("file_path")
            if not file_path:
                raise ValueError("file_path must be provided when using 'made-query'")
            with open(file_path, "r", encoding="utf-8") as f:
                queries = [line.strip() for line in f if line.strip()]
        else:
            raise ValueError(f"Unsupported llm_option: {llm_option}")

        if not queries:
            raise ValueError("No queries extracted for execution.")

        self.rag.invokes(queries)
        recent_items = list(self.rag.storage.history.items())[-len(queries):]
        query_ids = [qid for qid, _ in recent_items]
        await self._broadcast_rag_result(query_ids)

    # test query
    async def _on_test_query(self, msg: dict, ws):
        query = msg.get("query")

        self.rag.invoke(query)

        last_qid = list(self.rag.storage.history.keys())[-1]
        await self._broadcast_rag_result([last_qid])

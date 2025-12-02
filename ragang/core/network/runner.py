import datetime as dt
import json
import os
import traceback
import time
from typing import Dict, Tuple, List
from pathlib import Path

from ragang.core.utils.cli import get_history, update_history
from ragang.exceptions.user.cli import NotAllowedQueryFileException


def _ts_str() -> str:
    kst = dt.timezone(dt.timedelta(hours=9))
    return dt.datetime.now(tz=kst).strftime("%Y%m%d-%H:%M")


class Runner:
    def __init__(self, handler, engine, flow_id: str):
        self.handler = handler
        self.engine = engine
        self.flow_id = flow_id
        self._query_store: Dict[str, str] = {}

        self._install_status_callback()

        self.topic_map = {
            "run-rag-file-query": self._on_run_rag_file_query,
            "run-rag-llm-query": self._on_run_rag_llm_query,
            "test-query": self._on_test_query,
            "start!": self._start_react,
            "generated-query-files": self._generated_query_files,
            "custom-query-files": self._custom_query_files,
            "get-module-pairs": self._on_get_module_pairs
        }

    def _install_status_callback(self):
        try:
            cont = self.engine.containers[self.flow_id]

            async def on_status_async(module_id: str, statu: str):
                await self.handler.broadcast("module-statu", {
                    "module": module_id,
                    "statu": statu
                })

            setattr(cont.storage, "_on_module_status", on_status_async)
        except KeyError:
            print(f"[Runner] Warning: Flow ID '{self.flow_id}' not found in engine containers.")

    async def setup_handlers(self):
        await self._broadcast_container_topology()

    async def dispatch(self, msg: dict, ws):
        topic = msg.get("topic")
        fn = self.topic_map.get(topic)
        if not fn:
            print(f"[Runner] Unknown topic received: {topic}")
            return
        try:
            await fn(msg, ws)
        except Exception as e:
            print(f"[Runner] Dispatch Error: {e}")
            await self.handler.broadcast("error", {
                "module": "runner",
                "message": str(e),
                "traceback": traceback.format_exc()
            })

    # ------------------------------------------------------------------
    # [Helper Methods]
    # ------------------------------------------------------------------

    async def _broadcast_rag_result(self, query_ids: List[str]):
        cont = self.engine.containers[self.flow_id]

        states_payload = {
            qid: cont.storage.results[qid].serialize()
            for qid in query_ids
            if qid in cont.storage.results.keys()
        }

        await self.handler.broadcast("rag-result-data", {
            "ts": _ts_str(),
            "storage": {
                "flow_id": cont.flow_id,
                "states": states_payload
            }
        })

        try:
            current_ts = time.time()
            results = [cont.storage.results[qid] for qid in query_ids if qid in cont.storage.results.keys()]
            update_history(self.flow_id, current_ts, results)
            print(f"[Runner] History updated: {len(results)} results saved.")
        except Exception as e:
            print(f"[Runner] Error updating history: {e}")
            traceback.print_exc()

    async def _broadcast_container_topology(self):
        try:
            cont = self.engine.containers[self.flow_id]
            edges: List[Tuple[str, str]] = getattr(cont.storage, "flow_graph", [])
            await self.handler.broadcast("rag-container", {"rag-container": edges})
        except Exception as e:
            print(f"[Runner] Error broadcasting topology: {e}")

    async def _rag_on_run(self, query_num: int):
        await self.handler.broadcast("rag-on", {
            "ts": _ts_str(),
            "query-num": int(query_num),
        })

    # ------------------------------------------------------------------
    # [Handlers]
    # ------------------------------------------------------------------

    async def _on_run_rag_file_query(self, msg: dict, ws):
        QUERY_DIR = Path(os.getcwd()) / 'datas/queries/custom'
        settings = msg.get("settings") or {}
        file_name = settings.get("file_name")

        if not file_name:
            raise ValueError("file_name must be provided")

        file_path = QUERY_DIR / file_name

        if not file_path.is_file():
            raise FileNotFoundError(f"Query file not found: {file_path}")

        if Path(file_name).suffix != '.txt':
            raise NotAllowedQueryFileException(file_name)

        queries = []
        with open(file_path, "r", encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]

        if not queries:
            raise ValueError("No queries extracted for execution.")

        await self._rag_on_run(len(queries))
        results = await self.engine.async_invoke_batch(queries, flow_ids=[self.flow_id])

        query_ids = list(results.get(self.flow_id, {}).keys())
        await self._broadcast_rag_result(query_ids)

    async def _on_run_rag_llm_query(self, msg: dict, ws):
        QUERY_DIR = Path(os.getcwd()) / 'datas/queries/generated'
        settings = msg.get("settings") or {}
        file_name = settings.get("file_name")

        if not file_name:
            raise ValueError("file_name must be provided")

        file_path = QUERY_DIR / file_name
        if not file_path.is_file():
            raise FileNotFoundError(f"Query file not found: {file_path}")

        if Path(file_name).suffix != '.json':
            raise NotAllowedQueryFileException(file_name)

        queries = []
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            query_list = data.get('query', [])
            for q in query_list:
                if isinstance(q, dict):
                    queries.append(q.get('query', ''))
                elif isinstance(q, str):
                    queries.append(q)

        if not queries:
            raise ValueError("No queries extracted for execution.")

        await self._rag_on_run(len(queries))
        results = await self.engine.async_invoke_batch(queries, flow_ids=[self.flow_id])
        query_ids = list(results.get(self.flow_id, {}).keys())
        await self._broadcast_rag_result(query_ids)

    async def _on_test_query(self, msg: dict, ws):
        query = msg.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("`query` must be a non-empty string.")

        results = await self.engine.async_invoke(query, flow_ids=[self.flow_id])
        query_ids = list(results.get(self.flow_id, {}).keys())
        await self._broadcast_rag_result(query_ids)

    async def _generated_query_files(self, msg, ws):
        base_dir = Path(os.getcwd()) / 'datas/queries/generated'
        file_list = []
        try:
            if base_dir.exists() and base_dir.is_dir():
                for p in sorted(base_dir.rglob("*.json")):
                    file_list.append(p.name)
        except Exception:
            file_list = []

        await self.handler.broadcast("generated-query-files", {
            "ts": _ts_str(),
            "files": file_list
        })

    async def _custom_query_files(self, msg, ws):
        base_dir = Path(os.getcwd()) / 'datas/queries/custom'
        file_list = []
        try:
            if base_dir.exists() and base_dir.is_dir():
                for p in sorted(base_dir.rglob("*.txt")):
                    file_list.append(p.name)
        except Exception:
            file_list = []

        await self.handler.broadcast("custom-query-files", {
            "ts": _ts_str(),
            "files": file_list
        })

    async def _on_get_module_pairs(self, msg, ws):
        await self._broadcast_container_topology()

    async def _start_react(self, msg: dict, ws):
        print("[Backend] Start signal received!")
        try:
            flow_id = self.flow_id
            history = get_history(flow_id)
            safe_history = json.loads(json.dumps(history, default=str))

            await self.handler.broadcast("history", {
                "ts": _ts_str(),
                "history": safe_history
            })
        except Exception as e:
            print(f"[Backend] Error in _start_react: {e}")
            print(traceback.format_exc())
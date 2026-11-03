import datetime as dt
import json
import os
import time
import asyncio
from typing import Dict, Tuple, List
from pathlib import Path

from ragang.core.utils.cli import get_history, update_history, read_queries
from ragang.evaluator import safe_failure
from ragang.core.network.request_context import (
    current_request, RequestContext, EXECUTION_TOPICS, supplied_request_id, validate_request_id,
)
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
        self._execution_lock = asyncio.Lock()
        self._request_lock = asyncio.Lock()
        self._requests: dict[str, dict] = {}
        self._request_tasks: set[asyncio.Task] = set()
        self.max_request_records = 1024
        self._closing = False

        self._install_status_callback()

        self.topic_map = {
            "run-rag-file-query": self._on_run_rag_file_query,
            "run-rag-llm-query": self._on_run_rag_llm_query,
            "test-query": self._on_test_query,
            "start!": self._start_react,
            "generated-query-files": self._generated_query_files,
            "custom-query-files": self._custom_query_files,
            "get-module-pairs": self._on_get_module_pairs,
            "get-request-status": self._on_get_request_status
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

    async def _reply(self, ws, topic: str, payload: dict):
        if ws is None:
            return
        if hasattr(self.handler, 'send'):
            await self.handler.send(ws, topic, payload)
        else:
            try:
                await ws.send(json.dumps({"topic": topic, **payload}, ensure_ascii=False))
            except Exception:
                pass

    async def _reply_status(self, ws, record):
        await self._reply(ws, 'request-status', {key: value for key, value in record.items() if not key.startswith('_')})

    @staticmethod
    def _restored_record(request_id, states, *, persisted):
        failed = any(state.get('execution_summary', {}).get('terminated') is True or
                     state.get('execution_summary', {}).get('success') is False for state in states.values())
        completed = all(state.get('execution_summary', {}).get('success') is True or
                        state.get('execution_summary', {}).get('termination_reason') == 'answer' or
                        (isinstance(state.get('gen'), str) and state['gen'].strip() and
                         not state.get('execution_summary', {}).get('termination_reason')) for state in states.values())
        return {'request_id': request_id, 'status': 'failed' if failed else 'completed' if completed else 'unknown',
                'query_ids': list(states), 'run_ids': list(dict.fromkeys(
                    state.get('run_metadata', {}).get('run_id') for state in states.values()
                    if isinstance(state.get('run_metadata', {}).get('run_id'), str))), 'persisted': persisted}

    def _memory_request(self, request_id):
        """Snapshot completed States on the event loop, before any disk-worker await."""
        memory = {}
        container = self.engine.containers[self.flow_id]
        for query_id, state in getattr(container.storage, 'results', {}).items():
            metadata = getattr(state, 'run_metadata', {})
            if isinstance(metadata, dict) and metadata.get('request_id') == request_id:
                memory[query_id] = state.serialize()
        return memory

    def _find_stored_request(self, request_id, memory):
        """Disk I/O runs in a worker; mutable engine state is never read there."""
        saved = {}
        history = get_history(self.flow_id)
        for states in history.values():
            if not isinstance(states, dict):
                continue
            for query_id, state in states.items():
                if isinstance(state, dict) and isinstance(state.get('run_metadata'), dict) and state['run_metadata'].get('request_id') == request_id:
                    saved[query_id] = state
        if saved:
            return self._restored_record(request_id, saved, persisted=True)
        if memory:
            return self._restored_record(request_id, memory, persisted=False)
        return None

    def _make_request_room(self):
        while len(self._requests) >= self.max_request_records:
            removable = next((key for key, value in self._requests.items()
                              if value['status'] in ('completed', 'failed') and value.get('persisted') is True), None)
            if removable is None:
                return False
            del self._requests[removable]
        return True

    async def _accept_execution(self, msg, ws, operation):
        try:
            request_id = supplied_request_id(msg)
        except ValueError as error:
            await self._reply(ws, 'error', {'request_id': None, 'code': 'invalid_request_id', 'message': str(error)})
            return
        async with self._request_lock:
            record = self._requests.get(request_id)
            if record is None:
                try:
                    record = await asyncio.to_thread(self._find_stored_request, request_id, self._memory_request(request_id))
                except Exception:
                    await self._reply(ws, 'error', {'request_id': request_id, 'code': 'history_unavailable',
                        'message': '이력을 확인하지 못해 중복 실행 방지를 위해 요청을 시작하지 않았습니다.'})
                    return
            if record is not None:
                await self._reply_status(ws, record)
                return
            if self._closing:
                await self._reply(ws, 'error', {'request_id': request_id, 'code': 'server_stopping',
                    'message': '서버가 종료 중이므로 새 평가를 시작하지 않았습니다.'})
                return
            if not self._make_request_room():
                await self._reply(ws, 'error', {'request_id': request_id, 'code': 'request_capacity',
                    'message': '미저장 요청 기록의 보존 한도에 도달했습니다. 결과 저장 상태를 확인하고 서버를 재시작한 뒤 새 평가를 실행하세요.'})
                return
            record = {'request_id': request_id, 'status': 'queued', 'query_ids': [], 'run_ids': [], 'persisted': False, '_ws': ws}
            self._requests[request_id] = record
            await self._reply_status(ws, record)
            task = asyncio.create_task(self._execute_request(msg, ws, operation, record))
            self._request_tasks.add(task)
            task.add_done_callback(self._request_finished)

    def _request_finished(self, task):
        self._request_tasks.discard(task)
        if not task.cancelled():
            error = task.exception()  # Retrieve unexpected transport/cleanup errors too.
            if error is not None:
                failure = safe_failure(error)
                print(f"[Runner] Request cleanup error: {failure['type']}: {failure['message']}")

    async def _execute_request(self, msg, ws, operation, record):
        token = current_request.set(RequestContext(record['request_id']))
        record['_ws'] = ws
        try:
            await operation(msg, ws)
            if record['status'] not in ('failed', 'completed'):
                record['status'] = 'completed'
        except BaseException as error:
            record['status'] = 'failed'
            failure = safe_failure(error)
            await self.handler.broadcast('error', {'module': 'runner', 'request_id': record['request_id'],
                'message': failure['message'], 'failure_type': failure['type']})
        finally:
            try:
                await self._reply_status(ws, record)
            finally:
                record.pop('_ws', None)
                current_request.reset(token)

    async def _on_get_request_status(self, msg, ws):
        try:
            request_id = validate_request_id(msg.get('request_id'))
        except ValueError as error:
            await self._reply(ws, 'error', {'request_id': None, 'code': 'invalid_request_id', 'message': str(error)})
            return
        async with self._request_lock:
            record = self._requests.get(request_id)
            if record is None:
                try:
                    record = await asyncio.to_thread(self._find_stored_request, request_id, self._memory_request(request_id))
                except Exception:
                    record = {'request_id': request_id, 'status': 'unknown', 'reason': 'history_unavailable'}
        await self._reply_status(ws, record or {'request_id': request_id, 'status': 'unknown'})

    async def shutdown(self):
        self._closing = True
        async with self._request_lock:
            tasks = list(self._request_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        # A task cancelled before its first instruction never enters its finally.
        for record in list(self._requests.values()):
            if record['status'] in ('queued', 'running'):
                record['status'] = 'failed'
                await self.handler.broadcast('error', {'module': 'runner', 'request_id': record['request_id'],
                    'failure_type': 'CancelledError', 'message': '서버 종료로 대기 중인 요청이 취소되었습니다.'})
                await self._reply_status(record.pop('_ws', None), record)

    async def dispatch(self, msg: dict, ws):
        if not isinstance(msg, dict) or not isinstance(msg.get('topic'), str):
            return
        topic = msg['topic']
        operation = self.topic_map.get(topic)
        if operation is None:
            return
        if topic in EXECUTION_TOPICS:
            await self._accept_execution(msg, ws, operation)
            return
        try:
            await operation(msg, ws)
        except Exception as error:
            failure = safe_failure(error)
            print(f"[Runner] Dispatch Error: {failure['type']}: {failure['message']}")
            payload = {'module': 'runner', 'message': failure['message']}
            if ws is None:
                await self.handler.broadcast('error', payload)
            else:
                await self._reply(ws, 'error', payload)

    # ------------------------------------------------------------------
    # [Helper Methods]
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_query_file(base_dir: Path, file_name: str, suffix: str) -> Path:
        """Resolve a client supplied file name inside base_dir.

        The name arrives over an unauthenticated socket, so it must stay within the
        query directory. '../' escapes and absolute paths are both rejected.
        """
        if not file_name:
            raise ValueError("file_name must be provided")
        supplied_path = Path(file_name)
        if supplied_path.is_absolute() or supplied_path.suffix != suffix:
            raise NotAllowedQueryFileException(file_name)

        base = base_dir.resolve()
        target = (base / supplied_path).resolve()
        if not target.is_relative_to(base):
            raise NotAllowedQueryFileException(file_name)
        if not target.is_file():
            raise FileNotFoundError(f"Query file not found: {target}")
        return target

    async def _broadcast_rag_result(self, query_ids: List[str]):
        cont = self.engine.containers[self.flow_id]

        context = current_request.get()
        if context is not None:
            for query_id in query_ids:
                if query_id in cont.storage.results:
                    state = cont.storage.results[query_id]
                    if not isinstance(getattr(state, 'run_metadata', None), dict):
                        state.run_metadata = {}
                    state.run_metadata['request_id'] = context.request_id
        states_payload = {
            qid: cont.storage.results[qid].serialize()
            for qid in query_ids
            if qid in cont.storage.results.keys()
        }

        persisted = False
        history_key = None
        try:
            current_ts = time.time()
            results = [cont.storage.results[qid] for qid in query_ids if qid in cont.storage.results.keys()]
            history_key = update_history(self.flow_id, current_ts, results)
            persisted = True
            print(f"[Runner] History updated: {len(results)} results saved.")
        except Exception as e:
            failure = safe_failure(e)
            print(f"[Runner] Error updating history: {failure['type']}: {failure['message']}")
            await self.handler.broadcast('error', {
                'module': 'history', 'message': '실행 결과를 디스크에 저장하지 못했습니다. 현재 결과는 메모리에만 있습니다.',
                'failure_type': failure['type'],
            })

        if context is not None:
            record = self._requests.get(context.request_id)
            if record is not None:
                record.update(self._restored_record(context.request_id, states_payload, persisted=persisted))
                if not persisted:
                    record['status'] = 'failed'
        await self.handler.broadcast("rag-result-data", {
            "ts": history_key or _ts_str(),
            "persisted": persisted,
            "storage": {"flow_id": cont.flow_id, "states": states_payload},
        })

    async def _broadcast_container_topology(self):
        try:
            cont = self.engine.containers[self.flow_id]
            edges: List[Tuple[str, str]] = getattr(cont.storage, "flow_graph", [])
            await self.handler.broadcast("rag-container", {
                "rag-container": edges,
                "module_ids": list(getattr(cont, 'modules', {})),
            })
        except Exception as e:
            failure = safe_failure(e)
            print(f"[Runner] Error broadcasting topology: {failure['type']}: {failure['message']}")

    async def _run_and_broadcast(self, operation, query_num=None):
        """Broadcast every newly stored State, including executions that raise."""
        async with self._execution_lock:
            context = current_request.get()
            if context is not None:
                record = self._requests[context.request_id]
                record['status'] = 'running'
                await self._reply_status(record.get('_ws'), record)
            if query_num is not None:
                await self._rag_on_run(query_num)
            container = self.engine.containers[self.flow_id]
            previous_query_ids = set(container.storage.results)
            try:
                return await operation()
            finally:
                new_query_ids = [
                    query_id
                    for query_id in container.storage.results
                    if query_id not in previous_query_ids
                ]
                if new_query_ids:
                    await self._broadcast_rag_result(new_query_ids)

    async def _rag_on_run(self, query_num: int):
        await self.handler.broadcast("rag-on", {
            "ts": _ts_str(),
            "query-num": int(query_num),
        })
        context = current_request.get()
        if context is not None:
            context.preparation_sent = True

    # ------------------------------------------------------------------
    # [Handlers]
    # ------------------------------------------------------------------

    async def _on_run_rag_file_query(self, msg: dict, ws):
        QUERY_DIR = Path(os.getcwd()) / 'datas/queries/custom'
        settings = msg.get("settings") or {}
        file_path = self._resolve_query_file(QUERY_DIR, settings.get("file_name"), '.txt')

        queries = read_queries(file_path)

        await self._run_and_broadcast(
            lambda: self.engine.async_invoke_batch(queries, flow_ids=[self.flow_id]), query_num=len(queries)
        )

    async def _on_run_rag_llm_query(self, msg: dict, ws):
        QUERY_DIR = Path(os.getcwd()) / 'datas/queries/generated'
        settings = msg.get("settings") or {}
        file_path = self._resolve_query_file(QUERY_DIR, settings.get("file_name"), '.json')

        queries = read_queries(file_path, generated=True)

        await self._run_and_broadcast(
            lambda: self.engine.async_invoke_batch(queries, flow_ids=[self.flow_id]), query_num=len(queries)
        )

    async def _on_test_query(self, msg: dict, ws):
        query = msg.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("`query` must be a non-empty string.")

        await self._run_and_broadcast(
            lambda: self.engine.async_invoke(query, flow_ids=[self.flow_id]), query_num=1
        )

    async def _generated_query_files(self, msg, ws):
        base_dir = Path(os.getcwd()) / 'datas/queries/generated'
        file_list = []
        try:
            if base_dir.exists() and base_dir.is_dir():
                for p in sorted(base_dir.rglob("*.json")):
                    file_list.append(p.relative_to(base_dir).as_posix())
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
                    file_list.append(p.relative_to(base_dir).as_posix())
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
            failure = safe_failure(e)
            print(f"[Backend] Error in _start_react: {failure['type']}: {failure['message']}")

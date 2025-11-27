import datetime as dt
import json
import os
import traceback
from typing import Dict, Tuple, List
from pathlib import Path

from ragang.core.utils.cli import get_history
from ragang.exceptions.user.cli import NotAllowedQueryFileException


def _ts_str() -> str:
    kst = dt.timezone(dt.timedelta(hours=9))
    return dt.datetime.now(tz=kst).strftime("%Y%m%d-%H:%M")


class Runner:
    """
    - FlowEngine과 socket handler를 연결
    - topic_map: { topic(str) -> handler(async fn) }
    - dispatch(msg, ws): topic_map을 통해 msg 처리
    - 컨테이너(=flow_id)의 모듈 상태(start, end) 및 결과(history 일부)를 socket handler로 브로드캐스트
    """

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
            "custom-query-files": self._custom_query_files
        }

    # 모듈 상태(start, end) 브로드캐스트 -> 엔진/모듈 실행 지점에서 호출
    def _install_status_callback(self):
        cont = self.engine.containers[self.flow_id]

        async def on_status_async(module_id: str, statu: str):
            await self.handler.broadcast("module-statu", {
                "module": module_id,
                "statu": statu
            })

        # 컨테이너의 storage에 콜백 주입 (engine이 모듈 실행시 여기 콜백을 호출)
        setattr(cont.storage, "_on_module_status", on_status_async)

    async def setup_handlers(self):
        await self._broadcast_container_topology()

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

    async def _broadcast_container_topology(self):
        cont = self.engine.containers[self.flow_id]
        edges: List[Tuple[str, str]] = getattr(cont.storage, "flow_graph", [])
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

    # query 파일 (txt)에서 줄바꿈 기준으로 질의들을 뽑아 배치 실행
    async def _on_run_rag_file_query(self, msg: dict, ws):
        # user_workspace/datas/queries/custom/을 base로 이 위체에서의 query file 상대경로를 받아야 함
        QUERY_DIR = Path(os.getcwd()) / 'datas/queries/custom'  # custom query base file path

        settings = msg.get("settings") or {}

        file_name = settings.get("file_name")
        if not file_name:
            raise ValueError("file_name must be provided when using 'made-query'")

        file_path = QUERY_DIR / file_name
        if not file_path.is_file():
            raise FileNotFoundError(f"Query file not found: {file_path}")

        # check file suffix
        if file_name.suffix != '.txt':
            raise NotAllowedQueryFileException(file_name)

        queries = []
        with open(file_path, "r", encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]

        if not queries:
            raise ValueError("No queries extracted for execution.")

        results = await self.engine.async_invoke_batch(queries, flow_ids=[self.flow_id])
        query_ids = list(results.get(self.flow_id, {}).keys())
        await self._broadcast_rag_result(query_ids)

    # LLM 생성 query
    async def _on_run_rag_llm_query(self, msg: dict, ws):
        # 정해진 쿼리 폴더
        QUERY_DIR = Path(os.getcwd()) / 'datas/queries/generated'  # generated query base file path

        settings = msg.get("settings") or {}

        file_name = settings.get("file_name")
        if not file_name:
            raise ValueError("file_name must be provided when using 'made-query'")

        file_path = QUERY_DIR / file_name
        if not file_path.is_file():
            raise FileNotFoundError(f"Query file not found: {file_path}")

        # check file suffix
        if file_name.suffix != '.json':
            raise NotAllowedQueryFileException(file_name)

        queries = []
        with open(file_path, "r", encoding="utf-8") as f:
            # load queries
            data = json.load(f)
            query = data['query']
            for q in query:
                queries.append(q['query'])
            # queries = [line.strip() for line in f if line.strip()]

        if not queries:
            raise ValueError("No queries extracted for execution.")

        results = await self.engine.async_invoke_batch(queries, flow_ids=[self.flow_id])
        query_ids = list(results.get(self.flow_id, {}).keys())
        await self._broadcast_rag_result(query_ids)

    # test query: 단일 질의를 즉시 실행해 결과 송신
    async def _on_test_query(self, msg: dict, ws):
        query = msg.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("`query` must be a non-empty string.")

        results = await self.engine.async_invoke(query, flow_ids=[self.flow_id])
        query_ids = list(results.get(self.flow_id, {}).keys())
        await self._broadcast_rag_result(query_ids)

    # rag가 실행을 시작하였을 때 실행할 query 전체 개수와 함께 시작 알람 송신 -> rag가 실행되면 프론트에서 rag실행이 끝날 때 까지 화면 정지(프로그래스 바만)
    async def _rag_on_run(self, query_num: int):
        await self.handler.broadcast("rag-on", {
            "ts": _ts_str(),
            "query-num": int(query_num),
        })

    # genertor을 통해 만든 query file 리스트를 송신(data/generted_query 폴더에 있는 파일 이름들을 list로 만들어 송신)
    #   -> 프론트에서 generted query list를 출력하여 사용자가 선택할 때 이용
    async def _end_query(self, query_id: str):
        await self.handler.broadcast("ended-query", {
            "ts": _ts_str(),
            "end-query": query_id,
        })

    # rag continer가 하나의 query에 대해 실행이 완료될 때마다 해당 query_id 송신 -> 프로그래스 바에 사용
    async def _generated_query_files(self):
        base_dir = Path(os.getcwd()) / 'datas/queries/generated'
        file_list = []
        try:
            if base_dir.exists() and base_dir.is_dir():
                for p in sorted(base_dir.rglob("*.json")):
                    file_list.append(str(p.as_posix()))
        except Exception:
            file_list = []

        await self.handler.broadcast("generated-query-files", {
            "ts": _ts_str(),
            "files": file_list
        })

    async def _custom_query_files(self):
        # send custom query file list in user_workspace/datas/queries/
        base_dir = Path(os.getcwd()) / 'datas/queries/custom'
        file_list = []
        try:
            if base_dir.exists() and base_dir.is_dir():
                for p in sorted(base_dir.rglob("*.txt")):
                    file_list.append(str(p.as_posix()))
        except Exception:
            file_list = []
        await self.handler.broadcast("custom-query-files", {
            "ts": _ts_str(),
            "files": file_list
        })

    async def _start_react(self, msg: dict, ws):
        flow_id = msg.get("flow_id")
        history = get_history(flow_id)

        await self.handler.broadcast("history", {
            "ts": _ts_str(),
            "history": history
        })

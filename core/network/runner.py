import datetime as dt
import traceback
from typing import Dict, Tuple, List

from core.utils.query_generator import generate_query_from_data

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

    # query_id list로 해당 결과만 브로드캐스트
    # async def _broadcast_rag_result(self, query_ids: List[str]):
    #     cont = self.engine.containers[self.flow_id]
    #     hist = {
    #         qid: st.serialize()
    #         for qid, st in cont.storage.history.items()
    #         if qid in query_ids
    #     }
    #     await self.handler.broadcast("rag-result-data", {
    #         "ts": _ts_str(),
    #         "storage": {
    #             "flow_id": cont.storage.flow_id,
    #             "history": hist
    #         }
    #     })

    async def _broadcast_rag_result(self, query_ids: List[str]):
        cont = self.engine.containers[self.flow_id]
        states_payload = {
            qid: cont.states[qid].serialize()
            for qid in query_ids
            if qid in cont.states
        }
        await self.handler.broadcast("rag-result-data", {
            "ts": _ts_str(),
            "storage": {
                "flow_id": cont.flow_id,
                "states": states_payload
            }
        })


    # # 컨테이너 토폴로지 브로드캐스트
    # async def _broadcast_container_topology(self):
    #     cont = self.engine.containers[self.flow_id]
    #     edges: List[Tuple[str, str]] = []
    #     for m in getattr(cont, "modules", []):
    #         try:
    #             # direction 객체에서 다음 모듈 id 목록을 받아와 (src, dst) 형식으로 추가
    #             for dst in m.direction.get_directions():
    #                 edges.append((m.module_id, dst))
    #         except Exception:
    #             continue
    #     await self.handler.broadcast("rag-container", {"rag-container": edges})

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
        files = msg.get("files") or []
        if not isinstance(files, list):
            files = []

        queries: List[str] = []
        for file_path in files:
            with open(file_path, "r", encoding="utf-8") as f:
                queries.extend([line.strip() for line in f if line.strip()])

        if not queries:
            raise ValueError("No queries extracted from files.")

        # 선택한 flow_id 컨테이너만 실행
        results = self.engine.invoke_batch(queries, flow_ids=[self.flow_id])
        # 반환 포맷: { flow_id: { qid1:{...}, qid2:{...}, ... } }
        query_ids = list(results.get(self.flow_id, {}).keys())
        await self._broadcast_rag_result(query_ids)

    # LLM 생성 query
    async def _on_run_rag_llm_query(self, msg: dict, ws):
        settings = msg.get("settings") or {}
        llm_option = (settings.get("llm_option") or "").lower()

        cont = self.engine.containers[self.flow_id]

        if llm_option in ("새 질문 생성", "make-query"):
            file_path = settings.get("file_path", "./data/default.txt")
            queries = generate_query_from_data(
                getattr(cont, "llm_adapter", None),
                file_path
            )
            if not isinstance(queries, list):
                queries = [queries]
            # 생성된 질의를 내부 저장(선택 사용)
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

        results = self.engine.invoke_batch(queries, flow_ids=[self.flow_id])
        query_ids = list(results.get(self.flow_id, {}).keys())
        await self._broadcast_rag_result(query_ids)

    # test query: 단일 질의를 즉시 실행해 결과 송신
    async def _on_test_query(self, msg: dict, ws):
        query = msg.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("`query` must be a non-empty string.")

        results = self.engine.invoke(query, flow_ids=[self.flow_id])
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
    async def _end_query(self, query_id: int):
        await self.handler.broadcast("ended-query", {
            "ts": _ts_str(),
            "end-query": int(query_id),
        })
    
    # rag continer가 하나의 query에 대해 실행이 완료될 때마다 해당 query_id 송신 -> 프로그래스 바에 사용
    async def _generated_query_files(self, query_num: int):
        from pathlib import Path
        base_dir = Path("data/generated_query")
        file_list = []
        try:
            if base_dir.exists() and base_dir.is_dir():
                for p in sorted(base_dir.rglob("*.txt")):
                    file_list.append(str(p.as_posix()))
        except Exception:
            file_list = []

        await self.handler.broadcast("generated-query-files", {
            "ts": _ts_str(),
            "files": file_list
        })

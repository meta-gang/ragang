import argparse
import asyncio
import importlib.util
import sys
from pathlib import Path
import websockets

from core.network.socket_handler import SocketHandler
from core.network.runner import Runner
from core.bases.abstracts.base_engine import FlowEngine
from core.network.socket_sender import SocketSender


def _is_rag_container_instance(obj) -> bool:
    try:
        from container.rag_container import RAGContainer
        return isinstance(obj, RAGContainer)
    except Exception:
        return False


def load_engine_with_flow(py_path: str, flow_id: str) -> FlowEngine:
    """
    주어진 파일에서 flow_id에 해당하는 RAGContainer를 찾고,
    - 모듈에 engine이 있으며 해당 flow_id를 포함하면 그 engine을 그대로 반환
    - 그렇지 않으면 flow_id에 매칭되는 RAGContainer만 골라 FlowEngine([rag])로 감싸 반환
    """
    path = Path(py_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"RAG file not found: {path}")

    mod_name = f"rag_user_{abs(hash(str(path)))}"
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)

    if hasattr(module, "engine"):
        engine = getattr(module, "engine")
        containers = getattr(engine, "containers", {})
        if isinstance(containers, dict) and flow_id in containers:
            return engine
    
    candidates = []
    for name, obj in vars(module).items():
        if _is_rag_container_instance(obj):
            try:
                if getattr(obj, "flow_id", None) == flow_id:
                    candidates.append(obj)
            except Exception:
                continue

    if not candidates:
        raise AttributeError(
            f"No RAGContainer with flow_id='{flow_id}' found in {path.name}."
        )
    if len(candidates) > 1:
        raise RuntimeError(
            f"Multiple RAGContainers with flow_id='{flow_id}' found. Please expose exactly one."
        )

    return FlowEngine([candidates[0]])


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rag-file", type=str, default=str(Path("./usage/linear_graph/main.py").resolve()))
    parser.add_argument("--flow-id", type=str, default="linear_graph")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()

    engine = load_engine_with_flow(args.rag_file, flow_id=args.flow_id)
    print(f"[Engine] loaded from {args.rag_file} (flow_id={args.flow_id})")

    handler = SocketHandler()
    engine.set_ws_sender(SocketSender(handler))

    runner = Runner(handler, engine=engine, flow_id=args.flow_id)
    await runner.setup_handlers()

    async def _on_message(msg: dict, ws, h: SocketHandler):
        await runner.dispatch(msg, ws)

    handler.on_message = _on_message

    async with websockets.serve(handler.handle_connection, args.host, args.port):
        print(f"[WS] listening on ws://{args.host}:{args.port}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
import argparse
import asyncio
import importlib.util
import sys
from pathlib import Path
import websockets

from core.network.socket_handler import SocketHandler
from core.network.runner import Runner


def load_rag_from_path(py_path: str, preferred_symbol: str = "rag"):
    """
    주어진 파일 경로에서 RAGContainer 인스턴스를 로드
    """
    path = Path(py_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"RAG file not found: {path}")

    # 고유 모듈명으로 동적 import
    mod_name = f"rag_user_{abs(hash(str(path)))}"
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import RAGcontainer from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)

    # 'rag' 심볼 우선 사용
    if hasattr(module, preferred_symbol):
        candidate = getattr(module, preferred_symbol)
        _ensure_instance(candidate)
        return candidate

    # fallback: 모듈 전역에서 BaseContainer 인스턴스 탐색
    instances = []
    for name, obj in vars(module).items():
        if _is_rag_container_instance(obj):
            instances.append((name, obj))

    if not instances:
        raise AttributeError(
            f"No '{preferred_symbol}' found and no RAGContainer instance discovered in {path.name}."
        )
    if len(instances) > 1:
        names = ", ".join(n for n, _ in instances)
        raise RuntimeError(
            f"Multiple instances found: {names}. Please expose exactly one or name it '{preferred_symbol}'."
        )

    _, rag = instances[0]
    return rag


def _is_rag_container_instance(obj) -> bool:
    try:
        from container.rag_container import RAGContainer
        if isinstance(obj, RAGContainer):
            return True
    except Exception:
        pass
    return False


def _ensure_instance(candidate):
    if callable(candidate):
        raise TypeError("'rag' must be an instance (not a function/class).")
    if not _is_rag_container_instance(candidate):
        raise TypeError(f"'rag' is not a valid RAGContainer instance. Got {type(candidate)}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rag-file", type=str, default=str(Path("./usage/main.py").resolve()))
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()

    rag = load_rag_from_path(args.rag_file, preferred_symbol="rag")
    print(f"[RAG] loaded from {args.rag_file}")

    handler = SocketHandler()
    runner = Runner(handler, rag_container=rag)
    runner.setup_handlers()

    async def _on_message(msg: dict, ws, h: SocketHandler):
        await runner.dispatch(msg, ws)

    handler.on_message = _on_message

    async with websockets.serve(handler.handle_connection, args.host, args.port):
        print(f"[WS] listening on ws://{args.host}:{args.port}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
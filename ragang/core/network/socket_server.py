import asyncio
import websockets

from ragang.core.network.socket_handler import SocketHandler
from ragang.core.network.runner import Runner
from ragang.core.network.socket_sender import SocketSender
from ragang.core.utils.modules import create_engine


async def main(root_path: str, flow_id: str, host: str, port: int):
    engine = create_engine(root_path, flow_id)

    handler = SocketHandler()
    engine.set_ws_sender(SocketSender(handler))

    runner = Runner(handler, engine=engine, flow_id=flow_id)
    await runner.setup_handlers()

    async def _on_message(msg: dict, ws):
        await runner.dispatch(msg, ws)

    handler.on_message = _on_message

    async with websockets.serve(handler.handle_connection, host, port):
        await asyncio.Future()

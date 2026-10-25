import asyncio
import logging
import hmac
from http import HTTPStatus
from urllib.parse import parse_qs, urlsplit

import websockets

from ragang.core.network.socket_handler import SocketHandler
from ragang.core.network.runner import Runner
from ragang.core.network.socket_sender import SocketSender
from ragang.core.utils.modules import create_engine


async def main(root_path: str, flow_id: str, host: str, port: int,
               session_token: str | None = None, allowed_origins=None, on_ready=None):
    # disable websocket log to appear inside user console
    # further we should handle these logs with some log file
    logging.getLogger('websockets').setLevel(logging.CRITICAL)

    engine = create_engine(root_path, flow_id)

    handler = SocketHandler()
    engine.set_ws_sender(SocketSender(handler))

    runner = Runner(handler, engine=engine, flow_id=flow_id)
    await runner.setup_handlers()

    async def _on_message(msg: dict, ws):
        await runner.dispatch(msg, ws)

    handler.on_message = _on_message

    async def authenticate(connection, request):
        if session_token is not None:
            supplied = parse_qs(urlsplit(request.path).query).get('session_token', [])
            if len(supplied) != 1 or not hmac.compare_digest(supplied[0], session_token):
                return connection.respond(HTTPStatus.FORBIDDEN, 'Dashboard session required')
        return None

    origins = allowed_origins if allowed_origins is not None else [
        'http://127.0.0.1:8080', 'http://localhost:8080', None,
    ]
    async with websockets.serve(handler.handle_connection, host, port,
                                 origins=origins, process_request=authenticate,
                                 max_size=2**20):
        if on_ready is not None:
            on_ready()
        await asyncio.Future()

import asyncio
import os
import signal
import threading
import webbrowser
from argparse import Namespace
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

from ragang.core.utils.ansi_styler import ANSIStyler
import ragang.core.network.socket_server as ws
from ragang.exceptions.frameworks.cli import HTMLNotFoundException

stop_event = threading.Event()


def run_web_cli(host: str, port: int):
    # serve react build file
    web_path: Path = Path(__file__).parent.parent.parent / 'web'
    if not web_path.exists():
        raise HTMLNotFoundException()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web_path), **kwargs)

        # disable log
        def log_message(self, format, *args):
            pass

    # bind to the advertised host only; the dashboard serves local evaluation results
    # and must not be reachable from the rest of the network
    server = HTTPServer((host, port), Handler)
    server.serve_forever()


def run(args: Namespace):
    host: str = "127.0.0.1"
    ws_port: int = 8081
    web_port: int = 8080
    flow_id: str = args.flow_id
    user_root: Path = Path(os.getcwd())

    # run ws server
    ws_thread = threading.Thread(target=lambda: asyncio.run(ws.main(user_root, flow_id, host, ws_port)), daemon=True)
    ws_thread.start()

    # run front
    web_thread = threading.Thread(target=run_web_cli, args=(host, web_port), daemon=True)
    web_thread.start()

    webbrowser.open(f"http://{host}:{web_port}")  # open web browser

    print(ANSIStyler.style(f"[Visualize] Dashboard running at 'http://{host}:{web_port}'",
                           fore_color='light-yellow',
                           font_style='bold'))
    print(ANSIStyler.style("Press Ctrl+C to stop...",
                           fore_color='yellow'))

    try:
        signal.signal(signal.SIGINT, lambda *_: stop_event.set())
        signal.signal(signal.SIGTERM, lambda *_: stop_event.set())

        stop_event.wait()  # main thread will wait keyboard interrupt without spinning
    finally:
        print(ANSIStyler.style("\nBye!",
                               fore_color='yellow'))

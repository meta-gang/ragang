import asyncio
import os
import json
import secrets
import queue
import signal
import threading
import webbrowser
from argparse import Namespace
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

from ragang.core.utils.ansi_styler import ANSIStyler
import ragang.core.network.socket_server as ws
from ragang.exceptions.frameworks.cli import HTMLNotFoundException
from ragang.evaluator import safe_failure

stop_event = threading.Event()


def dashboard_handler(web_path: Path, host: str, port: int, session_token: str | None = None):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web_path), **kwargs)

        def end_headers(self):
            self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-store')
            super().end_headers()

        def do_GET(self):
            allowed_hosts = {f'{host}:{port}', f'localhost:{port}'}
            if self.headers.get('Host') not in allowed_hosts:
                self.send_error(403, 'Local dashboard host required')
                return
            if self.headers.get('Sec-Fetch-Site') in {'cross-site', 'same-site'}:
                self.send_error(403, 'Same-origin dashboard request required')
                return
            request_path = self.path.split('?', 1)[0]
            if request_path == '/ragang-session.js':
                value = json.dumps(session_token)
                payload = f'window.__RAGANG_SESSION_TOKEN__ = {value};'.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/javascript; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if request_path in {'/', '/index.html'}:
                content = (web_path / 'index.html').read_text(encoding='utf-8')
                content = content.replace('</head>', '<script src="./ragang-session.js"></script></head>')
                payload = content.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            super().do_GET()

        # disable log
        def log_message(self, format, *args):
            pass

    return Handler


def run_web_cli(host: str, port: int, session_token: str | None = None, on_ready=None):
    web_path: Path = Path(__file__).parent.parent.parent / 'web'
    if not web_path.exists():
        raise HTMLNotFoundException()

    # bind to the advertised host only; the dashboard serves local evaluation results
    # and must not be reachable from the rest of the network
    server = HTTPServer((host, port), dashboard_handler(web_path, host, port, session_token))
    if on_ready is not None:
        on_ready()
    try:
        server.serve_forever()
    finally:
        if hasattr(server, 'server_close'):
            server.server_close()


def run(args: Namespace):
    host: str = "127.0.0.1"
    ws_port: int = 8081
    web_port: int = 8080
    flow_id: str = args.flow_id
    user_root: Path = Path(os.getcwd())
    session_token = secrets.token_urlsafe(32)
    stop_event.clear()
    startup = queue.Queue()

    def launch(name, operation):
        try:
            operation(lambda: startup.put((name, None)))
        except Exception as error:
            startup.put((name, safe_failure(error)))
            stop_event.set()

    # run ws server
    ws_thread = threading.Thread(target=launch, args=('WebSocket', lambda ready: asyncio.run(
        ws.main(user_root, flow_id, host, ws_port, session_token=session_token, on_ready=ready))), daemon=True)
    ws_thread.start()

    # run front
    web_thread = threading.Thread(target=launch, args=('HTTP', lambda ready:
        run_web_cli(host, web_port, session_token, on_ready=ready)), daemon=True)
    web_thread.start()

    services = set()
    while len(services) < 2:
        try:
            name, failure = startup.get(timeout=30)
        except queue.Empty:
            raise RuntimeError('Dashboard startup timed out; check the local model and ports 8080/8081') from None
        if failure:
            raise RuntimeError(f"{name} startup failed ({failure['type']}): {failure['message']}")
        services.add(name)

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

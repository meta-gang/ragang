"""User-facing contracts for persistence, safe local startup, and failures."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import http.client
from http.server import HTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import websockets
from ragang.cli_script.run.main import run
from ragang.cli_script.show.main import dashboard_handler
from ragang.core.bases.abstracts.base_engine import FlowEngine
from ragang.core.bases.datas.linker import Linker
from ragang.core.bases.datas.state import State
from ragang.core.network.socket_server import main as serve_ws
from ragang.core.utils.cli import get_history, update_history, read_queries
from ragang.container import RAGContainer
from ragang.modules.custom import CustomModule
from tests.test_core_regressions import Starter, Output


class SometimesFails(CustomModule):
    async def execute(self, query):
        if query == 'bad':
            raise RuntimeError('synthetic module failure')
        return {'gen': 'answer'}


class WorkflowAcceptanceTests(unittest.TestCase):
    def test_dashboard_reports_startup_failure_before_opening_browser(self):
        import ragang.cli_script.show.main as show
        async def unavailable(*args, **kwargs):
            raise RuntimeError('synthetic backend unavailable')
        def fake_web(host, port, session_token=None, on_ready=None):
            on_ready()
        with patch.object(show.ws, 'main', unavailable), patch.object(show, 'run_web_cli', fake_web), \
                patch.object(show.webbrowser, 'open') as opened:
            with self.assertRaisesRegex(RuntimeError, 'WebSocket startup failed'):
                show.run(SimpleNamespace(flow_id='audit'))
            opened.assert_not_called()

    def test_generated_input_schema_and_safe_flow_names(self):
        invalid = [None, [], {'query': 'question'}, {'query': [None]},
                   {'query': [{'query': ''}]}, {'query': [42]}, {'query': []}]
        with tempfile.TemporaryDirectory() as temp:
            previous = os.getcwd()
            os.chdir(temp)
            try:
                path = Path('queries.json')
                for value in invalid:
                    path.write_text(json.dumps(value))
                    with self.subTest(value=value), self.assertRaises(ValueError):
                        read_queries(path, generated=True)
                path.write_text(json.dumps({'query': [' first ', {'query': ' second '}]}))
                self.assertEqual(read_queries(path, generated=True), ['first', 'second'])
                state = State('one', 'question')
                state.run_metadata = {'run_id': None}
                update_history('production-rag', 1, [state])
                saved = next(iter(next(iter(get_history('production-rag').values())).values()))
                self.assertIsInstance(saved['run_metadata']['run_id'], str)
                for flow in ('../escape', '/absolute', '.', '..', 'a\\b', ''):
                    with self.subTest(flow=flow), self.assertRaises(ValueError):
                        get_history(flow)
            finally:
                os.chdir(previous)

    def test_disk_save_failure_is_visible_to_dashboard(self):
        from ragang.core.network.runner import Runner
        class Handler:
            def __init__(self): self.events = []
            async def broadcast(self, topic, payload): self.events.append((topic, payload))
        state = State('one', 'question')
        storage = SimpleNamespace(flow_graph=[], results={'one': state})
        engine = SimpleNamespace(containers={'audit': SimpleNamespace(storage=storage, flow_id='audit')})
        handler = Handler()
        runner = Runner(handler, engine, 'audit')
        with patch('ragang.core.network.runner.update_history', side_effect=OSError('synthetic failure')), redirect_stdout(io.StringIO()):
            asyncio.run(runner._broadcast_rag_result(['one']))
        self.assertEqual(handler.events[0][0], 'error')
        self.assertFalse(handler.events[-1][1]['persisted'])
        self.assertEqual(handler.events[-1][1]['storage']['states']['one']['query'], 'question')

    def test_cli_partial_and_total_failures_preserve_every_attempt(self):
        for questions in ('good\nbad\n', 'bad\n'):
            with self.subTest(questions=questions), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / 'datas/queries/custom').mkdir(parents=True)
                (root / 'datas/queries/custom/questions.txt').write_text(questions)
                cont = RAGContainer('audit', [Starter('starter', is_starter=True),
                                    SometimesFails('output', linker=Linker('starter'))])
                engine = FlowEngine([cont])
                previous = os.getcwd()
                try:
                    os.chdir(root)
                    with patch('ragang.cli_script.run.main.create_engine', return_value=engine), redirect_stdout(io.StringIO()):
                        with self.assertRaises((SystemExit, RuntimeError)):
                            run(SimpleNamespace(flow_id='audit', query_path='custom/questions.txt', save=True))
                    runs = get_history('audit')
                    states = [state for run_states in runs.values() for state in run_states.values()]
                    self.assertEqual(len(states), len(questions.splitlines()))
                    self.assertTrue(any(s['execution_summary']['terminated'] for s in states))
                finally:
                    os.chdir(previous)

    def test_history_same_second_unique_runs_and_concurrent_writers(self):
        with tempfile.TemporaryDirectory() as temp:
            previous = os.getcwd()
            os.chdir(temp)
            try:
                def save(index):
                    state = State(str(index), f'question {index}')
                    state.run_metadata = {'run_id': f'run-{index}'}
                    update_history('audit', 1_800_000_000.0, [state])
                with ThreadPoolExecutor(max_workers=4) as pool:
                    list(pool.map(save, range(12)))
                history = get_history('audit')
                self.assertEqual(len(history), 12)
                self.assertEqual(sum(len(states) for states in history.values()), 12)
                self.assertEqual(Path('history/audit.json').stat().st_mode & 0o777, 0o600)
            finally:
                os.chdir(previous)

    def test_history_repeated_delivery_updates_one_run(self):
        with tempfile.TemporaryDirectory() as temp:
            previous = os.getcwd()
            os.chdir(temp)
            try:
                first = State('one', 'first')
                second = State('two', 'second')
                first.run_metadata = {'run_id': 'shared'}
                second.run_metadata = {'run_id': 'shared'}
                update_history('audit', 1, [first])
                update_history('audit', 2, [first, second])
                history = get_history('audit')
                self.assertEqual(len(history), 1)
                self.assertEqual(len(next(iter(history.values()))), 2)
            finally:
                os.chdir(previous)

    def test_atomic_history_write_preserves_previous_file_on_replace_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            previous = os.getcwd()
            os.chdir(temp)
            try:
                update_history('audit', 1, [State('one', 'first')])
                before = Path('history/audit.json').read_bytes()
                with patch('ragang.core.utils.cli.os.replace', side_effect=OSError('synthetic disk failure')):
                    with self.assertRaises(OSError):
                        update_history('audit', 2, [State('two', 'second')])
                self.assertEqual(Path('history/audit.json').read_bytes(), before)
                self.assertFalse(list(Path('history').glob('.audit.*')))
            finally:
                os.chdir(previous)

    def test_existing_template_milvus_collection_is_read_only(self):
        path = Path(__file__).resolve().parents[1] / 'ragang/templates/init_template/config/load_adapters.py'
        spec = importlib.util.spec_from_file_location('audit_template', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        database = SimpleNamespace(has_collection=lambda _: True)
        with patch.object(module, 'MilvusAdapter', return_value=database):
            self.assertIs(module.__dict__['__init_milvus'](), database)
        database = SimpleNamespace(has_collection=lambda _: False)
        with patch.object(module, 'MilvusAdapter', return_value=database):
            with self.assertRaisesRegex(RuntimeError, 'separately'):
                module.__dict__['__init_milvus']()
        for invalid in ('api.example:11434', '127.0.0.1:11434/path', 'user:pass@localhost:11434'):
            with self.assertRaises(ValueError):
                module._loopback_endpoint(invalid)

    def test_new_project_runs_with_all_network_calls_blocked(self):
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / 'project'
            subprocess.run([sys.executable, '-c', 'from ragang.cli_script.entry import main; main()',
                            'init', str(project)], cwd=repository, check=True, capture_output=True)
            script = '''
from unittest.mock import patch
from argparse import Namespace
from ragang.cli_script.run.main import run
from ragang.core.utils.cli import get_history
with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')), patch('requests.post', side_effect=AssertionError('network forbidden')):
    run(Namespace(flow_id='sample_rag', query_path='custom/queries.txt', save=True))
assert get_history('sample_rag')
'''
            result = subprocess.run([sys.executable, '-c', script], cwd=project, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_http_bootstrap_same_origin_and_host_protection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'index.html').write_text('<head></head><body>dashboard</body>')
            server = HTTPServer(('127.0.0.1', 0), lambda *a, **k: dashboard_handler(
                root, '127.0.0.1', server.server_port, 'synthetic-session')(*a, **k))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
                conn.request('GET', '/')
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn(b'ragang-session.js', response.read())
                conn.request('GET', '/ragang-session.js', headers={'Sec-Fetch-Site': 'cross-site'})
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                conn.request('GET', '/ragang-session.js', headers={'Host': 'untrusted.example'})
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_websocket_rejects_foreign_origin_and_missing_session(self):
        async def exercise():
            cont = RAGContainer('audit', [Starter('starter', is_starter=True), Output('output', linker=Linker('starter'))])
            # Reserve an ephemeral port before launching the actual production server.
            import socket
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            with patch('ragang.core.network.socket_server.create_engine', return_value=FlowEngine([cont])):
                task = asyncio.create_task(serve_ws('.', 'audit', '127.0.0.1', port, session_token='synthetic-session'))
                try:
                    for _ in range(30):
                        try:
                            async with websockets.connect(f'ws://127.0.0.1:{port}?session_token=synthetic-session', origin='http://127.0.0.1:8080') as client:
                                await client.send(json.dumps({'topic': 'subscribe', 'topics': ['history']}))
                                await client.send(json.dumps({'topic': 'start!'}))
                                self.assertEqual(json.loads(await asyncio.wait_for(client.recv(), 2))['topic'], 'history')
                                break
                        except OSError:
                            await asyncio.sleep(.01)
                    else:
                        self.fail('server did not start')
                    for origin, suffix in [('https://untrusted.example', '?session_token=synthetic-session'),
                                           ('http://127.0.0.1:8080', '')]:
                        with self.assertRaises(websockets.exceptions.InvalidStatus):
                            async with websockets.connect(f'ws://127.0.0.1:{port}{suffix}', origin=origin):
                                pass
                finally:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
        with tempfile.TemporaryDirectory() as temp:
            previous = os.getcwd()
            os.chdir(temp)
            try:
                asyncio.run(exercise())
            finally:
                os.chdir(previous)


if __name__ == '__main__':
    unittest.main()

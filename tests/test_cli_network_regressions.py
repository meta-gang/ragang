from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import ragang.cli_script.entry as entry
import ragang.cli_script.show.main as show
from ragang.cli_script.init.main import run as run_init
from ragang.core.network.runner import Runner
from ragang.exceptions.user.cli import NoEntryPointException, NotAllowedQueryFileException
from ragang.core.utils.modules import load_user_containers


class CliNetworkRegressionTests(unittest.TestCase):
    def test_no_save_flag_parses_false(self):
        captured = {}

        def fake_run(args):
            captured["save"] = args.save

        argv = ["ragang", "run", "-Q", "queries.txt", "--no-save"]
        with patch.object(entry, "run_run", fake_run), patch.object(sys, "argv", argv):
            entry.main()
        self.assertFalse(captured["save"])

    def test_init_creates_nested_project_and_merges_gitignore_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "project"
            target.mkdir(parents=True)
            (target / ".gitignore").write_text("custom-entry\n", encoding="utf-8")

            run_init(SimpleNamespace(path=str(target)))

            rules = (target / ".gitignore").read_text(encoding="utf-8").splitlines()
            self.assertIn("custom-entry", rules)
            self.assertIn("__pycache__/", rules)
            self.assertIn("history/", rules)
            self.assertTrue((target / "manager.py").is_file())

    def test_missing_manager_preserves_actionable_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(NoEntryPointException):
                load_user_containers(tmp)

    def test_query_file_resolver_rejects_traversal_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            query_file = base / "ok.txt"
            query_file.write_text("question", encoding="utf-8")
            self.assertEqual(Runner._resolve_query_file(base, "ok.txt", ".txt"), query_file)

            for invalid in ("../escape.txt", str(query_file)):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(NotAllowedQueryFileException):
                        Runner._resolve_query_file(base, invalid, ".txt")

    def test_dashboard_http_server_binds_to_advertised_loopback(self):
        captured = {}

        class FakeServer:
            def __init__(self, address, handler):
                captured["address"] = address

            def serve_forever(self):
                return None

        old_cwd = os.getcwd()
        try:
            with patch.object(show, "HTTPServer", FakeServer):
                show.run_web_cli("127.0.0.1", 8080)
        finally:
            os.chdir(old_cwd)
        self.assertEqual(captured["address"], ("127.0.0.1", 8080))

    def test_dispatch_error_payload_does_not_leak_traceback(self):
        class Handler:
            def __init__(self):
                self.events = []

            async def broadcast(self, topic, payload):
                self.events.append((topic, payload))

        storage = SimpleNamespace(flow_graph=[])
        container = SimpleNamespace(storage=storage)
        engine = SimpleNamespace(containers={"flow": container})
        handler = Handler()
        runner = Runner(handler, engine, "flow")

        async def boom(msg, ws):
            raise RuntimeError("api_key=do-not-leak at /Users/example/private/file.txt")

        runner.topic_map = {"boom": boom}
        asyncio.run(runner.dispatch({"topic": "boom"}, None))

        topic, payload = handler.events[-1]
        self.assertEqual(topic, "error")
        self.assertIn("api_key=[REDACTED]", payload["message"])
        self.assertIn("[PATH]", payload["message"])
        self.assertNotIn("do-not-leak", payload["message"])
        self.assertNotIn("/Users/example", payload["message"])
        self.assertNotIn("traceback", payload)

    def test_history_load_error_is_redacted_without_secondary_failure(self):
        class Handler:
            async def broadcast(self, topic, payload):
                raise AssertionError("history must not be broadcast after a load failure")

        storage = SimpleNamespace(flow_graph=[])
        container = SimpleNamespace(storage=storage)
        engine = SimpleNamespace(containers={"flow": container})
        runner = Runner(Handler(), engine, "flow")
        output = io.StringIO()

        with patch(
            "ragang.core.network.runner.get_history",
            side_effect=RuntimeError("token=do-not-leak at /Users/example/private/history.json"),
        ), redirect_stdout(output):
            asyncio.run(runner._start_react({}, None))

        message = output.getvalue()
        self.assertIn("token=[REDACTED]", message)
        self.assertIn("[PATH]", message)
        self.assertNotIn("do-not-leak", message)
        self.assertNotIn("/Users/example", message)


if __name__ == "__main__":
    unittest.main()

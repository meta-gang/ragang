"""Executable README onboarding contracts, without model or DB services."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


class ReadmeExampleTests(unittest.TestCase):
    def _minimal_manager(self) -> str:
        text = README.read_text(encoding="utf-8")
        match = re.search(r"<!-- executable-example: minimal-manager -->\s*```python\n(.*?)\n```", text, re.DOTALL)
        self.assertIsNotNone(match, "README must identify its executable manager example")
        source = match.group(1)
        compile(source, "README:minimal-manager", "exec")
        return source

    def _cli(self, cwd: Path, *args: str):
        # The README example is tested through the real CLI parser and loader.
        # Model HTTP calls are blocked in the child process as a regression guard.
        code = """
from unittest.mock import patch
from ragang.cli_script.entry import main
with patch('requests.post', side_effect=AssertionError('README example attempted a model network call')), \
     patch('socket.socket.connect', side_effect=AssertionError('README example attempted a network connection')):
    main()
"""
        return subprocess.run([sys.executable, "-c", code, *args], cwd=cwd,
                              capture_output=True, text=True, timeout=30)

    def _project(self, directory: str) -> Path:
        project = Path(directory) / "example_project"
        created = self._cli(Path(directory), "init", str(project))
        self.assertEqual(created.returncode, 0, created.stderr)
        (project / "manager.py").write_text(self._minimal_manager(), encoding="utf-8")
        return project

    def test_readme_minimal_manager_runs_through_real_cli_and_saves_history(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self._project(directory)
            completed = self._cli(project, "run", "-F", "my_rag", "-Q", "custom/queries.txt")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            history = json.loads((project / "history" / "my_rag.json").read_text(encoding="utf-8"))
            states = [state for run in history.values() for state in run.values()]
            self.assertTrue(states)
            for state in states:
                self.assertEqual(state["execution_summary"]["termination_reason"], "answer")
                self.assertFalse(state["execution_summary"]["terminated"])
                packet = state["snapshots"]["rag"][-1]
                self.assertEqual(state["gen"], packet["data"]["ret_docs"][0])
                self.assertTrue(packet["performances"][0]["_Performance__did_eval"])
                self.assertEqual(packet["performances"][0]["_Performance__metric"], "Jaccard Similarity Metric")

    def test_readme_manager_supports_show_startup_and_live_engine_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self._project(directory)
            code = """
import importlib
from pathlib import Path
from unittest.mock import patch
from ragang.cli_script.entry import main
from ragang.core.utils.modules import create_engine
show = importlib.import_module('ragang.cli_script.show.main')
checked = []
async def websocket_contract(root_path, flow_id, host, port, session_token=None, on_ready=None):
    assert host == '127.0.0.1' and port == 8081
    assert isinstance(session_token, str) and session_token
    engine = create_engine(root_path, flow_id)
    result = await engine.async_invoke('RAGANG은 무엇인가요?')
    assert result[flow_id]
    checked.append('engine')
    on_ready()
def http_contract(host, port, session_token=None, on_ready=None):
    assert host == '127.0.0.1' and port == 8080
    assert isinstance(session_token, str) and session_token
    checked.append('http-startup')
    on_ready()
with patch.object(show.ws, 'main', websocket_contract), patch.object(show, 'run_web_cli', http_contract), \\
     patch.object(show.webbrowser, 'open') as opened, patch.object(show.stop_event, 'wait', return_value=True), \\
     patch.object(show.signal, 'signal'), patch('requests.post', side_effect=AssertionError('Model network call')), \
     patch('socket.socket.connect', side_effect=AssertionError('README example attempted a network connection')):
    main()
    opened.assert_called_once_with('http://127.0.0.1:8080')
assert set(checked) == {'engine', 'http-startup'}
"""
            result = subprocess.run([sys.executable, "-c", code, "show", "-F", "my_rag"],
                                    cwd=project, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_readme_local_document_links_exist(self):
        text = README.read_text(encoding="utf-8")
        targets = re.findall(r"\[[^\]]+\]\(([^\s)]+)(?:\s+[^)]*)?\)", text)
        for target in targets:
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            local = unquote(target.split("#", 1)[0].split("?", 1)[0])
            with self.subTest(target=target):
                self.assertTrue((ROOT / local).exists(), f"Broken local README link: {target}")


if __name__ == "__main__":
    unittest.main()

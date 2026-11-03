"""Black-box contracts for selection, failure reporting, and bounded execution."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/verify_usability.py"


class UsabilityRunnerTests(unittest.TestCase):
    def invoke(self, directory: Path, *arguments: str, env=None):
        report = directory / "result.json"
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--output", str(report), *arguments],
            cwd=directory, env=env, capture_output=True, text=True, timeout=20,
        )
        return completed, json.loads(report.read_text(encoding="utf-8"))

    def fake_npm(self, directory: Path, source: str):
        ui = directory / "private-ui-checkout"
        (ui / "node_modules").mkdir(parents=True)
        (ui / "package.json").write_text("{}", encoding="utf-8")
        executable = directory / "npm"
        executable.write_text(f"#!{sys.executable}\n{source}\n", encoding="utf-8")
        executable.chmod(0o700)
        env = dict(os.environ, PATH=str(directory) + os.pathsep + os.environ.get("PATH", ""))
        return ui, env

    def test_selected_check_runs_from_another_directory_and_reports_its_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed, report = self.invoke(Path(temporary), "--checks", "compile")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(report["status"], "passed")
        self.assertEqual([item["check"] for item in report["checks"]], ["compile"])
        self.assertFalse(report["browser_automation_performed"])
        self.assertFalse(report["human_user_testing_performed"])
        self.assertNotIn("ui", report["sources"])

    @unittest.skipIf(os.name == "nt", "The isolated executable fixture uses a POSIX shebang")
    def test_failed_child_logs_and_parent_credentials_never_enter_the_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            ui, env = self.fake_npm(directory, """
import os, sys
print('synthetic-credential-value', os.getcwd())
sys.exit(8 if 'RAGANG_RUNNER_TEST_SECRET' in os.environ else 7)
""")
            env["RAGANG_RUNNER_TEST_SECRET"] = "synthetic-parent-credential"
            completed, report = self.invoke(directory, "--checks", "compile", "ui", "--ui-path", str(ui), env=env)
            rendered = json.dumps(report) + completed.stdout + completed.stderr
            self.assertNotIn(str(directory), rendered)
        self.assertNotIn("synthetic-credential-value", rendered)
        self.assertNotIn("synthetic-parent-credential", rendered)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["checks"][0]["status"], "passed")
        self.assertEqual(report["checks"][1]["returncode"], 7)
        self.assertEqual(report["checks"][1]["reason"], "check_failed")

    @unittest.skipIf(os.name == "nt", "The isolated executable fixture uses a POSIX shebang")
    def test_timeout_and_zero_collected_tests_cannot_be_reported_as_success(self):
        for source, expected in (("import time; time.sleep(30)", "timeout"),
                                 ("print('# tests 0')", "no_tests_collected")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                ui, env = self.fake_npm(directory, source)
                started = time.monotonic()
                timeout = "0.2" if expected == "timeout" else "5"
                completed, report = self.invoke(directory, "--checks", "ui", "--ui-path", str(ui), "--timeout", timeout, env=env)
                self.assertLess(time.monotonic() - started, 8)
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(report["checks"][0]["status"], "failed")
                self.assertEqual(report["checks"][0]["reason"], expected)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Run offline developer acceptance checks without publishing raw subprocess logs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
CHECKS = ("backend", "protocol", "compile", "ui", "typecheck", "build")
DEFAULT_CHECKS = ("backend", "compile", "ui", "typecheck", "build")
LABELS = {
    "backend": "백엔드 전체 회귀",
    "protocol": "로컬 요청·동시 실행·복구 계약",
    "compile": "Python 컴파일",
    "ui": "UI 회귀",
    "typecheck": "UI 타입 검사",
    "build": "UI 프로덕션 빌드",
}
PROTOCOL_MODULES = (
    "tests.test_cli_network_regressions",
    "tests.test_user_workflow_acceptance",
    "tests.test_request_correlation",
)


def child_environment() -> dict[str, str]:
    """Keep runtime necessities; do not forward provider credentials or endpoints."""
    names = (
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "HOME",
        "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TMP", "TEMP", "TMPDIR",
        "LANG", "LC_ALL", "LC_CTYPE", "NUMBER_OF_PROCESSORS",
    )
    env = {name: os.environ[name] for name in names if name in os.environ}
    env.update({
        "CI": "1", "PIP_NO_INDEX": "1", "NO_COLOR": "1",
        "npm_config_offline": "true", "npm_config_audit": "false",
        "npm_config_fund": "false", "npm_config_update_notifier": "false",
    })
    return env


def source_metadata(directory: Path, env: dict[str, str]) -> dict:
    """Record provenance without repository URLs, file names, or local paths."""
    metadata = {"available": False, "commit": None, "dirty": None}
    try:
        revision = subprocess.run(
            ["git", "--no-optional-locks", "rev-parse", "HEAD"], cwd=directory,
            env=env, capture_output=True, timeout=5, check=True,
        ).stdout.decode().strip()
        status = subprocess.run(
            ["git", "--no-optional-locks", "status", "--porcelain", "--untracked-files=normal"],
            cwd=directory, env=env, capture_output=True, timeout=5, check=True,
        ).stdout
        if re.fullmatch(r"[0-9a-f]{40,64}", revision):
            metadata.update(available=True, commit=revision, dirty=bool(status))
    except (OSError, subprocess.SubprocessError, UnicodeError):
        pass
    return metadata


def command_for(name: str, npm: str | None) -> list[str]:
    if name == "backend":
        return [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    if name == "protocol":
        return [sys.executable, "-m", "unittest", "-v", *PROTOCOL_MODULES]
    if name == "compile":
        return [sys.executable, "-m", "compileall", "-q", "ragang", "tests", "scripts"]
    return [npm or "npm", *( ["test"] if name == "ui" else ["run", name] )]


def stop_process(process: subprocess.Popen) -> None:
    """Also stop npm's descendants when a check exceeds its time budget."""
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    process.communicate()


def run_check(name: str, ui_path: Path, timeout: float, env: dict[str, str]) -> dict:
    started = time.monotonic()
    result = {
        "check": name, "status": "failed", "reason": None,
        "returncode": None, "duration_seconds": 0.0,
    }
    npm = shutil.which("npm", path=env.get("PATH"))
    if name in {"ui", "typecheck", "build"}:
        if not (ui_path / "package.json").is_file():
            result["reason"] = "missing_ui_checkout"
            return result
        if not (ui_path / "node_modules").is_dir():
            result["reason"] = "ui_dependencies_not_installed"
            return result
        if npm is None:
            result["reason"] = "npm_not_found"
            return result
    cwd = ui_path if name in {"ui", "typecheck", "build"} else ROOT
    process = None
    try:
        process = subprocess.Popen(
            command_for(name, npm), cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=(os.name == "posix"),
        )
        output, _ = process.communicate(timeout=timeout)
        result["returncode"] = process.returncode
        if process.returncode == 0:
            result["status"] = "passed"
        else:
            result["reason"] = "check_failed"
        # Extract counts only. Never save subprocess output, including failures.
        pattern = rb"Ran (\d+) tests?\b" if name in {"backend", "protocol"} else rb"(?:\xe2\x84\xb9\s+|#\s+)tests (\d+)\b"
        if name in {"backend", "protocol", "ui"}:
            counts = re.findall(pattern, output)
            if counts:
                result["tests_run"] = int(counts[-1])
            if process.returncode == 0 and (not counts or int(counts[-1]) == 0):
                result.update(status="failed", reason="no_tests_collected")
    except subprocess.TimeoutExpired:
        if process is not None:
            stop_process(process)
        result["reason"] = "timeout"
    except KeyboardInterrupt:
        if process is not None:
            stop_process(process)
        result.update(status="interrupted", reason="interrupted")
    except OSError:
        result["reason"] = "process_start_failed"
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result


def write_report(target: Path, report: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def positive_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("제한 시간에는 양수를 입력하세요.") from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("제한 시간에는 유한한 양수를 입력하세요.")
    return timeout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="유료 API·Milvus 없이 개발자용 사용자 과제 회귀 검증을 실행합니다.")
    parser.add_argument("--ui-path", type=Path, default=ROOT.parent / "RAG-APP-UI", help="별도 UI 소스 저장소(기본: 형제 RAG-APP-UI)")
    parser.add_argument("--checks", nargs="+", choices=("all", *CHECKS), default=["all"], help="실행할 검사. 기본 all은 전체 백엔드·컴파일·UI·타입·빌드")
    parser.add_argument("--timeout", type=positive_timeout, default=180.0, help="각 검사 제한 시간(초, 기본 180)")
    parser.add_argument("--output", type=Path, default=ROOT / "build/validation/usability-results.json", help="비민감 JSON 결과 파일")
    parser.add_argument("--list", action="store_true", help="검사 목록만 표시하고 종료")
    args = parser.parse_args(argv)
    if args.list:
        for name in CHECKS:
            print(f"{name}: {LABELS[name]}")
        return 0

    selected = set(DEFAULT_CHECKS if "all" in args.checks else args.checks)
    if "all" in args.checks:
        selected.update(name for name in args.checks if name != "all")
    ui_path = args.ui_path.expanduser().resolve()
    env = child_environment()
    report = {
        "schema_version": 1,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "offline_automated_acceptance",
        "browser_automation_performed": False,
        "human_user_testing_performed": False,
        "sources": {"backend": source_metadata(ROOT, env)},
        "checks": [],
    }
    if selected.intersection({"ui", "typecheck", "build"}):
        report["sources"]["ui"] = source_metadata(ui_path, env)
    interrupted = False
    for name in CHECKS:
        if name not in selected:
            continue
        if interrupted:
            report["checks"].append({"check": name, "status": "not_run", "reason": "interrupted"})
            continue
        print(f"검증: {LABELS[name]}", flush=True)
        result = run_check(name, ui_path, args.timeout, env)
        report["checks"].append(result)
        interrupted = result["status"] == "interrupted"
        print(f"  {result['status']}" + (f" ({result['reason']})" if result["reason"] else ""), flush=True)
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["status"] = "passed" if all(item["status"] == "passed" for item in report["checks"]) else "failed"
    try:
        write_report(args.output.expanduser().resolve(), report)
    except OSError:
        print("JSON 보고서를 저장하지 못했습니다. 출력 위치의 쓰기 권한을 확인하세요.", file=sys.stderr)
        return 1
    print("검증 결과를 지정한 JSON 파일에 저장했습니다. 원시 실행 로그는 저장하지 않습니다.")
    return 130 if interrupted else (0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    raise SystemExit(main())

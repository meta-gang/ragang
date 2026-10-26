from __future__ import annotations

import json
from datetime import datetime
from argparse import Namespace

from ragang.comparison import compare_runs
from ragang.core.utils.cli import get_history


def _select_runs(history: dict, baseline: str | None, candidate: str | None) -> tuple[str, str]:
    if baseline is not None or candidate is not None:
        if not baseline or not candidate:
            raise ValueError("Provide both --baseline and --candidate, or omit both to compare the latest two runs.")
        missing = [run_id for run_id in (baseline, candidate) if run_id not in history]
        if missing:
            raise ValueError(f"History run not found: {', '.join(missing)}")
        return baseline, candidate

    def chronology(key):
        states = history[key]
        started = next(((state.get('run_metadata') or {}).get('started_at')
                        for state in states.values() if isinstance(state, dict)
                        and (state.get('run_metadata') or {}).get('started_at')), None)
        if started:
            try:
                return datetime.fromisoformat(started).timestamp(), key
            except (TypeError, ValueError):
                pass
        try:
            return datetime.strptime(key[:12], '%y%m%d%H%M%S').timestamp(), key
        except ValueError:
            raise ValueError('History run has no valid started_at or legacy timestamp') from None
    timestamps = sorted(history, key=chronology)
    if len(timestamps) < 2:
        raise ValueError("At least two history runs are required for comparison.")
    return timestamps[-2], timestamps[-1]


def _run_time_label(run_key: str, states: dict) -> str:
    for state in states.values():
        started = (state.get('run_metadata') or {}).get('started_at')
        if isinstance(started, str):
            try:
                return datetime.fromisoformat(started).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
            except ValueError:
                pass
    try:
        return datetime.strptime(run_key[:12], '%y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return '시각 정보 없음'


def _print_report(report: dict, *, baseline_label: str, candidate_label: str):
    print(f"기준 실행: {baseline_label}")
    print(f"비교 실행: {candidate_label}")
    print(f"실행 설정: {'동일' if report['configuration']['match'] else '다름'}")
    baseline_health = report["evaluator_health"]["baseline"]
    candidate_health = report["evaluator_health"]["candidate"]
    print(
        "평가 완료 / 기록된 평가: "
        f"{baseline_health['evaluated']}/{baseline_health['evaluated'] + baseline_health['not_evaluated']}"
        " -> "
        f"{candidate_health['evaluated']}/{candidate_health['evaluated'] + candidate_health['not_evaluated']}"
    )
    print(
        "질문별 모듈 실행 시간 합의 평균: "
        f"{report['latency_seconds']['baseline_mean']}s -> {report['latency_seconds']['candidate_mean']}s"
    )
    for metric in report["metrics"]:
        if metric["delta"] is None:
            print(f"[{metric['module']}] {metric['metric']}: 비교할 공통 유효 평가가 없거나 평가 조건이 다릅니다.")
            continue
        paired = metric['paired']
        print(
            f"[{metric['module']}] {metric['metric']}: "
            f"{paired['baseline_mean']} -> {paired['candidate_mean']} "
            f"(차이 {metric['delta']:+g} {metric['unit']}; "
            f"공통 유효 표본 {paired['evaluated']}개)"
        )
    for warning in report["warnings"]:
        print(f"확인: {warning.replace('configuration fingerprint', '설정 정보')}")
    print('원본 실행 ID와 설정 정보는 --json에서 확인할 수 있습니다.')


def run(args: Namespace):
    history = get_history(args.flow_id)
    baseline_run, candidate_run = _select_runs(history, args.baseline, args.candidate)
    report = compare_runs(history[baseline_run], history[candidate_run])
    report["baseline_run"] = baseline_run
    report["candidate_run"] = candidate_run
    if args.json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report, baseline_label=_run_time_label(baseline_run, history[baseline_run]),
                      candidate_label=_run_time_label(candidate_run, history[candidate_run]))
    return report

from __future__ import annotations

import json
from argparse import Namespace

from ragang.comparison import compare_runs
from ragang.core.utils.cli import get_history


def _select_runs(history: dict, baseline: str | None, candidate: str | None) -> tuple[str, str]:
    timestamps = sorted(history)
    if baseline is None and candidate is None:
        if len(timestamps) < 2:
            raise ValueError("At least two history runs are required for comparison.")
        return timestamps[-2], timestamps[-1]
    if not baseline or not candidate:
        raise ValueError("Provide both --baseline and --candidate, or omit both to compare the latest two runs.")
    missing = [timestamp for timestamp in (baseline, candidate) if timestamp not in history]
    if missing:
        raise ValueError(f"History run not found: {', '.join(missing)}")
    return baseline, candidate


def _print_report(report: dict):
    print(f"Baseline: {report['baseline_run']}")
    print(f"Candidate: {report['candidate_run']}")
    print(f"Configuration match: {report['configuration']['match']}")
    baseline_health = report["evaluator_health"]["baseline"]
    candidate_health = report["evaluator_health"]["candidate"]
    print(
        "Evaluator coverage: "
        f"{baseline_health['evaluated']}/{baseline_health['evaluated'] + baseline_health['not_evaluated']}"
        " -> "
        f"{candidate_health['evaluated']}/{candidate_health['evaluated'] + candidate_health['not_evaluated']}"
    )
    print(
        "Mean latency: "
        f"{report['latency_seconds']['baseline_mean']}s -> {report['latency_seconds']['candidate_mean']}s"
    )
    for metric in report["metrics"]:
        if metric["delta"] is None:
            continue
        print(
            f"[{metric['module']}] {metric['metric']}: "
            f"{metric['baseline']['mean']} -> {metric['candidate']['mean']} "
            f"(delta {metric['delta']:+g} {metric['unit']}; "
            f"coverage {metric['baseline']['coverage']} -> {metric['candidate']['coverage']}; "
            f"stddev {metric['baseline']['population_stddev']} -> "
            f"{metric['candidate']['population_stddev']})"
        )
    for warning in report["warnings"]:
        print(f"Warning: {warning}")


def run(args: Namespace):
    history = get_history(args.flow_id)
    baseline_run, candidate_run = _select_runs(history, args.baseline, args.candidate)
    report = compare_runs(history[baseline_run], history[candidate_run])
    report["baseline_run"] = baseline_run
    report["candidate_run"] = candidate_run
    if args.json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)
    return report

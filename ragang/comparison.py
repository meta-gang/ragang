"""Baseline/candidate comparison for serialized RAGANG history runs."""

from __future__ import annotations

from collections import defaultdict
import math
from statistics import fmean, pstdev
from typing import Any


def _field(performance: dict, public: str, private: str, default=None):
    return performance.get(public, performance.get(private, default))


def _iter_performances(state: dict):
    for module_name, snapshots in (state.get("snapshots") or {}).items():
        for snapshot in snapshots or []:
            for performance in snapshot.get("performances") or []:
                yield "module", module_name, performance
    for performance in state.get("performances") or []:
        yield "e2e", "E2E", performance


def summarize_run(states: dict[str, dict]) -> dict:
    metric_groups = defaultdict(lambda: {"scores": [], "not_evaluated": 0})
    failure_types = defaultdict(int)
    latencies = []
    fingerprints = set()
    evaluated = 0
    not_evaluated = 0

    for state in states.values():
        metadata = state.get("run_metadata") or {}
        if metadata.get("config_fingerprint"):
            fingerprints.add(metadata["config_fingerprint"])
        state_latency = 0.0
        for snapshots in (state.get("snapshots") or {}).values():
            for snapshot in snapshots or []:
                duration = snapshot.get("x_time")
                if isinstance(duration, (int, float)):
                    state_latency += duration
        latencies.append(state_latency)

        for stage, module, performance in _iter_performances(state):
            metric = _field(performance, "metric", "_Performance__metric", "Unknown")
            unit = _field(performance, "unit", "_Performance__unit", "")
            key = (stage, module, metric, unit)
            did_eval = bool(_field(performance, "did_eval", "_Performance__did_eval", False))
            score = _field(performance, "score", "_Performance__score")
            if (
                did_eval
                and not isinstance(score, bool)
                and isinstance(score, (int, float))
                and math.isfinite(float(score))
            ):
                evaluated += 1
                metric_groups[key]["scores"].append(float(score))
            else:
                not_evaluated += 1
                metric_groups[key]["not_evaluated"] += 1
                failure = _field(performance, "failure", "_Performance__failure", None) or {}
                failure_types[failure.get("type", "not_evaluated")] += 1

    metrics = {}
    for key, values in metric_groups.items():
        scores = values["scores"]
        attempted = len(scores) + values["not_evaluated"]
        metrics[key] = {
            "mean": fmean(scores) if scores else None,
            "evaluated": len(scores),
            "not_evaluated": values["not_evaluated"],
            "coverage": len(scores) / attempted if attempted else None,
            "minimum": min(scores) if scores else None,
            "maximum": max(scores) if scores else None,
            "population_stddev": pstdev(scores) if len(scores) >= 2 else None,
        }
    total = evaluated + not_evaluated
    return {
        "query_count": len(states),
        "config_fingerprints": sorted(fingerprints),
        "evaluator_health": {
            "evaluated": evaluated,
            "not_evaluated": not_evaluated,
            "coverage": evaluated / total if total else None,
            "failure_types": dict(sorted(failure_types.items())),
        },
        "latency_mean": fmean(latencies) if latencies else None,
        "metrics": metrics,
    }


def compare_runs(baseline_states: dict[str, dict], candidate_states: dict[str, dict]) -> dict:
    baseline = summarize_run(baseline_states)
    candidate = summarize_run(candidate_states)
    baseline_fingerprints = baseline["config_fingerprints"]
    candidate_fingerprints = candidate["config_fingerprints"]
    config_match = (
        len(baseline_fingerprints) == 1
        and baseline_fingerprints == candidate_fingerprints
    )
    warnings = []
    if not config_match:
        warnings.append(
            "실행 configuration fingerprint가 일치하지 않습니다. 점수 차이를 단일 변경의 효과로 해석하지 마세요."
        )

    metrics = []
    empty_metric = {
        "mean": None,
        "evaluated": 0,
        "not_evaluated": 0,
        "coverage": None,
        "minimum": None,
        "maximum": None,
        "population_stddev": None,
    }
    for key in sorted(set(baseline["metrics"]) | set(candidate["metrics"])):
        baseline_metric = baseline["metrics"].get(key, dict(empty_metric))
        candidate_metric = candidate["metrics"].get(key, dict(empty_metric))
        delta = None
        if baseline_metric["mean"] is not None and candidate_metric["mean"] is not None:
            delta = round(candidate_metric["mean"] - baseline_metric["mean"], 6)
        stage, module, metric, unit = key
        metrics.append({
            "stage": stage,
            "module": module,
            "metric": metric,
            "unit": unit,
            "baseline": baseline_metric,
            "candidate": candidate_metric,
            "delta": delta,
        })

    return {
        "configuration": {
            "match": config_match,
            "baseline_fingerprints": baseline_fingerprints,
            "candidate_fingerprints": candidate_fingerprints,
        },
        "query_count": {
            "baseline": baseline["query_count"],
            "candidate": candidate["query_count"],
        },
        "evaluator_health": {
            "baseline": baseline["evaluator_health"],
            "candidate": candidate["evaluator_health"],
        },
        "latency_seconds": {
            "baseline_mean": baseline["latency_mean"],
            "candidate_mean": candidate["latency_mean"],
            "delta": (
                candidate["latency_mean"] - baseline["latency_mean"]
                if baseline["latency_mean"] is not None and candidate["latency_mean"] is not None
                else None
            ),
        },
        "metrics": metrics,
        "warnings": warnings,
    }

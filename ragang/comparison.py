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


def summarize_multi_runs(runs: list[dict[str, dict]] | tuple[dict[str, dict], ...]) -> dict:
    """Aggregate repeated evaluation runs to assess multi-trial variance and stability."""
    if not runs:
        raise ValueError("At least one run must be provided for multi-run analysis")

    summaries = [summarize_run(states) for states in runs]
    all_fingerprints = sorted({fp for s in summaries for fp in s["config_fingerprints"]})
    config_consistent = len(all_fingerprints) == 1 and all(
        s["config_fingerprints"] == all_fingerprints for s in summaries
    )

    total_queries = sum(s["query_count"] for s in summaries)
    total_evaluated = sum(s["evaluator_health"]["evaluated"] for s in summaries)
    total_not_evaluated = sum(s["evaluator_health"]["not_evaluated"] for s in summaries)
    total_attempts = total_evaluated + total_not_evaluated

    combined_failures = defaultdict(int)
    for s in summaries:
        for f_type, count in s["evaluator_health"].get("failure_types", {}).items():
            combined_failures[f_type] += count

    trial_latency_means = [s["latency_mean"] for s in summaries if s["latency_mean"] is not None]
    grand_latency_mean = fmean(trial_latency_means) if trial_latency_means else None
    latency_stddev = pstdev(trial_latency_means) if len(trial_latency_means) >= 2 else None

    all_metric_keys = sorted({key for s in summaries for key in s["metrics"]})
    aggregated_metrics = []

    for key in all_metric_keys:
        stage, module, metric, unit = key
        trial_means = [
            s["metrics"][key]["mean"]
            for s in summaries
            if key in s["metrics"] and s["metrics"][key]["mean"] is not None
        ]
        trial_eval_counts = [
            s["metrics"][key]["evaluated"]
            for s in summaries
            if key in s["metrics"]
        ]
        trial_not_eval_counts = [
            s["metrics"][key]["not_evaluated"]
            for s in summaries
            if key in s["metrics"]
        ]
        m_eval_total = sum(trial_eval_counts)
        m_not_eval_total = sum(trial_not_eval_counts)
        m_attempts = m_eval_total + m_not_eval_total

        aggregated_metrics.append({
            "stage": stage,
            "module": module,
            "metric": metric,
            "unit": unit,
            "trial_means": trial_means,
            "mean": fmean(trial_means) if trial_means else None,
            "between_run_stddev": pstdev(trial_means) if len(trial_means) >= 2 else None,
            "min_trial_mean": min(trial_means) if trial_means else None,
            "max_trial_mean": max(trial_means) if trial_means else None,
            "evaluated": m_eval_total,
            "not_evaluated": m_not_eval_total,
            "coverage": m_eval_total / m_attempts if m_attempts else None,
        })

    warnings = []
    if not config_consistent:
        warnings.append(
            "실행 configuration fingerprint가 일치하지 않는 실행이 포함되어 있습니다. 실행 간 차이를 무작위 변동으로만 해석하지 마세요."
        )

    return {
        "trial_count": len(runs),
        "total_queries": total_queries,
        "configuration": {
            "consistent": config_consistent,
            "fingerprints": all_fingerprints,
        },
        "evaluator_health": {
            "evaluated": total_evaluated,
            "not_evaluated": total_not_evaluated,
            "coverage": total_evaluated / total_attempts if total_attempts else None,
            "failure_types": dict(sorted(combined_failures.items())),
        },
        "latency_seconds": {
            "mean": grand_latency_mean,
            "between_run_stddev": latency_stddev,
        },
        "metrics": aggregated_metrics,
        "warnings": warnings,
    }

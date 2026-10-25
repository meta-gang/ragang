"""Baseline/candidate comparison for serialized RAGANG history runs."""

from __future__ import annotations

from collections import defaultdict
import math
import json
from statistics import fmean, pstdev
from typing import Any

from ragang.evaluator import performance_metadata_error, valid_score_value


def _field(performance: dict, public: str, private: str, default=None):
    return performance.get(public, performance.get(private, default))


def _iter_performances(state: dict):
    for module_name, snapshots in (state.get("snapshots") or {}).items():
        for snapshot in snapshots or []:
            for performance in snapshot.get("performances") or []:
                if isinstance(performance, dict):
                    yield "module", module_name, performance
    for performance in state.get("performances") or []:
        if isinstance(performance, dict):
            yield "e2e", "E2E", performance


def _valid_score(performance: dict) -> float | None:
    did_eval = _field(performance, "did_eval", "_Performance__did_eval", False)
    score = _field(performance, "score", "_Performance__score")
    if (performance_metadata_error(performance) is None
            and did_eval is True and valid_score_value(score)):
        return float(score)
    return None


def _metric_key(stage, module, performance):
    name = _field(performance, "metric", "_Performance__metric")
    unit = _field(performance, "unit", "_Performance__unit", "")
    return (stage, module,
            name if isinstance(name, str) and name.strip() else "Invalid metric identity",
            unit if isinstance(unit, str) else "")


def _evaluator_identity(performance: dict) -> str | None:
    if performance_metadata_error(performance) is not None:
        return None
    evaluator = _field(performance, "evaluator", "_Performance__evaluator")
    metric_version = _field(performance, "metric_version", "_Performance__metric_version")
    if metric_version is None and isinstance(evaluator, dict):
        settings = evaluator.get("settings")
        metric_version = settings.get("metric_version") if isinstance(settings, dict) else None
    if not evaluator and metric_version is None:
        return None
    return json.dumps({"evaluator": evaluator or {}, "metric_version": metric_version},
                      sort_keys=True, ensure_ascii=True, default=str)


def _pipeline_latency(state: dict) -> float:
    summary_latency = (state.get("execution_summary") or {}).get("total_latency_seconds")
    if (type(summary_latency) in (int, float) and math.isfinite(summary_latency)
            and summary_latency >= 0):
        return float(summary_latency)
    durations = [snapshot.get("x_time") for snapshots in (state.get("snapshots") or {}).values()
                 for snapshot in snapshots or []]
    return sum(float(value) for value in durations
               if type(value) in (int, float) and math.isfinite(value) and value >= 0)


def summarize_run(states: dict[str, dict]) -> dict:
    metric_groups = defaultdict(lambda: {"scores": [], "not_evaluated": 0,
                                          "identities": set(), "query_final_scores": []})
    failure_types = defaultdict(int)
    latencies = []
    fingerprints = set()
    evaluated = not_evaluated = 0
    succeeded = failed = unknown = 0
    for state in states.values():
        metadata = state.get("run_metadata") or {}
        if metadata.get("config_fingerprint"):
            fingerprints.add(metadata["config_fingerprint"])
        latencies.append(_pipeline_latency(state))
        execution = state.get("execution_summary") or {}
        if execution.get("terminated") is True:
            failed += 1
        elif execution.get("termination_reason") == "answer" or isinstance(state.get("gen"), str) and bool(state["gen"]):
            succeeded += 1
        else:
            unknown += 1
        final_performances = {}
        for stage, module, performance in _iter_performances(state):
            key = _metric_key(stage, module, performance)
            final_performances[key] = performance
            identity = _evaluator_identity(performance)
            metric_groups[key]["identities"].add(identity)
            score = _valid_score(performance)
            if score is not None:
                evaluated += 1
                metric_groups[key]["scores"].append(score)
            else:
                not_evaluated += 1
                metric_groups[key]["not_evaluated"] += 1
                failure = _field(performance, "failure", "_Performance__failure", None)
                failure_type = failure.get("type") if isinstance(failure, dict) else None
                if performance_metadata_error(performance) is not None:
                    failure_type = "invalid_performance_metadata"
                failure_types[failure_type if isinstance(failure_type, str) else "not_evaluated"] += 1
        for key, performance in final_performances.items():
            score = _valid_score(performance)
            if score is not None:
                metric_groups[key]["query_final_scores"].append(score)
    metrics = {}
    for key, values in metric_groups.items():
        scores = values["scores"]
        query_scores = values["query_final_scores"]
        attempted = len(scores) + values["not_evaluated"]
        mixed = len(values["identities"]) > 1
        metrics[key] = {
            "mean": fmean(scores) if scores and not mixed else None,
            "aggregation_unit": "recorded_metric_execution",
            "query_final_mean": fmean(query_scores) if query_scores and not mixed else None,
            "query_final_evaluated": len(query_scores),
            "evaluated": len(scores), "not_evaluated": values["not_evaluated"],
            "coverage": len(scores) / attempted if attempted else None,
            "minimum": min(scores) if scores and not mixed else None,
            "maximum": max(scores) if scores and not mixed else None,
            "population_stddev": pstdev(scores) if len(scores) >= 2 and not mixed else None,
            "mixed_evaluators": mixed,
        }
    total = evaluated + not_evaluated
    return {
        "query_count": len(states),
        "execution_health": {"attempted": len(states), "succeeded": succeeded,
                             "failed": failed, "unknown": unknown},
        "config_fingerprints": sorted(fingerprints),
        "evaluator_health": {
            "evaluated": evaluated, "not_evaluated": not_evaluated,
            "coverage": evaluated / total if total else None,
            "coverage_basis": "recorded_metric_attempts",
            "failure_types": dict(sorted(failure_types.items())),
        },
        "latency_mean": fmean(latencies) if latencies else None,
        "metrics": metrics,
    }


def pair_query_states(baseline_states: dict[str, dict], candidate_states: dict[str, dict]):
    """Pair stable sample IDs first, then exact query text, then legacy query ID.

    Duplicate text first uses common IDs, then insertion-order occurrence. Counts
    and ambiguity are reported; query content itself is never copied to reports.
    """
    def identity(query_id, state):
        sample_id = state.get("sample_id")
        if isinstance(sample_id, (str, int)) and not isinstance(sample_id, bool) and str(sample_id):
            return "sample_id", str(sample_id)
        query = state.get("query", state.get("_State__query"))
        if isinstance(query, str) and query:
            return "query_text", query
        return "query_id", query_id
    groups = []
    for states in (baseline_states, candidate_states):
        grouped = defaultdict(list)
        for query_id, state in states.items():
            grouped[identity(query_id, state)].append((query_id, state))
        groups.append(grouped)
    pairs, bases = [], set()
    duplicate_groups = content_mismatches = duplicate_sample_ids = 0
    for key in sorted(set(groups[0]) & set(groups[1])):
        left, right = list(groups[0][key]), list(groups[1][key])
        bases.add(key[0])
        if len(left) > 1 or len(right) > 1:
            if key[0] == "sample_id":
                duplicate_sample_ids += 1
                continue
            duplicate_groups += 1
        right_by_id = {qid: state for qid, state in right}
        common_ids = {qid for qid, _ in left} & set(right_by_id)
        ordered = [(state, right_by_id[qid]) for qid, state in left if qid in common_ids]
        ordered.extend(zip([state for qid, state in left if qid not in common_ids],
                           [state for qid, state in right if qid not in common_ids]))
        for first, second in ordered:
            first_query, second_query = first.get("query"), second.get("query")
            if (key[0] == "sample_id" and isinstance(first_query, str)
                    and isinstance(second_query, str) and first_query != second_query):
                content_mismatches += 1
                continue
            pairs.append((first, second))
    pairing = {
        "paired_query_count": len(pairs),
        "baseline_unpaired": len(baseline_states) - len(pairs),
        "candidate_unpaired": len(candidate_states) - len(pairs),
        "pairing_basis": next(iter(bases)) if len(bases) == 1 else "mixed" if bases else "none",
        "duplicate_query_groups": duplicate_groups,
        "sample_id_content_mismatches": content_mismatches,
        "duplicate_sample_ids": duplicate_sample_ids,
    }
    return pairs, pairing


def _final_metrics(state: dict) -> dict:
    grouped = defaultdict(list)
    for stage, module, performance in _iter_performances(state):
        grouped[_metric_key(stage, module, performance)].append(performance)
    return grouped


def compare_runs(baseline_states: dict[str, dict], candidate_states: dict[str, dict]) -> dict:
    """Report whole-run summaries and deltas over paired final executions only.

    Numeric deltas never use unrelated questions or one-sided valid samples.
    Known evaluator changes block a delta. Legacy metadata is explicitly marked
    unverified rather than pretending to prove evaluator equivalence.
    """
    baseline, candidate = summarize_run(baseline_states), summarize_run(candidate_states)
    baseline_fingerprints = baseline["config_fingerprints"]
    candidate_fingerprints = candidate["config_fingerprints"]
    config_match = len(baseline_fingerprints) == 1 and baseline_fingerprints == candidate_fingerprints
    pairs, pairing = pair_query_states(baseline_states, candidate_states)
    warnings = []
    if not config_match:
        warnings.append("실행 configuration fingerprint가 일치하지 않습니다. 점수 차이를 단일 변경의 효과로 해석하지 마세요.")
    if pairing["baseline_unpaired"] or pairing["candidate_unpaired"]:
        warnings.append("질문 집합이 일치하지 않습니다. delta는 대응되는 질문의 공통 유효 평가만 사용합니다.")
    if pairing["duplicate_query_groups"]:
        warnings.append("중복 질문은 공통 ID 뒤에 입력 순서의 발생 횟수로 대응했습니다. 안정적인 sample_id를 사용하세요.")
    if pairing["sample_id_content_mismatches"]:
        warnings.append("같은 sample_id의 질문 내용이 달라 해당 쌍을 제외했습니다.")
    if pairing["duplicate_sample_ids"]:
        warnings.append("sample_id가 중복된 그룹은 안정적으로 대응할 수 없어 비교에서 제외했습니다.")
    empty_metric = {"mean": None, "evaluated": 0, "not_evaluated": 0, "coverage": None,
                    "minimum": None, "maximum": None, "population_stddev": None}
    pair_metrics = [(_final_metrics(first), _final_metrics(second)) for first, second in pairs]
    metrics = []
    any_legacy = any_incomplete = False
    for key in sorted(set(baseline["metrics"]) | set(candidate["metrics"])):
        before, after = baseline["metrics"].get(key, dict(empty_metric)), candidate["metrics"].get(key, dict(empty_metric))
        paired_before, paired_after = [], []
        evaluator_mismatch = legacy = False
        for first_metrics, second_metrics in pair_metrics:
            first_values, second_values = first_metrics.get(key, []), second_metrics.get(key, [])
            if not first_values or not second_values:
                continue
            identities = [{_evaluator_identity(p) for p in values} for values in (first_values, second_values)]
            # Mixing evaluator versions under one metric name cannot be averaged.
            if any(len(ids) > 1 for ids in identities) or identities[0] != identities[1]:
                evaluator_mismatch = True
                continue
            first, second = first_values[-1], second_values[-1]
            first_score, second_score = _valid_score(first), _valid_score(second)
            if first_score is None or second_score is None:
                continue
            legacy = legacy or identities[0] == {None}
            paired_before.append(first_score)
            paired_after.append(second_score)
        any_legacy = any_legacy or legacy
        count = len(paired_before)
        any_incomplete = any_incomplete or count < len(pairs)
        comparable = bool(count) and not evaluator_mismatch and not before.get("mixed_evaluators") and not after.get("mixed_evaluators")
        reasons = []
        if not pairs: reasons.append("no_paired_queries")
        elif not count: reasons.append("no_common_evaluated_samples")
        if evaluator_mismatch or before.get("mixed_evaluators") or after.get("mixed_evaluators"):
            reasons.append("evaluator_configuration_mismatch")
        if legacy: reasons.append("legacy_evaluator_unverified")
        if count < len(pairs): reasons.append("incomplete_paired_evaluation")
        stage, module, metric, unit = key
        metrics.append({
            "stage": stage, "module": module, "metric": metric, "unit": unit,
            "baseline": before, "candidate": after,
            "delta": round(fmean(b - a for a, b in zip(paired_before, paired_after)), 6) if comparable else None,
            "paired": {"evaluated": count,
                       "baseline_mean": fmean(paired_before) if comparable else None,
                       "candidate_mean": fmean(paired_after) if comparable else None,
                       "coverage": count / len(pairs) if pairs else None,
                       "aggregation_unit": "query_final_execution"},
            "comparable": comparable, "evaluator_verified": comparable and not legacy,
            "comparison_notes": reasons,
        })
    if any_legacy:
        warnings.append("일부 legacy 결과에 평가자 provenance가 없습니다. 해당 delta는 평가자 동일성이 검증되지 않은 기술 통계입니다.")
    if any_incomplete:
        warnings.append("양쪽에서 유효하게 평가된 공통 표본만 비교했습니다. 판정 실패에 따른 표본 선택 편향을 확인하세요.")
    if any("evaluator_configuration_mismatch" in metric["comparison_notes"] for metric in metrics):
        warnings.append("평가자 또는 지표 버전이 다른 항목의 delta는 계산하지 않았습니다.")
    return {
        "configuration": {"match": config_match, "baseline_fingerprints": baseline_fingerprints,
                          "candidate_fingerprints": candidate_fingerprints},
        "query_count": {"baseline": baseline["query_count"], "candidate": candidate["query_count"]},
        "pairing": pairing,
        "execution_health": {"baseline": baseline["execution_health"], "candidate": candidate["execution_health"]},
        "evaluator_health": {"baseline": baseline["evaluator_health"], "candidate": candidate["evaluator_health"]},
        "latency_seconds": {
            "baseline_mean": baseline["latency_mean"], "candidate_mean": candidate["latency_mean"],
            "delta": fmean(_pipeline_latency(second) - _pipeline_latency(first) for first, second in pairs) if pairs else None,
            "paired_queries": len(pairs), "scope": "pipeline_module_execution"},
        "metrics": metrics, "warnings": warnings,
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

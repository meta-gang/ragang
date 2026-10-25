"""Conservative, gold-free diagnostics derived from observed runtime state."""

from __future__ import annotations

from typing import Any

from ragang.evaluator import performance_metadata_error, valid_score_value


def _serialized(state: Any) -> dict:
    return state.serialize() if hasattr(state, "serialize") else state


def _field(performance: dict, public: str, private: str, default=None):
    return performance.get(public, performance.get(private, default))


def _execution_path(trace: list[dict], target_execution_id: str) -> list[str]:
    """Return deterministic causal ancestry labels for a failed execution.

    Merge nodes can have multiple parents, so this is a topologically ordered
    ancestry list rather than a claim that only one linear path existed.
    """
    event_by_id = {event.get("execution_id"): event for event in trace}
    visited: set[str] = set()
    ordered: list[dict] = []

    def visit(execution_id: str) -> None:
        if execution_id in visited:
            return
        visited.add(execution_id)
        event = event_by_id.get(execution_id)
        if event is None:
            return
        for parent_id in event.get("parent_execution_ids") or []:
            visit(parent_id)
        ordered.append(event)

    visit(target_execution_id)
    return [
        f"{event.get('module_id', 'unknown')}#{event.get('execution_index', '?')}"
        for event in ordered
    ]


def _answer_retrieval_frontier(payload: dict) -> tuple[list[list], bool]:
    """Find nearest recorded retrieval output on each final answer ancestry path.

    Earlier failed/empty attempts remain observations, but a successful retry must
    not turn into an unsupported claim that the final answer lacked evidence.
    Raw snapshot content is used only to inspect presence and is not copied.
    """
    trace = payload.get("execution_trace") or []
    completed = [event for event in trace if event.get("status") == "completed"]
    answer_events = [event for event in completed if "gen" in (event.get("output_keys") or [])]
    final = answer_events[-1] if answer_events else completed[-1] if completed else None
    if final is not None:
        by_id = {event.get("execution_id"): event for event in trace}
        frontier, visited = [], set()
        def visit(event):
            execution_id = event.get("execution_id")
            if execution_id in visited:
                return
            visited.add(execution_id)
            snapshots = (payload.get("snapshots") or {}).get(event.get("module_id")) or []
            index = event.get("execution_index", 0) - 1
            if 0 <= index < len(snapshots):
                docs = (snapshots[index].get("data") or {}).get("ret_docs")
                if isinstance(docs, list):
                    frontier.append(docs)
                    return
            for parent_id in event.get("parent_execution_ids") or []:
                if parent_id in by_id:
                    visit(by_id[parent_id])
        visit(final)
        return frontier, True
    # Legacy payloads have no execution ancestry. Inspect only each module's
    # latest retrieval snapshot and explicitly lower inference confidence.
    frontier = []
    for snapshots in (payload.get("snapshots") or {}).values():
        retrieval_outputs = [(snapshot.get("data") or {}).get("ret_docs") for snapshot in snapshots or []]
        retrieval_outputs = [docs for docs in retrieval_outputs if isinstance(docs, list)]
        if retrieval_outputs:
            frontier.append(retrieval_outputs[-1])
    return frontier, False


def diagnose_state(state: Any) -> dict:
    payload = _serialized(state)
    observations = []
    inferences = []
    evaluated = 0
    not_evaluated = 0
    empty_retrieval_modules = []
    execution_trace = payload.get("execution_trace") or []
    execution_summary = payload.get("execution_summary") or {}
    failed_executions = [
        event for event in execution_trace if event.get("status") == "failed"
    ]
    repeated_modules = execution_summary.get("repeated_modules") or []

    for event in failed_executions:
        failure = event.get("failure") or {}
        observations.append({
            "code": "graph.execution_failed",
            "stage": "execution",
            "module": event.get("module_id"),
            "execution": event.get("execution_index"),
            "failure_type": failure.get("type", "execution_error"),
            "path": _execution_path(execution_trace, event.get("execution_id")),
            "message": failure.get("message", "모듈 실행이 실패했습니다."),
        })

    for repeated in repeated_modules:
        observations.append({
            "code": "graph.module_revisited",
            "stage": "execution",
            "module": repeated.get("module_id"),
            "executions": repeated.get("executions"),
            "revisits": repeated.get("revisits"),
            "message": "순환 또는 재시도 경로에서 모듈이 반복 실행되었습니다.",
        })

    if execution_summary.get("termination_reason") == "max_steps":
        observations.append({
            "code": "graph.max_steps_reached",
            "stage": "execution",
            "message": "설정된 최대 실행 단계에 도달하여 흐름을 중단했습니다.",
        })

    performance_groups = []
    for module_name, snapshots in (payload.get("snapshots") or {}).items():
        for execution_index, snapshot in enumerate(snapshots or []):
            data = snapshot.get("data") or {}
            if isinstance(data.get("ret_docs"), list) and not data["ret_docs"]:
                empty_retrieval_modules.append(module_name)
                observations.append({
                    "code": "retrieval.empty",
                    "stage": "retrieval",
                    "module": module_name,
                    "execution": execution_index + 1,
                    "message": "검색 모듈이 문서를 반환하지 않았습니다.",
                })
            performance_groups.append(("module", module_name, snapshot.get("performances") or []))
    performance_groups.append(("e2e", "E2E", payload.get("performances") or []))

    for stage, module_name, performances in performance_groups:
        for performance in performances:
            raw_score = _field(performance, "score", "_Performance__score")
            metadata_error = performance_metadata_error(performance)
            did_eval = (metadata_error is None
                        and _field(performance, "did_eval", "_Performance__did_eval", False) is True
                        and valid_score_value(raw_score))
            metric = _field(performance, "metric", "_Performance__metric")
            if not isinstance(metric, str) or not metric.strip():
                metric = "Invalid metric identity"
            if did_eval:
                evaluated += 1
                continue
            not_evaluated += 1
            failure = _field(performance, "failure", "_Performance__failure", None)
            if not isinstance(failure, dict):
                failure = {}
            failure_type = failure.get("type", "not_evaluated")
            failure_message = failure.get("message", "평가 결과가 생성되지 않았습니다.")
            if metadata_error:
                failure_type = "invalid_performance_metadata"
                failure_message = "지표 메타데이터가 선언된 형식과 일치하지 않습니다."
            observations.append({
                "code": "evaluator.not_evaluated",
                "stage": stage,
                "module": module_name,
                "metric": metric,
                "failure_type": failure_type if isinstance(failure_type, str) else "not_evaluated",
                "message": failure_message if isinstance(failure_message, str) else "평가 결과가 생성되지 않았습니다.",
            })

    answer_retrieval, ancestry_available = _answer_retrieval_frontier(payload)
    if answer_retrieval and all(not documents for documents in answer_retrieval) and payload.get("gen"):
        inferences.append({
            "code": "answer_without_retrieved_evidence",
            "possible_cause": "최종 답변의 기록된 경로에서 최근 검색 결과가 비어 있습니다.",
            "confidence": "medium" if ancestry_available else "low",
            "confidence_basis": "heuristic_rule_not_calibrated_probability",
            "based_on": ["retrieval.latest_answer_ancestry_empty", "state.gen_present"],
            "next_action": "답변가능성/안전 거절 동작과 검색 설정을 확인하세요.",
        })
    if not_evaluated:
        inferences.append({
            "code": "evaluator_health_risk",
            "possible_cause": "평가자 또는 평가 입력/출력 파싱이 불안정할 수 있습니다.",
            "confidence": "medium",
            "based_on": ["evaluator.not_evaluated"],
            "next_action": "실패 유형, judge 모델, metric fingerprint를 기준으로 재실행을 비교하세요.",
        })
    if failed_executions or execution_summary.get("termination_reason") == "max_steps":
        inferences.append({
            "code": "graph_execution_risk",
            "possible_cause": "실행 경로, 분기 조건, 재시도 정책 또는 외부 모듈을 점검해야 합니다.",
            "confidence": "medium",
            "based_on": [
                "graph.execution_failed" if failed_executions else "graph.max_steps_reached"
            ],
            "next_action": "실패 실행의 parent_execution_ids와 경로를 따라 최초 이상 지점을 확인하세요.",
        })

    total = evaluated + not_evaluated
    return {
        "evaluator_health": {
            "evaluated": evaluated,
            "not_evaluated": not_evaluated,
            "coverage": evaluated / total if total else None,
            "coverage_basis": "recorded_metric_attempts",
        },
        "graph_health": {
            "trace_available": bool(execution_trace),
            "total_executions": execution_summary.get("total_executions", len(execution_trace)),
            "failed_executions": execution_summary.get("failed_executions", len(failed_executions)),
            "module_revisits": execution_summary.get("module_revisits", 0),
            "cycle_or_retry_observed": bool(repeated_modules),
            "total_latency_seconds": execution_summary.get("total_latency_seconds"),
            "terminated": bool(execution_summary.get("terminated", False)),
            "termination_reason": execution_summary.get("termination_reason"),
        },
        "observations": observations,
        "inferences": inferences,
    }

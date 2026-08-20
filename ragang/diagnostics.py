"""Conservative, gold-free diagnostics derived from observed runtime state."""

from __future__ import annotations

from typing import Any


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
                    "execution": execution_index,
                    "message": "검색 모듈이 문서를 반환하지 않았습니다.",
                })
            performance_groups.append(("module", module_name, snapshot.get("performances") or []))
    performance_groups.append(("e2e", "E2E", payload.get("performances") or []))

    for stage, module_name, performances in performance_groups:
        for performance in performances:
            did_eval = bool(_field(performance, "did_eval", "_Performance__did_eval", False))
            metric = _field(performance, "metric", "_Performance__metric", "Unknown")
            if did_eval:
                evaluated += 1
                continue
            not_evaluated += 1
            failure = _field(performance, "failure", "_Performance__failure", None) or {}
            observations.append({
                "code": "evaluator.not_evaluated",
                "stage": stage,
                "module": module_name,
                "metric": metric,
                "failure_type": failure.get("type", "not_evaluated"),
                "message": failure.get("message", "평가 결과가 생성되지 않았습니다."),
            })

    if empty_retrieval_modules and payload.get("gen"):
        inferences.append({
            "code": "answer_without_retrieved_evidence",
            "possible_cause": "검색 근거가 없는 상태에서 답변이 생성되었습니다.",
            "confidence": "high",
            "based_on": ["retrieval.empty", "state.gen_present"],
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

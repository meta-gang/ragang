"""Conservative, gold-free diagnostics derived from observed runtime state."""

from __future__ import annotations

from typing import Any


def _serialized(state: Any) -> dict:
    return state.serialize() if hasattr(state, "serialize") else state


def _field(performance: dict, public: str, private: str, default=None):
    return performance.get(public, performance.get(private, default))


def diagnose_state(state: Any) -> dict:
    payload = _serialized(state)
    observations = []
    inferences = []
    evaluated = 0
    not_evaluated = 0
    empty_retrieval_modules = []

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

    total = evaluated + not_evaluated
    return {
        "evaluator_health": {
            "evaluated": evaluated,
            "not_evaluated": not_evaluated,
            "coverage": evaluated / total if total else None,
        },
        "observations": observations,
        "inferences": inferences,
    }

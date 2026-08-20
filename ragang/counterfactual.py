"""Deterministic, gold-free retrieval perturbations and conservative comparison."""

from __future__ import annotations

import random
from collections import Counter
from typing import Any, Sequence

from ragang.comparison import compare_runs


_INJECTION_KINDS = {
    "distractor_injection",
    "conflict_injection",
    "noisy_context_injection",
}
_SUPPORTED_KINDS = _INJECTION_KINDS | {"retrieval_dropout", "retrieval_shuffle"}
_SUPPORTED_INSERTIONS = {"front", "end", "random"}


def _validate_documents(documents: Sequence[str], name: str) -> list[str]:
    if isinstance(documents, (str, bytes)):
        raise TypeError(f"{name} must be a sequence of document strings, not a single string")
    copied = list(documents)
    if any(not isinstance(document, str) for document in copied):
        raise TypeError(f"{name} must contain only strings")
    return copied


def perturb_retrieval(
    documents: Sequence[str],
    *,
    kind: str,
    injected_documents: Sequence[str] | None = None,
    drop_count: int = 1,
    seed: int = 0,
    insertion: str = "random",
) -> dict[str, Any]:
    """Create one reproducible retrieval variant without requiring reference answers.

    Injection labels are supplied by the caller. RAGANG records the declared role
    but does not claim to have verified that a document is truly distracting,
    conflicting, or noisy.
    """
    if kind not in _SUPPORTED_KINDS:
        raise ValueError(f"kind must be one of {sorted(_SUPPORTED_KINDS)}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")

    baseline = _validate_documents(documents, "documents")
    variant = list(baseline)
    rng = random.Random(seed)
    details: dict[str, Any] = {}

    if kind in _INJECTION_KINDS:
        if injected_documents is None:
            raise ValueError(f"injected_documents is required for {kind}")
        injected = _validate_documents(injected_documents, "injected_documents")
        if not injected:
            raise ValueError("injected_documents must not be empty")
        if insertion not in _SUPPORTED_INSERTIONS:
            raise ValueError(f"insertion must be one of {sorted(_SUPPORTED_INSERTIONS)}")

        insertion_indices = []
        for document in injected:
            if insertion == "front":
                index = len(insertion_indices)
            elif insertion == "end":
                index = len(variant)
            else:
                index = rng.randint(0, len(variant))
            variant.insert(index, document)
            insertion_indices.append(index)
        details = {
            "declared_injected_role": kind.removesuffix("_injection"),
            "injected_count": len(injected),
            "insertion": insertion,
            "insertion_indices": insertion_indices,
            "semantic_role_verified": False,
        }
    elif kind == "retrieval_dropout":
        if isinstance(drop_count, bool) or not isinstance(drop_count, int) or drop_count <= 0:
            raise ValueError("drop_count must be a positive integer")
        if drop_count > len(baseline):
            raise ValueError("drop_count cannot exceed the number of documents")
        dropped_indices = sorted(rng.sample(range(len(baseline)), drop_count))
        dropped = set(dropped_indices)
        variant = [document for index, document in enumerate(baseline) if index not in dropped]
        details = {"drop_count": drop_count, "dropped_indices": dropped_indices}
    else:
        source_indices = list(range(len(baseline)))
        rng.shuffle(source_indices)
        variant = [baseline[index] for index in source_indices]
        details = {"source_indices": source_indices}

    return {
        "documents": variant,
        "provenance": {
            "schema_version": 1,
            "kind": kind,
            "seed": seed,
            "baseline_document_count": len(baseline),
            "variant_document_count": len(variant),
            "changed": variant != baseline,
            **details,
        },
    }


def compare_counterfactual_runs(
    baseline_states: dict[str, dict],
    candidate_states: dict[str, dict],
    *,
    perturbation: dict[str, Any],
) -> dict[str, Any]:
    """Compare variants while explicitly avoiding an unsupported causal claim."""
    if not isinstance(perturbation, dict) or not perturbation.get("kind"):
        raise ValueError("perturbation provenance with a kind is required")

    report = compare_runs(baseline_states, candidate_states)
    def query_counts(states: dict[str, dict]) -> Counter[str]:
        return Counter(
            query
            for state in states.values()
            if isinstance(state, dict)
            and isinstance((query := state.get("query", state.get("_State__query"))), str)
            and query
        )

    baseline_queries = query_counts(baseline_states)
    candidate_queries = query_counts(candidate_states)
    if baseline_queries and candidate_queries:
        paired_query_count = sum(
            min(count, candidate_queries.get(query, 0))
            for query, count in baseline_queries.items()
        )
        pairing_basis = "query_text"
    else:
        paired_query_count = len(set(baseline_states).intersection(candidate_states))
        pairing_basis = "query_id"
    report["counterfactual"] = {
        "perturbation": dict(perturbation),
        "paired_query_count": paired_query_count,
        "pairing_basis": pairing_basis,
        "causal_claim_supported": False,
        "interpretation": (
            "보고된 delta는 관측된 실행 차이입니다. RAGANG은 perturbation 외의 조건이 "
            "동일했는지 또는 주입 문서의 의미적 역할이 정확한지 증명하지 않습니다."
        ),
    }
    report["warnings"].append(
        "Counterfactual 비교는 민감도 단서이며 gold 정답이나 인과 효과의 증명이 아닙니다."
    )
    return report

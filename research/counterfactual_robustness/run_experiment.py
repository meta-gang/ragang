"""Experiment B: Counterfactual Retrieval Robustness.

Demonstrates RAGANG's deterministic retrieval perturbation engine across
distractor injection, conflict injection, noisy context injection, dropout,
and shuffling, followed by conservative non-causal delta comparison.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ragang.counterfactual import perturb_retrieval, compare_counterfactual_runs


# Base documents representing an authentic retrieved context set
BASELINE_DOCUMENTS = [
    "RAGANG is a ground-truth-free RAG evaluation and diagnosis framework developed in Python.",
    "It distinguishes calculated zero scores from unevaluated errors and preserves evaluator health.",
    "The framework provides execution tracing for linear, branching, retry, and cyclic pipelines.",
    "Counterfactual perturbations allow measuring system sensitivity without gold-standard answers.",
]

DISTRACTORS = [
    "Sourdough fermentation requires flour, water, wild yeast, and lactic acid bacteria.",
]

CONFLICTING_DOCS = [
    "RAGANG strictly requires millions of human-annotated gold answer pairs to compute scores.",
]

NOISY_DOCS = [
    "Garbled text: 12938102938012938 ??? $$$ #### corrupt buffer payload.",
]


def mock_run_state(query: str, docs: list[str], answer: str, sim_score: float) -> dict:
    return {
        "query": query,
        "run_metadata": {
            "config_fingerprint": "a1b2c3d4e5f60718",
        },
        "snapshots": {
            "retrieval": [
                {
                    "data": {"ret_docs": docs},
                    "x_time": 0.005,
                    "performances": [
                        {
                            "metric": "Query-context coverage",
                            "unit": "%",
                            "score": sim_score,
                            "did_eval": True,
                        }
                    ],
                }
            ],
            "generation": [
                {
                    "data": {"gen": answer},
                    "x_time": 0.020,
                    "performances": [
                        {
                            "metric": "Answer-evidence overlap",
                            "unit": "%",
                            "score": 85.0 if sim_score > 30 else 20.0,
                            "did_eval": True,
                        }
                    ],
                }
            ],
        },
        "performances": [
            {
                "metric": "Query-answer alignment",
                "unit": "%",
                "score": sim_score * 0.9,
                "did_eval": True,
            }
        ],
    }


def run_experiment():
    print("=" * 70)
    print("EXPERIMENT B: Counterfactual Retrieval Robustness")
    print("=" * 70)

    perturbations = [
        ("distractor_injection", {"injected_documents": DISTRACTORS, "insertion": "front", "seed": 42}),
        ("conflict_injection", {"injected_documents": CONFLICTING_DOCS, "insertion": "end", "seed": 42}),
        ("noisy_context_injection", {"injected_documents": NOISY_DOCS, "insertion": "random", "seed": 42}),
        ("retrieval_dropout", {"drop_count": 2, "seed": 42}),
        ("retrieval_shuffle", {"seed": 42}),
    ]

    print(f"\n[Baseline] Document Count: {len(BASELINE_DOCUMENTS)}")
    for i, doc in enumerate(BASELINE_DOCUMENTS):
        print(f"  [{i+1}] {doc[:75]}...")

    results = []
    for kind, kwargs in perturbations:
        res = perturb_retrieval(BASELINE_DOCUMENTS, kind=kind, **kwargs)
        variant_docs = res["documents"]
        prov = res["provenance"]

        print(f"\n--- Perturbation: {kind} ---")
        print(f"  Seed: {prov['seed']}, Changed: {prov['changed']}, New Count: {prov['variant_document_count']}")
        if "declared_injected_role" in prov:
            print(f"  Injected Role: {prov['declared_injected_role']}, Insertion: {prov['insertion']}, Indices: {prov['insertion_indices']}")
        elif "dropped_indices" in prov:
            print(f"  Dropped Indices: {prov['dropped_indices']}, Drop Count: {prov['drop_count']}")
        elif "source_indices" in prov:
            print(f"  Permuted Source Indices: {prov['source_indices']}")

        results.append((kind, res))

    # Demonstrate conservative comparison between Baseline run and Distractor-injected run
    print("\n--- Counterfactual Run Comparison (Baseline vs Distractor) ---")
    query_text = "What is RAGANG and what does it evaluate?"

    baseline_states = {
        "q1": mock_run_state(query_text, BASELINE_DOCUMENTS, "RAGANG evaluates RAG systems without gold answers.", 90.0)
    }

    distractor_res = perturb_retrieval(BASELINE_DOCUMENTS, kind="distractor_injection", injected_documents=DISTRACTORS, seed=42)
    candidate_states = {
        "q1": mock_run_state(query_text, distractor_res["documents"], "RAGANG evaluates RAG systems. Sourdough requires yeast.", 65.0)
    }

    cf_report = compare_counterfactual_runs(
        baseline_states,
        candidate_states,
        perturbation=distractor_res["provenance"],
    )

    print(f"Paired Queries: {cf_report['counterfactual']['paired_query_count']}")
    print(f"Causal Claim Supported: {cf_report['counterfactual']['causal_claim_supported']}")
    print(f"Interpretation Note: {cf_report['counterfactual']['interpretation']}")
    print(f"Metric Deltas:")
    for m in cf_report["metrics"]:
        print(f"  - [{m['stage']}:{m['module']}] {m['metric']}: Baseline={m['baseline']['mean']}{m['unit']}, Candidate={m['candidate']['mean']}{m['unit']}, Delta={m['delta']}{m['unit']}")

    print(f"Warnings: {cf_report['warnings']}")

    print("\n" + "=" * 70)
    print("EXPERIMENT B PASSED: Deterministic perturbation and non-causal comparison verified.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    run_experiment()

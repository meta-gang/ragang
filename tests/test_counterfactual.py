from __future__ import annotations

import unittest

from ragang.counterfactual import compare_counterfactual_runs, perturb_retrieval


class CounterfactualTests(unittest.TestCase):
    def test_injection_is_deterministic_and_does_not_mutate_baseline(self):
        baseline = ["relevant-a", "relevant-b"]

        first = perturb_retrieval(
            baseline,
            kind="distractor_injection",
            injected_documents=["distractor"],
            seed=7,
        )
        second = perturb_retrieval(
            baseline,
            kind="distractor_injection",
            injected_documents=["distractor"],
            seed=7,
        )

        self.assertEqual(first, second)
        self.assertEqual(baseline, ["relevant-a", "relevant-b"])
        self.assertFalse(first["provenance"]["semantic_role_verified"])
        self.assertEqual(first["provenance"]["injected_count"], 1)

    def test_dropout_records_exact_changed_indices(self):
        variant = perturb_retrieval(
            ["a", "b", "c"],
            kind="retrieval_dropout",
            drop_count=2,
            seed=4,
        )

        self.assertEqual(len(variant["documents"]), 1)
        self.assertEqual(len(variant["provenance"]["dropped_indices"]), 2)
        self.assertTrue(variant["provenance"]["changed"])

    def test_invalid_perturbation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "injected_documents"):
            perturb_retrieval(["a"], kind="conflict_injection")
        with self.assertRaisesRegex(ValueError, "drop_count"):
            perturb_retrieval(["a"], kind="retrieval_dropout", drop_count=2)

    def test_counterfactual_comparison_is_explicitly_non_causal(self):
        baseline = {
            "baseline-id": {"query": "same question", "snapshots": {}, "performances": []}
        }
        candidate = {
            "candidate-id": {"query": "same question", "snapshots": {}, "performances": []}
        }

        report = compare_counterfactual_runs(
            baseline,
            candidate,
            perturbation={"kind": "retrieval_shuffle", "seed": 3},
        )

        self.assertEqual(report["counterfactual"]["paired_query_count"], 1)
        self.assertEqual(report["counterfactual"]["pairing_basis"], "query_text")
        self.assertFalse(report["counterfactual"]["causal_claim_supported"])
        self.assertTrue(any("인과" in warning for warning in report["warnings"]))


if __name__ == "__main__":
    unittest.main()

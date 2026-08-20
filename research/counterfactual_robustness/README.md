# Experiment B: Counterfactual Retrieval Robustness

## 1. Hypothesis & Objective
In ground-truth-free RAG evaluation, measuring system sensitivity to variations in retrieved contexts is critical for understanding robustness against noisy retrievers, conflicting data, or positional bias.

**Hypothesis**:
1. Applying deterministic context perturbations (`distractor_injection`, `conflict_injection`, `noisy_context_injection`, `retrieval_dropout`, `retrieval_shuffle`) produces reproducible sensitivity deltas without requiring human-annotated gold answers.
2. Sensitivity deltas quantify empirical behavioral change, but must be accompanied by explicit non-causal interpretation warnings.

---

## 2. Experimental Setup

The experiment applies 5 deterministic perturbation strategies to a baseline document set:
1. `distractor_injection`: Inserts an irrelevant passage at the front.
2. `conflict_injection`: Appends a contradictory claim at the end.
3. `noisy_context_injection`: Injects garbled noise at a random index.
4. `retrieval_dropout`: Drops 2 documents using fixed seed subsampling.
5. `retrieval_shuffle`: Permutes context ordering to evaluate position sensitivity.

---

## 3. How to Run

```bash
python research/counterfactual_robustness/run_experiment.py
```

---

## 4. Expected Output & Findings
- Provenance accurately records inserted indices, dropped indices, and permuted ordering.
- `compare_counterfactual_runs` outputs exact metric deltas (e.g., retrieval coverage $\Delta = -25.0\%$, query-answer alignment $\Delta = -22.5\%$).
- The report explicitly flags `causal_claim_supported: False` and adds the warning: *"Counterfactual comparison is a sensitivity clue, not proof of gold correctness or causal effect."*

For detailed delta breakdowns and methodological constraints, see [analysis.md](analysis.md).

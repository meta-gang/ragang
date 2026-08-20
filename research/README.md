# RAGANG Research Artifacts Package

This package provides deterministic, offline-reproducible research experiments demonstrating RAGANG's core evaluation capabilities and diagnostic workflows.

---

## Experiment Index

| Experiment Suite | Focus Area | Key Hypothesis & Objective | Reproduction Command |
| --- | --- | --- | --- |
| **[Experiment A: Cycle Failure Diagnosis](cycle_failure_analysis/README.md)** | Cyclic & Agentic RAG | Bounded `max_steps` and lineage tracing isolate non-converging loops without stalling the system. | `python research/cycle_failure_analysis/run_experiment.py` |
| **[Experiment B: Counterfactual Robustness](counterfactual_robustness/README.md)** | Retrieval Perturbation Probes | Deterministic context manipulations (distractor, conflict, noise, dropout, shuffle) reveal generator sensitivity without gold data. | `python research/counterfactual_robustness/run_experiment.py` |
| **[Experiment C: Evaluator Failure Detection](evaluator_failure_detection/README.md)** | Evaluator Health & Trust | Distinguishes calculated zero scores (`0.00%`) from unevaluated errors (`not evaluated`), isolating judge crashes. | `python research/evaluator_failure_detection/run_experiment.py` |

---

## Running All Experiments

All experiments are designed to run using Python 3.13+ with standard local dependencies (no external API keys or live vector databases required):

```bash
# Run Experiment A
python research/cycle_failure_analysis/run_experiment.py

# Run Experiment B
python research/counterfactual_robustness/run_experiment.py

# Run Experiment C
python research/evaluator_failure_detection/run_experiment.py
```

---

## Scientific & Interpretation Constraints

1. **Deterministic Reproducibility**: All experiments use explicit pseudorandom seeds and deterministic fake adapters.
2. **Non-Causal Interpretation**: Counterfactual sensitivity metrics ($\Delta$) quantify observed empirical divergence between runs; they do not prove formal causality.
3. **No Fabricated Benchmarks**: These artifacts demonstrate methodology correctness and failure diagnosis rather than synthetic benchmark leaderboards.

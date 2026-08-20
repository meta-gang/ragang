# Research Experiment Design Guide

## 1. Overview

This document specifies the experimental design framework for evaluating RAG architectures in RAGANG. RAGANG supports a variety of pipeline topographies:
- **Linear RAG**: Sequential `Input → Retrieval → Generation → E2E`
- **Branching / Multi-Retriever RAG**: Hybrid retrieval (e.g., dense + sparse) with downstream merge
- **Self-Corrective / Retry RAG**: Iterative refinement loops conditioned on internal verification
- **Agentic / Cyclic RAG**: Dynamic multi-step workflows bounded by `max_steps`
- **GraphRAG Module Instrumentation**: Execution tracing and metric evaluation of graph retriever modules

---

## 2. Controlled Experiment Methodologies

### 2.1 Cycle Failure & Termination Analysis
- **Goal**: Evaluate how iterative / cyclic workflows behave under edge cases (e.g., unresolvable queries, degenerative retrieval loops).
- **Independent Variables**: `max_steps` threshold, loop termination predicates, retriever mode (`focused`, `noisy`, `empty`).
- **Dependent Metrics**: Number of execution steps, module revisit count, total execution latency, termination reason (`answer`, `max_steps`, `module_error`), failed ancestry paths.
- **Hypothesis**: Bounded execution tracing prevents infinite loops and produces deterministic causal ancestry graphs for root-cause diagnosis.

### 2.2 Counterfactual Retrieval Robustness
- **Goal**: Measure generator sensitivity to controlled perturbations of retrieved contexts without gold references.
- **Perturbation Techniques**:
  - `distractor_injection`: Insertion of irrelevant factual passages at random/front/end positions.
  - `conflict_injection`: Insertion of contradictory evidence.
  - `noisy_context_injection`: Insertion of low-quality or corrupted documents.
  - `retrieval_dropout`: Subsampling retrieved documents.
  - `retrieval_shuffle`: Permuting context order to assess positional bias.
- **Dependent Metrics**: Metric deltas ($\Delta$), evaluator coverage, generation stability.
- **Interpretation Constraint**: Sensitivity deltas represent observed empirical differences across deterministic runs; they do not constitute proven causal claims about general LLM reasoning.

### 2.3 Evaluator Failure Detection & Health Isolation
- **Goal**: Demonstrate how RAGANG distinguishes authentic system failures from evaluator breakdown.
- **Failure Scenarios**:
  - Malformed LLM judge JSON response
  - Evaluator API timeout or rate-limit
  - Empty retrieval input (`ret_docs = []`)
  - Insufficient sample size for dispersion metrics
- **Expected Behavior**: Evaluator records `did_eval = False`, stores `failure.type` and `failure.message`, and excludes the failed evaluation from score averages.

---

## 3. Best Practices for Reproducible Research

1. **Deterministic Random Seeds**: Explicitly set the integer `seed` in perturbation functions and fake adapters.
2. **Isolate Environment Effects**: Record OS, Python version, dependencies, and configuration fingerprint with all experimental results.
3. **Multi-Run Repetitions**: Perform repeated evaluations across identical query sets to compute variance and agreement metrics.
4. **Publish Complete Artifacts**: Package reproduction scripts, data fixtures, and configuration dumps alongside published findings.

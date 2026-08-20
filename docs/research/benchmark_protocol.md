# RAGANG Research Benchmark Protocol

## 1. Principles of Ground-Truth-Free Benchmarking

Traditional RAG benchmarks (e.g., RGB, CRUD, RAGAS-bench) typically rely on curated gold-standard reference answers or paired ground-truth documents. In practical enterprise and research settings, obtaining verified gold answers for dynamic corpora is expensive, brittle, and often impossible.

RAGANG establishes a **ground-truth-free evaluation protocol** governed by four core principles:

1. **Honest Evaluator State**: An evaluation score is valid *only* if all declared input prerequisites are satisfied and calculation completes without exception. Evaluator failures (e.g., malformed LLM outputs, timeouts, unsupported inputs) must be recorded as explicit `not_evaluated` states with typed failure diagnostics—never fabricated as `0.0` or `1.0`.
2. **Metric Heterogeneity Isolation**: Metrics have distinct ranges, units, and optimization directions (e.g., cosine distance vs. claim-level overlap vs. latency in ms). Metrics are never aggregated into an arbitrary single "Overall Score" or used to compute an automatic best-to-worst module ranking.
3. **Trace-Grounded Multi-Step Diagnosis**: Complex graph and agentic flows (branching, retry loops, self-correction cycles) produce rich execution lineages. Diagnosis must be derived from observed execution events (module revisits, parentage, step termination) rather than post-hoc speculation.
4. **Non-Causal Counterfactual Sensitivity**: Perturbation probes (e.g., distractor injection, retrieval dropout, shuffling) measure system sensitivity to context variations. Reports explicitly record declared perturbation parameters without claiming unverified semantic causality.

---

## 2. Experimental Setup & Configuration Fingerprinting

To guarantee reproducibility across research runs:

### Configuration Fingerprint
Every evaluation run in RAGANG computes a deterministic 16-character SHA-256 configuration fingerprint based on:
- DAG topology and module adjacency (`flow_graph`)
- Module implementations and source code fingerprints
- Declared public hyperparameters (e.g., `top_k`, `temperature`, `max_steps`)
- Metric definitions, parameter bindings (`param_refs`), and evaluator model specifications

### Run Comparison Rules
When comparing a baseline run against a candidate run:
- If fingerprints match, the comparison isolates query-level variations under identical pipeline semantics.
- If fingerprints differ, RAGANG emits an explicit warning indicating that metric deltas cannot be attributed to an isolated variable.

---

## 3. Evaluation Dimensions & Metric Registry

| Evaluation Scope | Metric Category | Primary Objective | Inputs | Key Considerations |
| --- | --- | --- | --- | --- |
| **Retrieval** | Vector / Distance | Measure query-document semantic proximity | `query`, `ret_docs` | Rejects empty retrieval as not-evaluated rather than fabricating 0. |
| **Retrieval** | Lexical Overlap | Token/n-gram coverage without gold docs | `query`, `ret_docs` | Bounded [0.0, 100.0]%; 0.0 is a valid score when evaluated. |
| **Generation** | Faithfulness / Grounding | Verify claims against retrieved contexts | `ret_docs`, `gen` | Requires claim extraction parsing; parse failure = not-evaluated. |
| **Generation** | Consistency | Internal generation stability | `gen_samples` | Requires multi-sample generation; single sample = not-evaluated. |
| **End-to-End** | Query-Answer Relevance | Assess final answer utility | `query`, `gen` | Uses LLM judge or cross-encoder; tracks evaluator provenance. |
| **Workflow** | Graph Execution | Measure cycle latency & termination | `execution_trace` | Tracks `max_steps`, module revisits, and failed ancestry paths. |

---

## 4. Reporting Standards & Statistical Metrics

For multi-query and multi-run experiments:
- **Evaluator Coverage**: `evaluated_count / (evaluated_count + not_evaluated_count)`
- **Central Tendency**: Arithmetic mean across valid evaluated scores only.
- **Dispersion**: Population standard deviation ($N \ge 2$) reported as descriptive variance. No unverified statistical confidence intervals are fabricated.
- **Latency Breakdown**: Per-module and end-to-end latency distributions in seconds.

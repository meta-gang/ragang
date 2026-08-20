# Limitations and Boundary Definition

## 1. Explicit Framework Boundaries

To ensure evaluator trust and scientific integrity, RAGANG clearly states what is supported and what is outside the framework's scope.

### Supported Capabilities
- **Ground-Truth-Free RAG Evaluation**: Evaluates retrieval, generation, and end-to-end alignment without requiring gold-standard answers.
- **Workflow & Graph Execution Tracing**: Tracks module ancestry, revisits, latency, and step-level failures in arbitrary DAGs and cyclic workflows.
- **Evaluator Health & Provenance Tracking**: Distinguishes valid zero scores from unevaluated errors; isolates evaluator crashes.
- **Conservative Automated Diagnostics**: Categorizes observed runtime facts (`observations`) separately from hypothesized root causes (`inferences`).
- **Deterministic Counterfactual Perturbations**: Provides structured context injection/dropout tools with reproducible metadata.
- **GraphRAG Module Instrumentation**: Evaluates GraphRAG retrievers as black-box or white-box pipeline modules (inputs, outputs, latency, text similarity).

### Explicitly Non-Supported Scope
- **No Automatic Knowledge Graph Construction Evaluation**: RAGANG does not score entity extraction precision, relation triple completeness, or community hierarchy quality inside external graph stores.
- **No Causal Inference Guarantees**: Metric deltas from counterfactual runs reflect observed empirical variance under specific perturbations, not mathematical proof of causality.
- **No Perfect LLM Judge Calibration**: While RAGANG records judge provenance and parse failures, LLM-as-a-judge metrics remain vulnerable to inherent model biases (verbosity bias, self-preference).
- **No Universal "Leaderboard Score"**: RAGANG refuses to collapse heterogeneous metrics into an arbitrary aggregate scalar or compute global best/worst rankings.

---

## 2. Research & Practical Considerations

| Consideration Area | Limitation | Recommendation |
| --- | --- | --- |
| **Statistical Generalization** | Standard deviation is descriptive of observed runs; small sample sizes do not yield reliable confidence intervals. | Report sample sizes ($N$) and avoid overinterpreting variance on $< 30$ queries. |
| **Judge Consistency** | LLM evaluators may exhibit non-deterministic verdicts across temperature variations. | Fix temperature to 0.0 or perform multi-run judge agreement analysis. |
| **Domain Specificity** | Built-in lexical and vector metrics do not replace domain-specific correctness criteria in regulated domains (e.g., medicine, law). | Register domain-specific custom metrics via `CustomMetric` with explicit parameter contracts. |
| **Graph Complexity** | Highly cyclic agentic pipelines may consume significant token/compute resources if `max_steps` is unbounded. | Always configure a reasonable `max_steps` threshold in production containers. |

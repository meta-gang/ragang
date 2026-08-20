# RAGANG Research & Development Roadmap

## Vision
To establish the de facto open standard for ground-truth-free evaluation, diagnostic tracing, and robustness benchmarking across linear, agentic, and graph-based retrieval-augmented generation systems.

---

## Phase Milestones

### 2026 Core Modernization (Completed)
- [x] **Ground-Truth-Free Core**: Distinguish evaluated zero from `not_evaluated`; isolate metric failures without pipeline aborts.
- [x] **Safe Evaluator Provenance**: Redacted config fingerprints, adapter model metadata, and sanitized error serialization.
- [x] **Execution Trace & Diagnostics**: Full DAG and cycle execution lineage tracking, revisit counters, `max_steps` termination, and separated observations/inferences.
- [x] **Deterministic Counterfactual Framework**: Perturbation engine (`distractor`, `conflict`, `noise`, `dropout`, `shuffle`) with non-causal comparison.
- [x] **Browser-Verified Web UI**: Modernized React/TypeScript dashboard with DAG visualization, real-time WebSocket telemetry, and honest metric rendering.

### Near-Term Research Focus (Q3–Q4 2026)
- [ ] **Multi-Run Distribution Analysis**: Extended statistical aggregation across repeated runs (bootstrapping for large sample sizes, inter-annotator agreement metrics for LLM judges).
- [ ] **Judge Reliability Benchmarking**: Quantifying LLM judge self-consistency, positional sensitivity, and prompt sensitivity under fixed temperature regimes.
- [ ] **Token & Energy Telemetry**: Granular token consumption and latency profiling per pipeline module.
- [ ] **Agentic Tool-Use Diagnostics**: Specialized observation rules for tool call retries, parameter parsing errors, and multi-turn conversational RAG state.

### Long-Term Research Explorations (2027+)
- [ ] **Adaptive Test-Query Synthesis**: Active-learning-driven query generation targeting identified pipeline weak points (e.g., low context coverage clusters).
- [ ] **Standardized Robustness Leaderboards**: Open benchmark datasets evaluating retrieval noise tolerance and refusal calibration across public LLM foundations.
- [ ] **Federated Evaluation Protocols**: Privacy-preserving evaluation telemetry for enterprise multi-tenant deployments.

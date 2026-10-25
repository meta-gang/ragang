# RAGANG

**Ground-Truth-Free RAG Evaluation and Diagnosis Framework**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Architecture: DAG & Cyclic Tracing](https://img.shields.io/badge/Architecture-DAG%20%26%20Cyclic%20Tracing-purple.svg)](docs/graph-rag/execution-trace.md)
[![Docs](https://img.shields.io/badge/Docs-Index-orange.svg)](docs/README.md)

RAGANG is a research-grade Python framework designed for **ground-truth-free evaluation and diagnostic tracing** of Retrieval-Augmented Generation (RAG) systems. It evaluates linear, branching, retry, and cyclic agentic workflows step-by-step without requiring curated gold-standard reference answers, while isolating evaluator failures from authentic pipeline behaviors.

---

## 1. Problem Definition: Beyond Scalar Answer Scoring

In real-world enterprise deployments and scientific benchmarking, evaluating a RAG pipeline based solely on a single end-to-end answer score is fundamentally insufficient:

1. **Hidden Intermediate Failures**: An answer may appear plausible while retrieval was completely empty (hallucination under zero context) or irrelevant context was retrieved.
2. **Evaluator Health Conflation**: When an LLM judge encounters a timeout, rate limit, or schema parse error, naive frameworks report `0.0` or crash. Fabricating `0.0` distorts benchmarks by conflating evaluator breakdown with genuine generation failure.
3. **Loss of Cyclic & Agentic Lineage**: Multi-step, iterative refinement, or cyclic self-correction loops can spin infinitely or revisit failed states without leaving an inspectable execution trace.
4. **Metric Heterogeneity Pollution**: Collapsing incompatible metrics (e.g., cosine distance, token overlap %, BLEU, ms latency) into an arbitrary "Overall Score" creates mathematically invalid comparisons.

---

## 2. System Architecture

RAGANG provides an observable, multi-layered evaluation lifecycle:

```
┌──────────────┐     ┌──────────────┐
│  Documents   │     │   Queries    │
└──────┬───────┘     └──────┬───────┘
       │                    │
       ▼                    ▼
┌───────────────────────────────────┐
│           RAG Pipeline            │  ◄── Linear, Branching, Retry, Cyclic DAGs
└─────────────────┬─────────────────┘
                  │
                  ▼
┌───────────────────────────────────┐
│          Execution Trace          │  ◄── Step Ancestry, Revisits, Latency, max_steps
└─────────────────┬─────────────────┘
                  │
                  ▼
┌───────────────────────────────────┐
│        Metrics & Evaluators       │  ◄── Retriever, Generator, E2E Evaluators
└─────────────────┬─────────────────┘
                  │
                  ▼
┌───────────────────────────────────┐
│      Evaluator Health Record      │  ◄── Evaluated (inc. Valid 0.0) vs. Not Evaluated
└─────────────────┬─────────────────┘
                  │
                  ▼
┌───────────────────────────────────┐
│     Evidence-Based Diagnosis      │  ◄── Explicit Observations + Inferred Hypotheses
└─────────────────┬─────────────────┘
                  │
                  ▼
┌───────────────────────────────────┐
│     Interactive Web Dashboard     │  ◄── Real-Time DAG Visualizer & Metric Trends
└───────────────────────────────────┘
```

---

## 3. Supported Pipeline Topologies

| Workflow Topology | Architectural Scope | Key Capabilities & Boundary Constraints |
| --- | --- | --- |
| **Linear RAG** | `Input → Retrieval → Generation → E2E` | Full step latency profiling, lexical & vector metric evaluation. |
| **Branching / Merge RAG** | Multi-retriever hybrid search, conditional branches | Dynamic conditional `next` routing, `AND`/`OR` dependency resolution. |
| **Retry & Self-Corrective RAG** | Iterative query rewrite, verification loops | Bounded execution via `max_steps`, loop detection, revisit counters. |
| **Agentic Workflow** | Multi-step decision and tool-augmented flows | Step-level input/output key capture, failure ancestry paths. |
| **Graph Workflow** | Arbitrary directed graphs with cycles | Deterministic cycle optimization in `Status`, state persistence. |
| **GraphRAG Module Instrumentation** | Instrumentation of GraphRAG retrievers | Evaluates graph retrievers as black-box/white-box modules (inputs, outputs, latency, similarity). |

---

## 4. Key Research Contributions

### 1. Evaluation Reliability & Evaluator Provenance
- **Honest State Handling**: Distinguishes valid calculated zero scores (`0.00%`) from unevaluated errors (`not evaluated`).
- **Failure Isolation**: Metric exceptions or judge parse failures never crash query execution; failures are isolated in `Performance` objects with typed error metadata.
- **Safe Provenance**: Computes a deterministic 16-character SHA-256 `config_fingerprint` tracking module source, public hyperparameters, and adapter models without logging credentials or raw text.

### 2. Execution Trace Based Diagnosis
- **Causal Ancestry**: Records execution lineage (`execution_id`, `parent_execution_ids`, `execution_index`, `revisit_count`) across cyclic DAGs.
- **Separated Diagnostics**: Separates verifiable runtime facts (`observations`, e.g., `retrieval.empty`, `graph.module_revisited`) from diagnostic hypotheses (`inferences`, e.g., `answer_without_retrieved_evidence`).

### 3. Gold-Free Robustness & Counterfactual Sensitivity
- **Deterministic Perturbations**: Built-in context manipulation tools (`distractor_injection`, `conflict_injection`, `noisy_context_injection`, `retrieval_dropout`, `retrieval_shuffle`).
- **Non-Causal Interpretation**: Explicitly reports empirical sensitivity deltas ($\Delta$) without making unsubstantiated causal claims.

---

## 5. Explicit Limitations & Boundaries

To preserve research integrity, RAGANG clearly declares what is outside its scope:
- ❌ **No Automatic Knowledge Graph Quality Scoring**: RAGANG does not evaluate entity extraction accuracy, triple validity, or community clustering inside external KG databases.
- ❌ **No Causal Guarantees**: Metric deltas from perturbation experiments indicate empirical sensitivity under specified parameters, not mathematical causal proofs.
- ❌ **No Perfect LLM Judge Calibration**: While parse failures and judge models are tracked, LLM evaluators retain inherent bias and prompt sensitivity.
- ❌ **No Single "Universal Leaderboard Score"**: Heterogeneous metrics are never averaged into a single scalar; directionality and units are preserved per metric.

---

## 6. Quickstart & Installation

### Requirements
- Python 3.13 or higher

### Installation
```bash
# Clone the repository
git clone https://github.com/meta-gang/ragang.git
cd ragang

# Create and activate virtual environment
python3.13 -m venv .venv
source .venv/bin/activate

# Install in editable mode
python -m pip install -e .

# Verify CLI
ragang --help
```

### Initializing a Project
```bash
# Initialize a new RAGANG workspace
ragang init my_rag_project
cd my_rag_project
```

---

## 7. Workflow Example

### Start locally without API keys

```bash
ragang init my_rag_project
cd my_rag_project
ragang run -F sample_rag -Q custom/queries.txt
ragang show -F sample_rag
```

The generated project defaults to an offline, in-memory retrieval and extractive
answer demonstration. It verifies the real execution, metric, history, and dashboard
workflow without contacting a model server or changing a vector database. These
fixture scores are **not a model-quality benchmark**. The generated README explains
the `RAGANG_PROFILE=ollama` path for actual local generation and embeddings.

### Connect your own modules

Implement `execute()` in `CustomModule`, `RetrievalModule`, or `GenerationModule`;
the public module classes are contracts, not ready-made retrievers or generators.
Return `ret_docs: list[str]` for retrieved text and `gen: str` for an answer.
A `gen` with outgoing modules is a draft; a leaf answer finishes the flow.
Use `terminal=True` with a non-empty `gen` for explicit early completion, or
`terminal=False` to continue. See the generated `manager.py` for a runnable flow
and [the execution contract](docs/graph-rag/execution-trace.md).

```python
from ragang.metrics.builtin.generator.llm_based import A2RYNFaithfulnessMetricSingleCall

# local_judge is your configured local BaseLLMAdapter implementation.
faithfulness = A2RYNFaithfulnessMetricSingleCall(
    ["ret.ret_docs", "output.gen"], llm_adapter=local_judge,
)
```

This optional judge evaluates support in the supplied documents, not absolute
factual correctness. Its result records the assessed scope and claim verdicts.
Malformed judgments are not evaluated; a valid negative verdict remains zero.

### Compare evaluations

```bash
# Run twice after changing one pipeline setting, keeping the questions fixed.
ragang run -F sample_rag -Q custom/queries.txt
ragang compare -F sample_rag --json
```

Comparison deltas use paired questions with valid scores on both sides and
compatible evaluator configurations. Whole-run summaries remain available, with
unmatched, failed, or incompatible samples explicitly reported. The dashboard
separates query completion, evaluator coverage, and each metric's declared scale.
See [the persona-driven hardening report](docs/validation/PERSONA_HARDENING_2026.md)
for changed behavior, checks, and remaining limits.

---

## 8. Reproducible Research Artifacts

RAGANG includes dedicated research experiment suites in [`research/`](research/README.md):
- [Experiment A: Cycle Failure & Max Steps Diagnosis](research/cycle_failure_analysis/README.md)
- [Experiment B: Counterfactual Robustness Probes](research/counterfactual_robustness/README.md)
- [Experiment C: Evaluator Failure & Health Isolation](research/evaluator_failure_detection/README.md)

---

## 9. Documentation Directory

For in-depth technical documentation, refer to the [Documentation Index](docs/README.md):

- **System Design**: [Architecture Overview](docs/architecture/overview.md) | [Graph & Cyclic Tracing](docs/graph-rag/execution-trace.md)
- **Evaluation Contract**: [Evaluation Contract](docs/evaluation/EVALUATION.md) | [Metric Catalog](docs/evaluation/metrics.md) | [Counterfactual Guide](docs/evaluation/counterfactual.md)
- **Research Protocols**: [Benchmark Protocol](docs/research/benchmark_protocol.md) | [Experiment Design](docs/research/experiment_design.md) | [Limitations](docs/research/limitations.md) | [Roadmap](docs/research/roadmap.md)
- **Validation**: [Final Validation Report](docs/validation/FINAL_VALIDATION_REPORT.md) | [Browser Acceptance Validation](docs/validation/BROWSER_ACCEPTANCE.md)
- **Security & Ops**: [Credential Security Audit](docs/security/CREDENTIAL_EXPOSURE.md) | [Dependency Risk Assessment](docs/security/DEPENDENCY_RISK.md) | [Development Guide](docs/development/DEVELOPMENT.md) | [Release Policy](docs/development/RELEASE.md)

---

## 10. Development & Testing

Run full backend test suite:
```bash
python -m unittest discover -s tests -v
python -m compileall -q ragang tests
```

---

## 11. License

This project is licensed under the terms of the [MIT License](LICENSE).

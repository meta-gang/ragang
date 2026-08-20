# Experiment A: Cycle Failure & Max Steps Diagnosis

## 1. Hypothesis & Objective
In complex agentic and self-corrective RAG systems, iterative query refinement and critique loops can either converge toward an evidence-grounded answer or diverge into infinite loops due to unresolvable queries or adversarial context.

**Hypothesis**:
1. Without bounded limits, cyclic pipelines hang indefinitely or overflow recursion stacks.
2. RAGANG's `max_steps` bounded execution policy guarantees termination while preserving complete step ancestry (`parent_execution_ids`, `execution_index`, `revisit_count`) and automated diagnosis for post-mortem debugging.

---

## 2. Experimental Setup

Two controlled pipeline topologies are compared:
- **Scenario 1 (Converging Cycle)**: A self-corrective loop where `critic` routes back to `retriever` until 2 refinement iterations complete, then routes to `generator`.
- **Scenario 2 (Non-Converging Loop)**: A degenerate cyclic graph where `infinite_loop` continuously routes to itself, bounded by `max_steps=4`.

---

## 3. How to Run

```bash
python research/cycle_failure_analysis/run_experiment.py
```

---

## 4. Expected Output & Findings
- **Converging Loop**: 6 total execution steps, 2 module revisits (`revisit_count=1` for `retriever` and `critic`), termination reason `answer`.
- **Non-Converging Loop**: Terminates at exactly step 4, raises `FlowExecutionLimitException`, flags `terminated=True`, sets `termination_reason="max_steps"`, and emits `graph.max_steps_reached` and `graph.module_revisited` diagnostic observations.

For full interpretation and diagnostic lineage analysis, see [analysis.md](analysis.md).

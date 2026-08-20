# Experiment C: Evaluator Failure Detection & Health Isolation

## 1. Hypothesis & Objective
LLM-as-a-judge evaluators and external embedding APIs frequently experience transient failures in production environments: schema parsing errors, API rate-limiting, network timeouts, and empty context inputs.

**Hypothesis**:
1. Conflating evaluator breakdown with a numeric failure score (`score = 0.0`) heavily pollutes benchmark averages (e.g., distorting a true 95.0% performance down to 57.0%).
2. RAGANG's explicit `not evaluated` state preserves metric calculation integrity across surviving evaluators while attaching structured failure diagnostics (`type`, `message`).

---

## 2. Experimental Setup

The experiment tests four critical error and edge-case conditions:
1. **Valid Calculated Zero**: Legitimate zero score (`score = 0.00%`, `did_eval = True`).
2. **Malformed Judge Response**: LLM judge output failing schema extraction (`ValueError`, `did_eval = False`).
3. **API Network Timeout**: Evaluator endpoint timeout (`TimeoutError`, `did_eval = False`).
4. **Pipeline Fault Isolation**: Pipeline containing 2 failing evaluators completes query execution without crashing, recording `coverage: 50.0%` (2/4) and triggering `evaluator_health_risk` diagnosis.

---

## 3. How to Run

```bash
python research/evaluator_failure_detection/run_experiment.py
```

---

## 4. Expected Output & Findings
- Evaluated zero score is preserved as numeric `0.00%`.
- Broken judge metrics are cleanly classified as `not evaluated` with redacted error types.
- Pipeline execution generates a valid answer without crashing on metric errors.
- Comparative statistics demonstrate that RAGANG's honest mean (95.0%) avoids the severe -38.0% distortion produced by naive `0.0` fallbacks.

For full mathematical distortion analysis, see [analysis.md](analysis.md).

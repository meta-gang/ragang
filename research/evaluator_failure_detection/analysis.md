# Analysis: Evaluator Failure Detection & Health Isolation

## 1. Evaluator State Matrix

| Scenario | Raw Execution State | RAGANG Performance State | `did_eval` | Rendered Display | Error Diagnostics Attached |
| --- | --- | --- | --- | --- | --- |
| **Legitimate Zero Overlap** | Normal return | `Performance(score=0.0, _eval=True)` | `True` | `0.00%` | None |
| **Malformed Judge JSON** | `ValueError` raised | `Performance(metric="...", _eval=False)` | `False` | `not evaluated` | `type: ValueError`, message redacted |
| **Judge Endpoint Timeout** | `TimeoutError` raised | `Performance(metric="...", _eval=False)` | `False` | `not evaluated` | `type: TimeoutError`, message redacted |
| **Empty Retrieved Context** | Explicit empty check | `Performance(metric="...", _eval=False)` | `False` | `not evaluated` | `type: empty_input` |

---

## 2. Statistical Distortion Impact

Consider a batch of 5 queries where 3 succeed with high quality ($S = \{100.0, 95.0, 90.0\}$) and 2 queries encounter transient judge timeouts ($F = 2$):

$$\text{Honest Evaluator Mean (RAGANG)} = \frac{100.0 + 95.0 + 90.0}{3} = 95.00\% \quad (\text{Coverage} = 3/5 = 60.0\%)$$

$$\text{Distorted Fallback Mean (Naive)} = \frac{100.0 + 95.0 + 90.0 + 0.0 + 0.0}{5} = 57.00\%$$

$$\text{Artificial Distortion} = 57.00\% - 95.00\% = \mathbf{-38.00\%}$$

### Key Insights
1. **Preventing Erroneous Pipeline Abandonment**: A 38% artificial penalty would lead researchers to wrongly conclude that generation quality deteriorated, when in fact only the judge endpoint failed.
2. **Transparent Coverage Telemetry**: By reporting `Evaluator Coverage: 60.0%`, RAGANG flags evaluator health risks while preserving true mean scores among valid responses.

---

## 3. Scientific Limitations
- While RAGANG isolates runtime exceptions and malformed outputs, it does not guarantee that a successful judge output is free of model bias (e.g., self-preference or length bias).
- Evaluator health metrics indicate technical execution success, not statistical judge calibration.

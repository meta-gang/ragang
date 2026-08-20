# Analysis: Counterfactual Retrieval Robustness

## 1. Perturbation Characteristics & Verification

| Perturbation Kind | Target Modification | Deterministic Output Attributes |
| --- | --- | --- |
| `distractor_injection` | Insert 1 irrelevant doc at index 0 (`front`) | `seed: 42`, `insertion_indices: [0]`, `variant_count: 5` |
| `conflict_injection` | Insert 1 conflicting doc at index 4 (`end`) | `seed: 42`, `insertion_indices: [4]`, `variant_count: 5` |
| `noisy_context_injection` | Insert 1 noise string randomly | `seed: 42`, `insertion_indices: [0]`, `variant_count: 5` |
| `retrieval_dropout` | Randomly drop 2 out of 4 documents | `seed: 42`, `dropped_indices: [0, 3]`, `variant_count: 2` |
| `retrieval_shuffle` | Permute all document positions | `seed: 42`, `source_indices: [2, 1, 3, 0]`, `variant_count: 4` |

---

## 2. Sensitivity Metric Deltas (Baseline vs Distractor)

| Evaluation Stage & Scope | Metric Name | Baseline Mean | Candidate Mean | Observed Delta ($\Delta$) |
| --- | --- | --- | --- | --- |
| **Retrieval Stage** | Query-context coverage | 90.00% | 65.00% | **-25.00%** |
| **Generation Stage** | Answer-evidence overlap | 85.00% | 85.00% | **0.00%** |
| **End-to-End Scope** | Query-answer alignment | 81.00% | 58.50% | **-22.50%** |

### Key Diagnostic Observations
1. **Retrieval Degradation**: Inserting an irrelevant distractor at the front reduced the query-context coverage ratio from 90% to 65%.
2. **Generation Hallucination / Contamination**: While the generator maintained high lexical adherence to the context (85%), the answer incorporated distractor facts, causing end-to-end query alignment to drop by 22.5%.

---

## 3. Methodological Boundaries: Non-Causality
- RAGANG records user-supplied role labels (e.g., `distractor`, `conflict`) without verifying whether an injected passage is semantically distracting or true/false.
- Metric differences reflect sensitivity to the specified perturbation setup and must not be cited as mathematical proofs of causal mechanisms in LLM generation.

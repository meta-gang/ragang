# Gold-free counterfactual retrieval probes

## 목적

Counterfactual support는 같은 RAG workflow에 통제된 retrieval 변형을 넣고 metric,
evaluator coverage, latency, execution trace가 얼마나 달라지는지 보는 lightweight sensitivity
도구입니다. Reference answer나 gold document를 요구하지 않습니다.

지원 변형:

- `distractor_injection`
- `conflict_injection`
- `noisy_context_injection`
- `retrieval_dropout`
- `retrieval_shuffle`

Injection document는 사용자가 제공합니다. RAGANG은 label을 provenance에 기록하지만 실제로
distracting/conflicting/noisy한지 검증하지 않습니다.

## 변형 생성

```python
from ragang import perturb_retrieval

variant = perturb_retrieval(
    baseline_docs,
    kind="conflict_injection",
    injected_documents=reviewed_conflicting_docs,
    insertion="random",  # front, end, random
    seed=2026,
)

candidate_docs = variant["documents"]
provenance = variant["provenance"]
```

Baseline sequence는 복사되며 mutate되지 않습니다. Provenance는 kind, seed, baseline/variant
count, changed 여부와 injection/drop/shuffle index를 기록하고 문서 본문은 복사하지 않습니다.

Dropout 예시:

```python
variant = perturb_retrieval(
    baseline_docs,
    kind="retrieval_dropout",
    drop_count=2,
    seed=11,
)
```

## 비교

Baseline과 candidate를 같은 query text로 실행해 serialized State mapping을 준비합니다.
실제 engine이 run마다 새 query ID를 발급해도 비교기는 query text multiset으로 pair 수를
계산하며, query text 자체는 report에 복사하지 않습니다. 구형 payload처럼 query text가
없을 때만 query ID 교집합으로 fallback합니다.

```python
from ragang import compare_counterfactual_runs

report = compare_counterfactual_runs(
    baseline_states,
    candidate_states,
    perturbation=variant["provenance"],
)
```

Report는 일반 `compare_runs` 결과에 perturbation provenance, paired query 수와
`pairing_basis`,
`causal_claim_supported=false`와 해석 warning을 추가합니다. Metric delta의 방향은 catalog를
개별 확인해야 합니다.

## 권장 protocol

1. Query, generator, prompt, adapter/model, `max_steps`를 고정합니다.
2. Baseline document order와 perturbation seed를 보존합니다.
3. Injection label은 사람이 검토하고 원본 corpus와 provenance를 별도로 관리합니다.
4. Configuration fingerprint, paired query count, evaluator coverage를 score delta보다 먼저
   확인합니다.
5. 한 seed/한 query의 결과를 robustness 결론으로 일반화하지 않습니다.
6. Multiple seed/query에서 metric별 분포를 보고 failure/not-evaluated 변화도 보고합니다.

## 해석 한계

- 이 비교는 observed sensitivity이지 causal estimate가 아닙니다.
- LLM judge가 noise나 conflict에 관대할 수 있으며 score 불변은 robustness 증명이 아닙니다.
- Retrieval shuffle은 order-sensitive generator/retriever 효과를 함께 포함할 수 있습니다.
- Injection은 document count와 context budget을 바꾸므로 두 효과를 분리하지 않습니다.
- Gold가 없으므로 answer correctness나 injected label correctness를 확정하지 않습니다.

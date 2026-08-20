# Evaluation contract

## 핵심 의미론

RAGANG은 gold 없이 실행 가능한 evaluation/diagnosis framework입니다. Gold 기반
`PrecisionMetric`과 `RandomDocumentInjectionEffect`는 optional metric이며 core contract가
아닙니다.

`Performance`는 다음 상태를 구분합니다.

| 상태 | 조건 | 해석 |
| --- | --- | --- |
| Evaluated | `did_eval=true`이고 score가 finite real | 실제 계산 결과. `0`도 유효할 수 있음 |
| Not evaluated | `did_eval=false` | 입력 부족, unsupported workflow, adapter/judge/parse 실패 |
| Invalid evaluated result | `did_eval=true`지만 NaN/Inf/non-numeric/bool | engine이 `not evaluated`로 변환하고 failure 기록 |

직렬화 시 NaN/Inf를 `null`로 만드는 것은 JSON 안전장치일 뿐, 평가 성공을 의미하지
않습니다. Engine 경계의 validation이 evaluator health와 직렬화 결과를 일치시킵니다.

## Evaluator provenance와 failure

각 metric 결과에는 다음 안전한 provenance가 붙습니다.

- Metric implementation과 source fingerprint
- `param_refs`
- Bounded public settings
- LLM/embedding adapter implementation과 공개 model name
- Failure type과 redacted/bounded message

API key, token, endpoint, header, prompt, document, answer, query, local path는 제외합니다.
`run_metadata.config_fingerprint`는 flow graph, module/metric 구현, 공개 설정,
`execution_policy.max_steps`를 포함합니다.

## 진단

`diagnosis.observations`는 runtime에서 직접 확인한 사실입니다. 예:

- `retrieval.empty`
- `evaluator.not_evaluated`
- `graph.module_revisited`
- `graph.execution_failed`
- `graph.max_steps_reached`

`diagnosis.inferences`는 가능한 원인 가설이며 `confidence`, `based_on`, `next_action`을
가집니다. Gold가 없으므로 root cause나 answer correctness를 확정하지 않습니다.

## 비교와 신뢰도

`compare_runs`는 stage/module/metric/unit가 같은 결과만 같은 metric으로 묶습니다. 각
metric에 다음을 반환합니다.

- mean, minimum, maximum
- population standard deviation(평가 표본 2개 이상)
- evaluated/not-evaluated count와 coverage
- baseline/candidate delta

전체 evaluator health, query 수, latency, configuration fingerprint도 함께 반환합니다.
표준편차는 관측된 실행의 분산 설명이며 confidence interval이나 통계적 유의성 주장이
아닙니다. Configuration이 다르면 단일 변경의 효과로 해석하지 말라는 warning이 붙습니다.

서로 다른 unit/range/direction의 metric을 평균하지 않습니다. Distance/variance처럼 낮을수록
좋은 metric과 similarity처럼 높을수록 좋은 metric을 한 “overall score”로 합치지 않습니다.

## Counterfactual

Retrieval perturbation은 gold-free sensitivity probe입니다. 동일 query와 명시된 seed를
사용해 baseline/candidate를 생성하고 provenance를 보존할 수 있습니다. 그러나 framework는
주입 문서의 의미적 label, 다른 조건의 동일성, 인과 효과를 증명하지 않습니다. 자세한
절차는 [counterfactual guide](counterfactual.md)에 있습니다.

## Metric 선택

하나의 metric으로 answer correctness, grounding, relevance, robustness를 모두 주장하지
않습니다. 목적별 최소 조합 예시는 다음과 같습니다.

- Retrieval utility: query-document similarity + empty retrieval observation
- Grounding: answer-context similarity 또는 claim-level faithfulness + evaluator health
- E2E relevance: answer-query similarity/judge + judge provenance
- Robustness: 동일 metric의 baseline/perturbation delta + coverage/configuration 확인
- Iterative workflow: module metric + execution trace + graph diagnosis

전체 식과 한계는 [metric catalog](metrics.md)에 있습니다.

# 2026 research alignment

기준일은 2026-08-20입니다. RAGANG의 정체성인 ground-truth-free evaluation과
WHY-oriented diagnosis에 직접 연결되는 1차 출처만 구현 결정에 사용했습니다.

## 근거와 반영

| 연구 근거 | RAGANG 결정 |
| --- | --- |
| [AgenticRAGTracer](https://aclanthology.org/2026.findings-acl.66/)는 최종 답변만이 아니라 hop/intermediate step을 검증해야 실패 위치를 찾을 수 있음을 보입니다. | Parent-child execution trace, module revisit, failed ancestry path, graph health를 구현했습니다. |
| [Dissecting GraphRAG](https://aclanthology.org/2026.tacl-1.29/)은 triple extraction, community clustering, report generation을 분해하고 graph construction coverage가 bottleneck이 될 수 있음을 분석합니다. | GraphRAG를 단일 마케팅 label로 점수화하지 않고 graph retriever/generator를 module로 분해해 계측하도록 문서화했습니다. KG 품질 자동 보증은 범위 밖입니다. |
| [CUB](https://aclanthology.org/2026.acl-long.1151/)은 다양한 realistic noisy context에서 holistic testing이 필요하고 synthetic setting만으로 일반화하기 어렵다는 점을 보입니다. | User-supplied distractor/conflict/noisy injection과 dropout/shuffle, seed/provenance, 비인과 warning을 추가했습니다. |
| [Redefining Retrieval Evaluation for RAG](https://aclanthology.org/2026.eacl-long.391/)은 전통 IR metric이 machine consumption과 distraction을 충분히 반영하지 못한다고 지적합니다. | Retrieval score 하나 대신 generation/grounding/E2E와 perturbation sensitivity를 함께 보며, empty retrieval/unsupported metric을 명시합니다. |
| [LLM Judges Can Be Too Generous in RAG Evaluation Without a Reference Answer](https://arxiv.org/abs/2607.12885)는 reference-free judge가 답변을 과대평가할 수 있어 calibration과 sensitivity 검증이 필요함을 보입니다. | Judge provenance, evaluator health, parse failure, coverage를 score와 분리하고 gold-free judge를 oracle로 표현하지 않습니다. |
| [Eval-Pair Matrix](https://arxiv.org/abs/2607.10626)는 evaluator/model 조합의 상호작용을 기록해야 자기편향 결론을 피할 수 있음을 제안합니다. | Metric/adapter implementation, model, public setting, configuration fingerprint를 저장합니다. |
| [RAGEC](https://aclanthology.org/2026.eacl-long.147/)은 RAG error를 stage별로 분해해 개선 우선순위를 찾습니다. | Retrieval/module/E2E observation과 보수적 inference를 분리합니다. 원 논문의 gold 기반 root-cause label은 가져오지 않습니다. |
| [FRANQ](https://aclanthology.org/2026.findings-acl.338/)은 factuality와 retrieved evidence faithfulness를 구분합니다. | Truthfulness/faithfulness/relevance metric을 같은 의미로 설명하지 않고 catalog에 limitation을 명시합니다. |

## 이번 채택

- Cycle-safe scheduler와 finite `max_steps`
- Hop-level execution trace와 frontend 전체 repetition 표시
- Finite numeric score validation, valid zero/not-evaluated 분리
- Metric coverage, range, variation과 configuration-aware comparison
- Lightweight gold-free counterfactual perturbation
- Raw unit를 보존하는 dashboard와 heterogeneous aggregate 제거

## 보류

- Multi-judge agreement, repeated-judge variance, bootstrap confidence interval
- Claim-level citation verification(실제 citation span이 있는 pipeline에 한정 필요)
- GraphRAG entity/triple/community 전용 quality metric
- Cluster-aware 대규모 statistical protocol
- Token/cost telemetry의 adapter 표준화

## 거부

- Single overall score 또는 단일 judge를 정답으로 취급하는 leaderboard
- Gold/reference를 core 실행의 필수 조건으로 만드는 변경
- 관측 근거 없이 pipeline을 자동 수정하는 agentic remediation
- RAG diagnosis와 무관한 범용 LLM observability 확장
- Metric 수를 늘리기 위한 중복 metric

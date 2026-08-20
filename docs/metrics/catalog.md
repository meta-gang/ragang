# Built-in metric catalog

## 공통 계약

모든 metric은 `Performance(score, unit, metric, did_eval)`을 반환합니다. Score가 finite
real이 아니거나 adapter/judge/parsing이 실패하면 `not evaluated`입니다. 유효한 0은
`did_eval=true, score=0`으로 유지합니다. 빈 집합의 평균, sample이 부족한 분산/순위,
표준 engine이 제공하지 않는 다중 generation 입력도 `not evaluated`입니다.

Range는 이론/구현상 범위이고 calibration을 의미하지 않습니다. “↑/↓”는 같은 metric과
동일 조건 안에서의 일반적 방향이며 서로 다른 metric을 합산하는 근거가 아닙니다.

## Retriever metrics

| Class | 목적·계산 | 입력 → 출력/방향 | 한계 | 미평가 조건 |
| --- | --- | --- | --- | --- |
| `KeywordMatchingMetric` | 문서 token 중 query token과 같은 비율을 문서별 계산 후 평균 | `query, ret_docs` → `%`, ↑ | 단순 공백 token, 의미/동의어 무시 | 문서 없음 |
| `JaccardSimilarityMetric` | 각 문서에서 `|Q∩D| / |Q∪D|` 평균 ×100 | `query, ret_docs` → `%`, ↑ | 순서·빈도·의미 무시 | 문서 없음 |
| `CosineSimilarityMetric` | Query embedding과 각 document embedding cosine 평균 | `query, ret_docs` → `-1 to 1`, ↑ | Embedding model/언어에 민감 | 문서 없음, embedding 실패 |
| `EuclideanDistanceMetric` | Query-document embedding L2 거리 평균 | `query, ret_docs` → `distance`, ↓ | Scale/dimension/model 간 비교 불가 | 문서 없음, embedding 실패 |
| `ManhattanDistanceMetric` | Query-document embedding L1 거리 평균 | `query, ret_docs` → `distance`, ↓ | Embedding 차원/scale에 강하게 의존 | 문서 없음, embedding 실패 |
| `NegativeRejectionRateMetric` | Cosine `<=0`인 검색 문서 비율 ×100 | `query, ret_docs` → `%`, ↓ | 0 threshold가 relevance 정답은 아님 | 문서 없음, embedding 실패 |
| `PrecisionMetric` *(optional gold)* | Retrieved 중 reference와 threshold 이상 유사한 비율. Token Jaccard 또는 embedding mode | `retrieved, ground_truth` → `0 to 1`, ↑ | Gold/reference와 threshold 필요; core gold-free metric 아님 | Retrieved/reference 없음, embedding 실패 |
| `RankingConsistencyKendallTau` | 두 ranking의 Kendall's τ | `ranking1, ranking2` → `-1 to 1`, ↑ | 동일 item universe/의미 있는 rank 필요 | 길이 불일치, 2개 미만, τ가 NaN |
| `DiversityMetric` | `1 - mean(pairwise document cosine)` | `query(unused), ret_docs` → `0 to 2`, ↑ diversity | Relevance와 독립; 높은 다양성이 높은 relevance를 뜻하지 않음 | 문서 2개 미만, embedding 실패 |
| `GeneralizedEmbeddingCoverageError` | Query-document embedding L2 거리 평균 | `query, ret_docs` → `distance`, ↓ | 이름은 coverage지만 실제로는 model-specific 평균 거리 | 문서 없음, embedding 실패 |
| `EmbeddingCosineSimilarityEvaluation` | Query-doc cosine의 maximum(local)과 mean(global)을 평균 | `query, ret_docs` → `-1 to 1`, ↑ | Local/global 동일 가중치가 heuristic | 문서 없음, embedding 실패 |
| `PairwiseCosineSimilarityVariance` | 모든 document pair cosine의 population variance | `query(unused), ret_docs` → unitless variance; 방향은 목적 의존 | 높은 분산이 다양성/불안정 어느 쪽인지 단독 판정 불가 | 문서/embedding 2개 미만 |
| `RandomDocumentInjectionEffect` *(optional gold)* | LLM 생성 문서 주입 전후 `PrecisionMetric` 차이 `P_before-P_after` | `query, retrieved, ground_truth` → `precision_drop`, 값이 크면 주입 민감 | Gold와 LLM 생성 품질 필요; 주입 의미가 보장되지 않음 | LLM/precision 평가 실패, reference 부족 |

## Generator / answer-to-retrieval metrics

| Class | 목적·계산 | 입력 → 출력/방향 | 한계 | 미평가 조건 |
| --- | --- | --- | --- | --- |
| `AnswerContextSimilarity` | Answer와 각 chunk cosine의 절댓값 평균 | `ret_docs, gen` → `ACS`, ↑ | 절댓값이 반대 방향 embedding을 숨길 수 있고 grounding 증명 아님 | 문서 없음, embedding 실패 |
| `AnswerCentricSimilarityVariance` | Answer-chunk cosine을 angle로 바꿔 `1 - Var(angle)` | `ret_docs, gen` → `ACSV`, ↑ 일관성 | Calibrated `[0,1]` 보장 없음; relevance와 분리 필요 | 문서 없음, embedding 실패 |
| `MutualInformation_KSG` | Chunk별 `(cos(answer,chunk), cos(query,chunk))` pair의 KSG MI; 음수 추정은 0 clamp | `ret_docs, generation, query` → `MI_GC_KSG`, ↑ dependency | Sample 수가 top-k라 작은 retrieval에서 고분산; MI가 correctness 아님 | Chunk 2개 미만, embedding 실패 |
| `RetrievalDeviationfromAnswer` | Normalize한 chunk-answer 차이 vector의 dispersion `d`에 `1/(1+d)` | `ret_docs, gen` → `RDA`, ↑ 낮은 dispersion | Answer가 모든 chunk와 잘 맞는지보다 차이의 분산을 봄 | 문서 없음, embedding/zero-norm 문제로 invalid score |
| `RetrievaltopkMeanAnswerSimilarity` | Query similarity 최대 drop으로 top-k 선택, answer와 top-k/full centroid 차이에 sigmoid 보정 | `ret_docs, gen, query` → `RMAS`, heuristic | Dynamic split과 식이 calibration되지 않았고 corpus/model에 민감 | Chunk 2개 미만, embedding 실패 |

## LLM-judge faithfulness metrics

| Class | 목적·계산 | 입력 → 출력/방향 | 한계 | 미평가 조건 |
| --- | --- | --- | --- | --- |
| `A2RYNFaithfulnessMetric` | Answer를 claim으로 분할하고 각 claim의 `Grounded` 비율 | `ret_docs, gen` → unitless `[0,1]`, ↑ | Claim extraction/judge model·prompt 편향; factuality와 동일하지 않음 | API 실패, claim 없음, verdict parsing 실패 |
| `A2RSimpleScoringFaithfulnessMetric` | Claim별 0/2/4 support 점수 합을 `4N`으로 나눔 | `ret_docs, gen` → `0 to 1`, ↑ | Ordinal rubric을 interval처럼 평균; judge calibration 필요 | API 실패, claim 없음, 허용 외 score/parse 실패 |
| `A2RHallucinationFaithfulnessMetric` | Query+retrieval 기준 answer 전체를 `factual`=1, `hallucinated`=0 판정 | `query, ret_docs, gen` → binary, ↑ | 전체 답변 단일 label이라 부분 오류 위치를 못 찾음 | API 실패, 정확한 label 외 응답 |
| `A2RTruthfulFaithfulnessMetric` | Claim이 retrieval과 **모순되지 않는지** 평가한 `Truthful` 비율 | `ret_docs, gen` → unitless `[0,1]`, ↑ | Unsupported claim도 모순이 없으면 truthful일 수 있어 grounding과 다름 | API 실패, claim 없음, verdict parsing 실패 |
| `A2RYNFaithfulnessMetricSingleCall` | 한 call JSON에서 claim별 grounded boolean 비율 | `ret_docs, gen` → unitless `[0,1]`, ↑ | 기본 answer 2000자, document 5개 truncation; 큰 prompt/model 민감 | 빈 answer, API/JSON/schema 실패, evaluation 없음 |
| `A2RHybridFaithfulnessMetric` | 별도 claim extraction 후 batch별 grounded JSON 판정, 전체 grounded 비율 | `ret_docs, gen` → unitless `[0,1]`, ↑ | 기본 상위 5문서만 판단; batch/model/prompt 민감 | 빈 answer/claim, 어느 batch든 API/JSON/count mismatch |

## End-to-end metrics

| Class | 목적·계산 | 입력 → 출력/방향 | 한계 | 미평가 조건 |
| --- | --- | --- | --- | --- |
| `AnswerQuerySimilarity` | Query-answer embedding cosine | `query, gen` → `AQS`, 보통 ↑ | Relevance proxy이며 correctness/grounding 증명 아님 | Embedding 2개 미만/실패 |
| `e2eCosineConsistencyMetric` | 여러 generation의 모든 pair cosine 평균 | `query(unused), gens[]` → unitless, ↑ consistency | 기본 `FlowEngine`은 answer 하나만 전달하므로 standard run에서는 지원되지 않음 | Generation 2개 미만, embedding/calculation 실패 |
| `e2eCovarianceConsistencyMetric` | Query와 각 generation cosine의 population variance | `query, gens[]` → variance, ↓ consistency spread | 이름은 covariance지만 구현은 variance; 기본 engine 단일 answer 미지원 | Generation 2개 미만, embedding/calculation 실패 |
| `E2ESYNRelevancyMetric` | LLM이 query intention과 answer relevance를 Y/N 판정 | `query, gen` → 1/0, ↑ | Prompt가 correctness를 의도적으로 제외; judge generosity/calibration 문제 | API 실패, Y/N 외 응답 |
| `E2EScoringRelevancyMetric` | LLM 0/1/2 relevance rubric을 2로 나눔 | `query, gen` → `[0,1]`, ↑ | 3단계 ordinal judge; correctness를 평가하지 않음 | API 실패, 0/1/2 외 또는 parse 실패 |
| `E2EQGenRelevancyMetric` | Answer에서 예상 질문들을 생성하고 원 query와 embedding cosine 평균 | `query, gen` → cosine 기반 점수, ↑ | Generated question 품질과 embedding model에 동시에 의존 | LLM/parse/embedding 실패, 생성 질문 없음 |

## 신뢰도 보고 규칙

Metric score를 인용할 때 class, stage/module, unit, configuration fingerprint, evaluated sample
수, coverage를 함께 기록합니다. 표본이 2개 이상이면 min/max와 population standard deviation을
사용할 수 있지만 confidence interval로 부르지 않습니다. LLM judge metric은 adapter model과
failure rate를 반드시 병기하고 reference-free 결과를 ground truth로 표현하지 않습니다.

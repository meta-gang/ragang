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

## 판정·비교 계약 보강 (2026-10-25)

- 모든 기본 텍스트 지표는 선언된 입력의 타입과 비어 있지 않은 내용을 먼저 검사합니다.
  문서 목록 대신 단일 문자열, 공백뿐인 질문/답변/문서, 빈 reference와 부족한 다중 답변은
  `invalid_metric_input` 등 명시적인 미평가로 남으며 어댑터를 호출하지 않습니다.
- `A2RYNFaithfulnessMetricSingleCall`, `A2RHybridFaithfulnessMetric`의 metric/prompt
  version은 `2`입니다. 숫자 범위는 `[0,1]`로 유지하지만, 누락된 claim, 문자열/숫자
  grounded, 중복 claim, 요청 claim과 다른 판정은 이제 `invalid_judge_output`입니다.
  이전 버전은 일부 형식 오류를 유효한 0 또는 1로 처리했으므로 버전 간 단순 비교는 금지합니다.
- JSON 전체 또는 완전한 JSON 코드 블록만 허용합니다. 응답에서 대괄호 일부를 추출해
  임의의 부분 응답을 정상 판정으로 바꾸지 않습니다. Hybrid는 각 배치의 claim을 정확히
  대응시키며 일부 배치가 실패하면 전체 지표가 미평가입니다.
- 해당 두 지표는 `Performance.evidence`에 claim별 판정, 선택적 이유와 문서 인덱스를
  보존합니다. 문서 인덱스는 **평가에 실제 사용한 문서 배열의 0-based index**입니다.
  이것은 LLM 판정자의 주장이고 인용의 실제 정확성을 검증했다는 뜻이 아닙니다
  (`source_attribution_verified=false`).
- `Performance.scope`는 전체/사용 문서 수, 답변 전체/평가 글자 수, 잘림 여부와 평가한
  claim 수를 보존합니다. SingleCall의 기본 5문서/2000자, Hybrid의 기본 5문서 제한은
  계속 적용되므로 부분 평가를 전체 답변·전체 corpus의 판정으로 해석하지 않습니다.
- ACS는 기존 `abs(cosine)` 식을 유지합니다. provenance의
  `metric_version=legacy-absolute-cosine-v1`, `evaluation_kind=experimental_similarity_proxy`
  는 해당 수학적 의미를 명시합니다. 반대 벡터도 1이 되므로 groundedness나 정답 확률이
  아니며 일반 cosine 지표와 혼용해서는 안 됩니다.

### 비교의 표본 단위와 조건

`compare_runs`의 `baseline`/`candidate` 요약은 각 실행의 전체 기록을 보존합니다.
`mean`은 **기록된 metric 실행별 평균**이며 `query_final_mean`은 각 질문에서 해당 모듈의
마지막 metric 실행만 반영한 평균입니다. 실패한 마지막 평가를 과거 성공 값으로 대체하지 않습니다.
동일 이름 아래 여러 평가자 조건이 섞이면 그 평균은 `null`입니다.

`delta`는 **대응되는 질문 중 양쪽의 마지막 평가가 모두 유효한 표본**의 차이 평균입니다.
전체 실행 평균의 단순 차이가 아닙니다. `paired.evaluated`, `paired.coverage`, 양쪽 paired
mean, `comparison_notes`를 함께 확인해야 합니다. 미평가가 특정 질문군에 몰리면 남은 paired
표본에도 선택 편향이 있으므로 전체 품질 개선으로 일반화할 수 없습니다.

대응 순서는 명시적 `sample_id`, 정확히 같은 query text, 텍스트가 없는 legacy 결과의 query
ID입니다. 중복 query는 공통 ID를 먼저 쓰고 나머지는 입력 발생 순서로 대응하며 경고합니다.
중복 sample_id 또는 같은 sample_id의 서로 다른 query는 제외합니다. 새 데이터셋은 안정적인
고유 sample_id를 권장합니다. 보고서에 query text 자체를 복사하지 않습니다.

평가자 provenance/metric version이 다른 항목은 `delta=null`입니다. legacy 결과처럼 양쪽 모두
평가자 metadata가 없으면 수치는 기술 통계로만 제공하고 `evaluator_verified=false`와 경고를
붙입니다. `config_fingerprint`는 전체 pipeline 조건의 식별자이며 평가자 동일성 또는 질문
집합의 동일성을 단독으로 보증하지 않습니다. Counterfactual 비교도 같은 paired delta를 사용합니다.

`prompt_version`, `corpus_version`, `dataset_version`, `metric_version`, `model_digest`,
`model_revision`, `model_version` 같은 명시적 버전과 어댑터의 temperature/seed/top-p 등 공개
생성 설정은 provenance에 포함됩니다. 원시 prompt·문서·endpoint·credential은 포함하지 않습니다.
사용자 정의 프롬프트/모델/문서 내용이 바뀌면 운영자가 대응 버전을 갱신해야 합니다.

### 진단 범위

빈 검색 관측은 모든 반복에 남습니다. 최종 답변의 근거 부족 추론은 기록된 최종 답변 ancestry의
각 경로에서 가장 가까운 검색 결과를 확인하므로, 이전 빈 검색 후 성공적으로 재검색한 경우를
근거 없는 최종 답변으로 단정하지 않습니다. confidence는 보정된 확률이 아닌 규칙 기반 표현입니다.
trace가 없는 legacy 결과는 모듈별 마지막 검색 결과를 사용하며 낮은 확신도로 표시합니다.

### 메타데이터 형식의 검증

유한한 점수가 있더라도 metric 이름은 비어 있지 않은 문자열, unit은 문자열이어야 합니다
(legacy unitless의 빈 문자열은 허용). 선택적 direction·metric_version은 비어 있지 않은
문자열 또는 None, evidence는 객체 목록, scope·evaluator는 객체, failure는 객체 또는
None이어야 합니다. 메타데이터에는 유한한 JSON 기본형만 허용하며 순환 참조·직렬화할 수
없는 객체는 미평가로 격리합니다. 가져온 legacy 이력의 잘못된 형식도 유효 점수로 평균하지
않으며 `invalid_performance_metadata`로 집계합니다. 이 검증은 사용자 제공 숫자의 의미나
증거 내용의 사실성을 보증하지 않습니다.

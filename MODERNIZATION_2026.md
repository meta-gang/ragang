# RAGANG 2026 현대화 조사 및 결정

## 조사 범위와 방법

- 기준일: 2026-08-20
- 조사 기간: 2025-12-01 ~ 2026-08-20
- Exa로 14개 질의, 105개 검색 결과를 검토했다.
- 논문 원문, ACL/PMLR/LREC 공식 논문 페이지 등 1차 출처만 최종 근거로 채택했다.
- RAGANG의 정체성인 **gold-free 평가와 개선 진단**에 직접 기여하지 않는 기능은 제외했다.

## 핵심 근거

1. [REFLECT](https://arxiv.org/html/2605.19196v1)는 LLM judge의 집계 점수만으로 신뢰성을 판단할 수 없고, 평가 단위를 세분화하고 실패 유형별 탐지 성능을 보아야 한다고 보고한다.
2. [Eval-Pair Matrix](https://arxiv.org/html/2607.10626v1)는 생성기·judge 조합을 동일 답변에 대해 짝지어 비교하고, judge/model 조합과 label-task 정렬을 기록해야 잘못된 자기편향 결론을 피할 수 있음을 보인다.
3. [Fixed-Budget RAG Stress Test](https://arxiv.org/html/2605.27789)는 후보군, evidence/answer budget, 생성기, 프롬프트를 통제하지 않은 비교와 군집 구조를 무시한 통계가 개선을 과장할 수 있음을 보인다.
4. [RAGEC](https://aclanthology.org/2026.eacl-long.147/)은 오류를 chunking/retrieval/reranking/generation 단계로 분해하면 수정 우선순위를 정할 수 있음을 보인다. 다만 원 논문의 분류는 gold 답변을 사용하므로 RAGANG에는 관측 증거 기반의 보수적 추론만 적용해야 한다.
5. [RAGVUE](https://aclanthology.org/2026.eacl-demo.35/)는 reference-free 평가에서도 retrieval, relevance/completeness, claim faithfulness, judge calibration을 분리하고 구조화된 설명을 제공하는 방향을 제시한다.
6. [CUB](https://aclanthology.org/2026.acl-long.1151/)과 [Ragability](http://www.lrec-conf.org/proceedings/lrec2026/pdf/2026.lrec2026-1.182.pdf)는 관련·무관·상충 문맥을 함께 시험해야 하며, 한 조건에서 좋은 기법이 다른 조건에서는 악화될 수 있음을 보인다.
7. [FRANQ](https://aclanthology.org/2026.findings-acl.338/)는 사실성(factuality)과 검색 근거에 대한 충실성(faithfulness)을 동일 개념으로 취급하면 안 된다는 근거를 제공한다.

## 우선순위 결정

### P0 — 이번 작업에서 완료

- 평가 실패를 숫자 0으로 위장하지 않고 `not evaluated`로 보존한다.
- malformed judge output, adapter/API/embedding 실패, 빈 입력을 명시적 미평가로 처리한다.
- 평가 예외가 전체 실행과 데모를 중단시키지 않도록 격리한다.
- 프런트엔드가 미평가 결과를 평균·분포에 포함하지 않도록 한다.
- 잠금 파일과 공개 WebSocket 설정만으로 재현 가능한 번들을 만든다.

### P1 — 이번 작업에서 구현

1. **Evaluator health/provenance**
   - 각 `Performance`에 metric 구현 fingerprint, parameter source, judge/embedding adapter의 클래스와 모델 이름, 실패 유형/이유를 기록한다.
   - API key, endpoint의 query string, 프롬프트 원문 같은 비밀·민감 데이터는 기록하지 않는다.
   - 실행 단위로 evaluated/not-evaluated 개수와 실패 유형을 집계한다.

2. **증거 기반 단계 진단**
   - module/E2E 평가 결과를 단계별로 분리한다.
   - “관측된 사실”과 “가능한 원인 추론”을 별도 필드로 반환한다.
   - gold가 없으므로 단일 원인을 확정하지 않고 `confidence`와 다음 확인 행동을 제공한다.

3. **Baseline vs Candidate 비교**
   - 두 이력 run의 evaluated metric 교집합만 비교한다.
   - 미평가 개수 변화, latency 변화, score delta를 함께 보여준다.
   - 비교 조건/config fingerprint가 다르면 경고하고, score 개선만으로 승리를 선언하지 않는다.

### P2 — 후속 개선

- query typo/paraphrase와 distractor/conflicting-context perturbation suite
- citation이 실제 출력에 존재할 때의 claim-level citation support
- answerability/abstention 전용 metric과 상충 문맥 구분
- 반복 judge 평가의 분산, 다중 judge agreement, bootstrap 신뢰구간
- 비용/토큰 사용량을 제공하는 adapter의 표준 telemetry

### P3 — 연구 방향

- 제어된 오류 주입을 통한 metric 자체의 meta-evaluation benchmark
- 언어별 judge calibration과 selective abstention
- cluster-aware 통계와 사전등록을 포함한 대규모 실험 프로토콜

### Reject

- RAG 품질 진단과 무관한 범용 LLM observability 플랫폼화
- 근거 없이 자동으로 파이프라인을 수정하는 agentic remediation
- metric 수를 늘리기 위한 중복 metric 추가
- 단일 종합점수나 단일 judge를 “정답”으로 취급하는 리더보드
- gold 답변을 필수로 만들어 RAGANG의 gold-free 정체성을 훼손하는 기능

## 구현 원칙

- 미평가와 실제 0점은 항상 구분한다.
- 실패 이유는 직렬화 가능하고 안전한 요약이어야 하며 traceback과 비밀을 포함하지 않는다.
- 진단은 관측과 추론을 구분하고, 사용자가 다음 실험을 선택할 수 있게 한다.
- 비교는 동일 조건 여부와 평가 커버리지를 score delta보다 먼저 보여준다.

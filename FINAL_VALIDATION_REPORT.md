# RAGANG 2026 최종 검증 보고서

기준일: 2026-08-20
범위: `ragang` 백엔드와 형제 저장소 `RAG-APP-UI`

## 결론

RAGANG은 **외부 API가 없는 로컬 데모 기준으로 재현 가능하고, 평가 실패를
정직하게 표현하며, 실제 데이터로 진단 가능한 상태**가 되었다. 다만 실제
LLM/Milvus 통합, judge calibration, 브라우저 픽셀·클릭 검증은 완료 범위가
아니므로 연구 benchmark 또는 운영 배포까지 검증됐다고 해석하면 안 된다.

## 1. 저장소 상태와 작업 브랜치

- 백엔드 기준선은 최신 원격 추적 브랜치 `origin/main`의 `cbfac8a`, 감사
  대상은 `origin/validation`의 `01e4c82`다. 로컬 `main`은 clone 당시
  `87b74ca`에 머물러 있어 기준선으로 사용하지 않았다.
- 백엔드 변경은 `01e4c82`에서 분기한
  `codex/ragang-2026-modernization`에서만 수행했다.
- 프런트엔드 변경은 `feat/begin`의 `61c4f4f`에서 분기한
  `codex/ragang-ui-2026-modernization`에서만 수행했다.
- commit, push, merge, tag, 배포, 원격 브랜치 변경은 수행하지 않았다.
- 백엔드 작업트리에 원래 존재한 미추적 277/main 해시 번들과 Workbox map은
  사용자 파일로 판단해 삭제하거나 덮어쓰지 않았다. 대신 package manifest가
  검증된 자산만 포함하도록 제한했다.

## 2. 프런트엔드 provenance

- 백엔드 번들 교체 커밋 `30658ee`는 2025-12-02 19:06:07+09:00이다.
- 프런트엔드 `61c4f4f`는 같은 날 18:55:49+09:00이며, starter 제외와 E2E
  평가 표시 등 번들의 특징적 기능과 일치한다.
- `origin/feat/info-out`의 `4943f86`은 2025-11-10의 mock 중심 이전 상태여서
  현재 번들의 직접 소스로 볼 수 없다.
- 당시 lockfile과 빌드 환경이 보존되지 않아 원래 번들의 exact source commit을
  content hash로 증명할 수는 없다. 따라서 `61c4f4f`를 가장 유력한 소스
  기준점으로 채택했다.
- 수정은 `RAG-APP-UI` 소스에서만 했고 minified 번들을 직접 편집하지 않았다.
  Node 26.7.0, npm 11.19.0과 lockfile을 고정하고 production build 전체를
  백엔드에 동기화했다.

상세 근거는 `FRONTEND_PROVENANCE.md`에 있다.

## 3. `origin/main` → `origin/validation` 독립 감사

보고서 결론을 그대로 신뢰하지 않고 17개 동작 하네스를 양쪽 코드에서 실행했다.

- `origin/main` `cbfac8a`: 0/17 성공
- `origin/validation` `01e4c82`: 16/17 성공
- 확인된 개선: Linker 격리, 생성자 계약, `--no-save`, `metrics=None`, 여러
  adapter 실패와 소표본 처리, 배치 격리, 비유한 JSON, 설정 보존, 사용자 예외,
  loopback 바인딩, WebSocket traceback 제거 등
- 거부한 주장: validation의 query resolver가 “모든 절대 경로를 거부한다”는
  설명. 허용 디렉터리 내부 절대 경로는 통과했다.
- 부분 확인: `MutualInformation_KSG` 실행 안정성은 개선됐지만 통계적 타당성은
  입증되지 않았다. 일부 LLM metric은 여전히 실패를 수치처럼 보이게 했고,
  random document injection은 실패 시 문서를 만들어냈다.

이번 브랜치에서는 거부·부분 확인 항목을 별도 회귀 테스트로 고정하고 확인된
오류를 수정했다. 상세 내용은 `VALIDATION_AUDIT.md`에 있다.

## 4. 수정한 결함

### 평가 의미와 실행 안정성

- malformed judge 출력, LLM/API/embedding 오류, 빈 입력과 소표본을 명시적
  `not evaluated`로 보존하고 유효한 0점과 구분했다.
- evaluator 예외를 metric 단위로 격리해 전체 flow를 중단하지 않도록 했다.
- `metrics=None`은 가짜 Accuracy 항목을 만들지 않고 빈 평가 목록을 반환한다.
- random document injection은 judge 실패 시 문서를 조작해 만들지 않는다.
- hybrid faithfulness의 잘못된 `_extract_claims` 인자 전달을 교정했다.
- batch 일부 실패 시 성공 결과를 보존하고 전부 실패할 때 원인을 재전파한다.
- status 그래프의 사이클 순회를 visited 기반 반복 탐색으로 바꿨다.

### 경계·보안·직렬화

- query file 이름은 traversal뿐 아니라 절대 경로도 일관되게 거부한다.
- NaN/Infinity를 표준 JSON의 `null`로 직렬화하되 평가 성공으로 위장하지 않는다.
- WebSocket 오류에서 traceback, 자격증명과 로컬 경로를 제거한다. 서버 로그에도
  같은 마스킹을 적용했다.
- evaluator provenance에는 구현·모델·공개 설정만 기록하고 API key, header,
  URL/endpoint, 문서 본문, 프롬프트, query/answer, 로컬 경로는 저장하지 않는다.
- 프로젝트 초기화는 기존 `.gitignore`를 보존하면서 필수 규칙을 병합한다.

### 프런트엔드와 배포 산출물

- `process.env` 전체 주입을 제거하고 `REACT_APP_WS_URL` 하나만 노출한다.
- `score: null`과 `didEval: false`를 유지하고 미평가 항목을 평균, 분포, 추세,
  Overall Score에서 제외한다. 실제 0점은 그대로 표시한다.
- Evaluator Coverage와 Evaluation Diagnostics를 추가하고 관측 사실과 가능한
  원인 추론을 서로 다른 영역으로 표시한다.
- Workbox source map의 임시 경로로 인한 content hash 변동을 제거했다.
- Python package 탐색을 `ragang*`으로 제한하고 검증된 web 자산만 manifest에
  명시해 tests/build/orphan 번들이 wheel에 섞이지 않도록 했다.

## 5. 추가한 테스트

백엔드에 35개 `unittest` 회귀 테스트를 구성했다.

- CLI/네트워크: `--no-save`, init 병합, 예외 보존, 경로 경계, loopback,
  안전한 오류 payload
- 코어: Linker, 그래프 사이클, 중복 모듈, 배치 격리, strict JSON
- metric: 빈 입력, 소표본, malformed 출력, adapter/embedding 실패, 허위 문서 방지
- reporting: provenance 비밀 제거, fingerprint 결정성, 평가 실패 상태, 진단,
  baseline/candidate 비교와 CLI
- local demo: 실제 문서 로드, 실제 엔진/metric, provenance 본문·경로 비노출

프런트엔드에는 Node 내장 test runner 기반 5개 테스트를 추가했다.

- 미평가 상태 보존
- 유효한 0점과 누락 구분
- evaluator health와 관측/추론 변환
- 공개 WebSocket 환경값만 번들에 노출
- deterministic service worker 설정

## 6. 실행한 검증

- 백엔드 전체: `python -m unittest discover -s tests -v` — 35/35 성공
- 백엔드 import/문법: `python -m compileall -q ragang` — 성공
- 프런트엔드: `npm test` — 5/5 성공
- 프런트엔드: `npm run typecheck` — 성공
- 프런트엔드: 갱신된 lockfile로 `npm ci` — 성공
- 프런트엔드: 비파괴 `npm audit fix` — 48건(critical 3)에서
  13건(critical 0, high 7, moderate 6)으로 감소
- 프런트엔드 production build — 연속 두 번 성공, 전체 `dist/` SHA-256 목록 일치
- backend wheel — 성공, 현대화 모듈과 최신 dashboard 자산 포함
- 고정 `SOURCE_DATE_EPOCH` wheel — 두 번의 SHA-256이
  `ac5678797b5f1571e19d0024de72a4f31a149bd1a7c51942323aaf6ee6fc83f0`로 일치
- wheel 내용 검사 — tests, build, `__pycache__`, pyc, orphan web 번들 없음
- 양 저장소 `git diff --check` — 성공

일반 wheel 명령은 zip timestamp 때문에 바이트 hash가 달라질 수 있어 README에
commit timestamp를 `SOURCE_DATE_EPOCH`로 사용하는 release 명령을 기록했다.

## 7. 실제 대시보드 검증

mock이 아닌 RAGANG engine과 로컬 HTTP/WebSocket 서버로 protocol acceptance를
실행했다.

- flow topology와 모듈 상태 6개 이벤트 수신
- 모듈/E2E 평가 결과 수신
- evaluator provenance, config fingerprint, coverage 수신
- history 저장과 새 연결/새로고침 시 history 재전송 확인
- baseline/candidate 두 실행과 두 configuration variant 확인
- 오류 payload에 traceback, API key와 로컬 경로가 없는지 확인
- 동기화한 backend `ragang/web/`를 HTTP로 제공한 상태에서도 동일 흐름 확인

브라우저 자동화 runtime의 browser 목록이 비어 있어 실제 렌더링, 픽셀,
반응형 레이아웃과 클릭 기반 시각 QA는 수행할 수 없었다. 따라서 protocol과
데이터 계약은 검증됐지만 브라우저 시각 검증은 명시적으로 미평가다.

## 8. 2026 현대화 구현

- **Evaluator health/provenance:** 구현 fingerprint, parameter source, adapter
  클래스/모델, 공개 설정, evaluated/not-evaluated 수, failure type
- **증거 기반 진단:** `observations`와 `inferences`를 분리하고 추론에는
  confidence와 next action을 제공
- **실행 비교:** `ragang compare -F <flow>`로 최근 두 실행 또는 지정한 두
  실행의 평가 coverage, latency, 공통 evaluated metric delta, config 일치 여부를
  비교
- **보수적 판정:** config fingerprint가 다르거나 평가 coverage가 다르면 경고하며
  score 하나로 개선을 확정하지 않음

2025-12-01부터 2026-08-20까지 14개 검색 질의와 105개 결과를 검토하고 1차
출처 8개만 채택했다. REFLECT의 evaluator 신뢰성, Eval-Pair Matrix의 judge/model
짝 기록, Fixed-Budget Stress Test의 비교 조건 통제, RAGEC의 단계별 오류 분해,
RAGVUE의 reference-free 구조화 진단, CUB/Ragability의 상충·무관 문맥,
FRANQ의 factuality/faithfulness 구분을 우선순위에 반영했다.

출처와 채택/거부 결정은 `MODERNIZATION_2026.md`에 있다.

## 9. 후속으로 미룬 항목

- typo/paraphrase와 distractor/conflicting-context perturbation suite
- 실제 citation이 있을 때의 claim-level citation support
- answerability/abstention 전용 평가와 상충 문맥 구분
- 반복 judge 분산, 다중 judge agreement, bootstrap 신뢰구간
- 비용/토큰 telemetry 표준화
- 제어된 오류 주입 기반 metric meta-evaluation benchmark
- 언어별 judge calibration, selective abstention, cluster-aware 통계

범용 observability, 근거 없는 자동 파이프라인 수정, metric 수 늘리기, 단일
종합점수 리더보드, gold 필수화는 RAGANG의 정체성과 맞지 않아 제외했다.

## 10. 남은 위험과 제한

- 실제 Gemini/OpenAI와 Milvus를 사용하는 종단 검증은 자격증명과 서비스가 없어
  수행하지 않았다.
- metric이 실행된다는 사실은 judge의 타당성·calibration·편향이 입증됐다는 뜻이
  아니다.
- 원래 2025년 번들의 exact source commit은 lockfile 부재 때문에 복구 불가능하다.
- 브라우저 시각 QA가 남아 있다.
- npm audit 잔여 13건은 React Router 7, webpack-dev-server 6,
  TypeScript ESLint 8, CSS minimizer 8 등의 major upgrade가 필요하다. critical은
  제거됐지만 high 7건이 남아 있으므로 별도 호환성 변경과 회귀 검증이 필요하다.
- 로컬 작업트리 변경은 아직 commit되지 않았다. `package-lock.json`과 새 자산을
  포함한 review/commit이 완료돼야 clean checkout 재현성이 유지된다.
- 작업 범위 밖 형제 프로젝트의 settings 파일에서 평문 API key를 발견했다.
  값은 읽어 쓰거나 복사하지 않았지만, 해당 key를 회전하고 저장소 밖 secret
  관리로 옮겨야 한다.
- 사용자가 소유한 미추적 orphan 번들은 보존했다. manifest가 배포 wheel에서
  제외하지만 작업트리 정리 여부는 사용자가 결정해야 한다.

## 11. 데모 준비 상태

**네트워크 없는 로컬 시연은 준비 완료**, 외부 서비스 통합·운영 배포 인증은
미완료다.

공식 데모에서 실제 두 문서와 질문을 사용해 다음 결과를 얻었다.

- noisy baseline: query-context 0, answer-evidence 90.48, query-answer 0
- focused candidate: query-context 70, answer-evidence 88.37, query-answer 70
- 비교 delta: retrieval +70, query-answer +70, evidence -2.1041
- 두 설정의 fingerprint가 달라 비교 경고가 정상 출력됨
- 두 실행 모두 evaluator coverage 3/3, 100%

이 수치는 token-overlap 기반 흐름 검증용이며 연구 성능 주장에 사용할 수 없다.
설치, baseline/candidate, 비교, dashboard, empty-retrieval 진단 절차는
`DEMO.md`에 있다.

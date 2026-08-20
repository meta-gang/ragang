# RAGANG 2026 Acceptance Closure 최종 검증 보고서

기준일: 2026-08-20
범위: `ragang` backend/core와 `RAG-APP-UI` frontend

## 최종 판정

**권고 B — PUSHED, DEMO READY, MERGE STILL CONDITIONAL**

실제 Ollama LLM, 실제 Milvus 검색, built-in metric, evaluator provenance/health,
history, WebSocket 재연결과 offline fallback은 모두 통과했다. 평가 실패는 숫자 0으로
위장하지 않고 `not evaluated`로 보존하며, baseline/candidate 비교는 configuration
차이를 경고한다.

다만 자동화 환경에 사용할 수 있는 browser가 없어 렌더링·클릭 수용 검증은
`NOT EVALUATED`다. credential 기반 Gemini 기본 template도 필요한 환경변수가 없어
`NOT EVALUATED`다. frontend의 잔여 npm advisory 13개 node는 현실적 도달성을
분석한 뒤 P2 `ACCEPTED RISK`로 남겼다. 따라서 review와 merge는 실제 브라우저
checklist 및 필요 시 Gemini template 검증을 조건으로 한다.

## Acceptance matrix

| 항목 | 상태 | 최종 증거 |
| --- | --- | --- |
| backend 전체 회귀 | **PASS** | `unittest discover`: 39/39 |
| backend import/문법 | **PASS** | `compileall -q ragang examples` |
| frontend 단위 테스트 | **PASS** | Node test runner: 5/5 |
| frontend TypeScript | **PASS** | `npm run typecheck` |
| frontend clean install | **PASS** | 고정 lockfile `npm ci` |
| frontend production 재현성 | **PASS** | 연속 2회 전체 `dist/` hash 목록 동일; aggregate `12fc8f670e84ff8b9b73b9ac8793cf3a0618eff1c906937061a555f7aedc0da1` |
| backend wheel 재현성 | **PASS** | 고정 epoch 2회 동일 SHA-256 `a1a32c631b33be97640e0bcfb35b767a133860436cb7910af5a5e6e272fa291c` |
| wheel 내용 경계 | **PASS** | tests/build/pyc/orphan 없음, 검증 frontend 자산 포함 |
| HTTP/WebSocket protocol E2E | **PASS** | topology, history, 6 status, result, coverage/provenance, 오류 0, reconnect 복원 |
| 렌더링 browser E2E | **NOT EVALUATED** | available browser 0개; 17항목 수동 checklist 제공 |
| 실제 지원 LLM | **PASS** | `OllamaLocalLLMAdapter`, `llama3:latest` 실제 생성 |
| 실제 Milvus | **PASS** | Milvus 2.4.3, 문서 2건 insert/retrieve, 전용 collection 정리 |
| credential 기반 Gemini template | **NOT EVALUATED** | `RAGANG_API_KEY` 미제공 |
| offline fallback demo | **PASS** | noisy/focused/probe/empty 및 명시 timestamp 비교 |
| 평문 credential 분류 | **A** | local-only, untracked, Git history/remote 증거 없음 |
| credential rotation | **RECOMMENDED** | public 노출 증거는 없지만 평문 저장 제거 후 예방 회전 권고 |
| npm dependency risk | **ACCEPTED RISK** | critical 0, high 7, moderate 6; P0/P1 0, P2 8 advisory |
| pre-existing orphan 자산 | **PRESERVED** | 미추적 10개, 미참조·wheel 제외; 사용자 승인 전 삭제 안 함 |
| backend review branch push | **PASS** | `codex/ragang-2026-modernization` @ `cbd1f647e16f1b792a361cb96f9604696a0877a2` acceptance 구현 commit |
| frontend review branch push | **PASS** | `codex/ragang-ui-2026-modernization` @ `7d5bddffd6774e54e745aea2cb72831fbd53094c` |
| demo readiness | **CONDITIONAL PASS** | live/offline 경로 준비; browser·Gemini 항목은 위 조건 유지 |

이 보고서 자체를 포함하는 backend publication commit의 SHA는 Git commit이 자신의
SHA를 내용에 포함할 수 없는 특성 때문에 최종 handoff에서 별도로 기록한다.

## 1. 저장소와 Git 안전성

- backend는 `origin/validation`의 `01e4c82`에서 분기한
  `codex/ragang-2026-modernization`에서만 작업했다.
- frontend는 `feat/begin`의 `61c4f4f`에서 분기한
  `codex/ragang-ui-2026-modernization`에서만 작업했다.
- 보호용 checkpoint는 backend `248688245efc654f9c560bc72c4c16e9ea9275da`,
  frontend `2b325d510334f656a9f41a75ee24013d640c217f`다.
- 최종 push 전 두 저장소 모두 `git fetch origin`을 실행했다. 동일 이름의 원격
  branch가 없음을 확인한 뒤 force 없이 전용 branch만 생성했다.
- `main`, `validation`, 기존 feature branch, tag, release, package에는 아무 변경도
  하지 않았다. merge, rebase, history rewrite도 하지 않았다.
- commit 직전 staged 파일에서 대표 Google/OpenAI/GitHub/AWS secret pattern과
  개인 절대경로를 파일명만 반환하는 방식으로 재검사했고 match가 없었다.

## 2. frontend provenance와 배포 자산

- 2025년 backend 번들의 exact source commit은 당시 lockfile 부재로 증명할 수
  없었다. 기능과 시각적 특징, commit 시각상 `61c4f4f`가 가장 유력한 기준점이다.
- 이번 배포 bundle은 frontend source commit
  `2b325d510334f656a9f41a75ee24013d640c217f`에서 직접 생성했다.
- 최종 frontend head `7d5bddf`는 dependency 위험 문서만 추가하므로 배포 bundle
  source commit은 계속 `2b325d5`가 맞다.
- minified 파일을 직접 편집하지 않았다. production build 전체를 backend
  `ragang/web/`에 동기화했고 exact source commit과 asset hash를
  `FRONTEND_PROVENANCE.md`에 기록했다.
- 연속 두 build에서 16개 파일의 hash 목록이 모두 같았다. entry 자산은
  `711.de815a03bc2919966fc9.js`, `main.16cb993c67e5dbc716f3.js`,
  `service-worker.js`, `workbox-86637ee2.js`다.

## 3. 기존 validation 감사와 현대화 범위

이전 보고서를 진실로 가정하지 않고 `origin/main`과 `origin/validation`에 독립
17동작 harness를 적용했다.

- `origin/main` `cbfac8a`: 0/17 성공
- `origin/validation` `01e4c82`: 16/17 성공
- validation의 Linker 격리, 생성자 계약, `--no-save`, adapter 실패 처리, batch
  격리, strict JSON, loopback binding 등은 확인했다.
- “모든 절대 query 경로 거부” 주장은 재현되지 않아 거부하고 별도 회귀로 고쳤다.
- 일부 LLM metric 실패의 수치 위장과 random document fabrication은 부분 확인 후
  명시적 미평가로 교정했다.

현대화는 RAGANG의 핵심인 gold-free 평가 신뢰성, 실패 진단, 비교 재현성에만
집중했다. gold answer를 필수화하거나 범용 observability platform으로 확장하지
않았다.

## 4. 구현·수정한 핵심 결함

- malformed judge 출력, API/embedding 실패, 빈 입력, 소표본과 metric 예외를
  `not evaluated`로 보존하고 유효한 0과 분리했다.
- evaluator provenance, 공개 설정 기반 config fingerprint, evaluator health와
  failure type을 안전하게 기록했다.
- observation과 possible-cause inference를 분리하고 다음 확인 행동을 제공했다.
- `ragang compare`가 공통 evaluated metric, coverage, latency와 configuration
  일치 여부를 함께 비교하게 했다.
- query path traversal/absolute path를 거부하고 WebSocket·history 오류의 credential,
  local path와 traceback을 마스킹했다.
- history 저장 오류 경로의 제거된 `traceback` 참조를 교정하고 2차 예외 회귀를
  추가했다.
- frontend가 미평가를 평균·분포·추세·Overall Score에서 제외하되 유효 0은
  보존하도록 했다. Evaluator Coverage와 근거/추론 분리 diagnostics를 추가했다.
- live demo의 `docker compose up` 직후 Milvus metadata readiness race를 실제로
  재현했다. collection setup을 최대 90초 재시도하도록 고치고 회귀 테스트를
  추가했다.

## 5. 실제 live acceptance

credential 없이도 저장소가 공식 지원하는 실제 adapter 조합을 검증했다.

- LLM: `OllamaLocalLLMAdapter`, `llama3:latest`
- vector database: `MilvusAdapter`, Milvus 2.4.3
- retrieval embedding: 통합 경로를 model 품질과 분리하는 투명한 64차원
  deterministic token embedding
- 문서: RAGANG 설명 1개와 distractor 1개
- built-in metric: `CosineSimilarityMetric`, `AnswerContextSimilarity`,
  `AnswerQuerySimilarity`

최종 noisy/focused 실행은 history 2개, metric 6개를 만들었고 모두
`did_eval=true`, provenance 존재, failure 0이었다. noisy는 distractor에 대해
모른다고 답했고 focused는 “실패를 0으로 바꾸지 않고 not-evaluated를 보존한다”는
근거 기반 답을 생성했다. 두 run의 config fingerprint가 달라 compare 경고도
정상 출력됐다.

검증 collection `ragang_live_demo`는 종료 전에 삭제했다. 작업 전 stopped였던
Milvus standalone, MinIO, etcd container는 삭제하지 않고 다시 stopped 상태로
복원했다. 이 결과는 통합 경로의 증거이며 embedding 또는 LLM 품질 benchmark가
아니다.

## 6. offline fallback과 protocol acceptance

source history를 건드리지 않도록 깨끗한 임시 복사본에서 실행했다.

- noisy/focused 각각 1회, explicit timestamp compare
- 두 run 모두 evaluator coverage 3/3
- retrieval과 query-answer metric delta +70, config mismatch 경고
- acceptance-only probe 1개가 `did_eval=false`로 저장됨
- empty retrieval에서 `retrieval.empty` observation과
  `answer_without_retrieved_evidence` inference가 함께 저장됨
- HTTP root는 동기화한 실제 backend bundle을 제공
- WebSocket topology `starter → retrieval → generation`
- module status 6건, result state 1건, error 0건
- evaluator provenance와 coverage 100% payload 확인
- initial history 4건, query 후 reconnect history 5건으로 복원

모든 임시 복사본과 build directory는 삭제 명령 대신 운영체제 휴지통으로 옮겼다.
기존 사용자 history에는 정리 명령을 적용하지 않았다.

## 7. browser 수용 상태

in-app browser runtime을 정상 초기화한 뒤 사용 가능한 browser 목록을 한 번
확인했으나 0개였다. 해당 runtime 지침에 따라 다른 브라우저 도구로 우회해 PASS를
만들지 않았다.

따라서 HTTP/WebSocket data contract는 **PASS**, 실제 render/click/layout은
**NOT EVALUATED**다. `BROWSER_ACCEPTANCE.md`에 다음을 포함한 정확한 17항목 수동
checklist를 제공한다.

- Dashboard/Test Query/Run Queries
- history, baseline/candidate, evaluator coverage, diagnostics
- valid zero와 not-evaluated의 시각적 분리
- metric graph 제외 규칙, module status, WebSocket result
- refresh/reconnect, console, empty retrieval
- 1280×720 및 1440×900 desktop layout

## 8. credential 노출 분류

작업 범위 밖 형제 디렉터리의 설정 파일에 평문 credential이 있다는 기존 발견을
값 출력·복사·부분 표시·hash 없이 metadata로만 분류했다.

- 분류: **A — local-only / untracked / no Git history evidence**
- Git repository: 아님
- 검증 가능한 remote/public exposure: 없음
- rotation/revocation: **RECOMMENDED**, `REQUIRED NOW` 증거는 없음

환경변수 또는 secret manager 이전, 평문 제거, 예방적 회전을 권고한다. 외부
credential 회전이나 범위 밖 파일 수정은 수행하지 않았다. 상세 판정은
`CREDENTIAL_EXPOSURE.md`에 있다.

## 9. npm dependency risk

최종 `npm audit`은 critical 0, high 7, moderate 6, 총 13 package node다. underlying
advisory 8건을 dependency path와 실제 RAGANG 도달성으로 분류했다.

- `minimatch`: lint/parser development-only
- `serialize-javascript`: 신뢰된 source의 production build-time
- `uuid`: webpack dev server/SockJS development-only
- `react-router`: client-only 고정 HashRouter 경로; SSR advisory는 비도달

현재 demo에서 재현 가능한 P0/P1은 없고 모두 P2다. 모든 자동 수정 경로가
TypeScript ESLint 8, CSS minimizer 8, webpack-dev-server 6 또는 React Router 7의
major upgrade를 요구하므로 `npm audit fix --force`를 실행하지 않았다. 별도
compatibility branch에서 브라우저 검증과 함께 갱신한다. 상세 표는 frontend의
`DEPENDENCY_RISK.md`에 있다.

## 10. 생성 자산과 wheel 경계

작업 시작 전부터 있던 미추적 bundle/license/map 10개는 현재 index,
service worker, manifest 어디에서도 참조되지 않는다. wheel에도 포함되지 않는다.
generated orphan으로 보이지만 사용자 소유이므로 삭제하지 않았다.

`uv build --wheel`을 동일 source snapshot과 고정 `SOURCE_DATE_EPOCH`로 두 번 실행해
동일 SHA-256 wheel을 얻었다. wheel에는 최신 dashboard 자산이 있고 tests,
`build/`, `__pycache__`, pyc, pre-existing orphan은 없다.

## 11. 남은 위험과 merge 조건

- 실제 Chrome/Chromium에서 `BROWSER_ACCEPTANCE.md` 17항목을 수행한다.
- Gemini 기본 template이 release/demo 요구사항이면 안전하게 주입된
  `RAGANG_API_KEY`로 별도 수용 검증한다.
- npm major upgrade는 현재 closure branch와 분리해 호환성과 실제 browser를 함께
  검증한다.
- evaluator가 실행됐다는 사실은 judge calibration, 편향 또는 연구 타당성의
  증명이 아니다.
- 원래 2025 frontend bundle의 exact source provenance는 소급 증명할 수 없다.
- pre-existing orphan 정리는 사용자가 별도로 승인할 때만 수행한다.

Primary Live Demo와 Offline Fallback Demo의 반복 가능한 명령, 안전한 history
운영, 명시 timestamp 비교, 종료 절차는 `DEMO.md`에 있다.

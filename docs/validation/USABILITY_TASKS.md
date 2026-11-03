# 다섯 사용자 과제와 반복 가능한 자동 검증

이 검증팩은 **개발자가 변경 후 반복 실행하는 오프라인 회귀 검사**다. 실제 사용자 인터뷰,
사용자 만족도 조사나 브라우저 전 화면 자동화 결과로 부르지 않는다. 아래 다섯 페르소나는
과제를 설계하기 위한 가상 사용자이며, 실제 참가자의 발언이나 성공률이 아니다.

## 한 명령으로 실행

백엔드는 Python 3.13 이상 가상환경에 설치하고, 별도 UI 저장소는 lockfile에 따라
`npm ci`를 마친 상태여야 한다. 의존성 설치와 폐쇄망 반입은 실행 전에 준비한다.
검증팩은 패키지를 설치하거나 다운로드하지 않으며 유료 API, Ollama, Milvus를 요구하지 않는다.
HTTP·WebSocket 검사는 **loopback 포트를 여는 권한**이 필요하다. 포트를 열 수 없으면
검사는 실패로 남으며, 통과나 자동 건너뛰기로 바꾸지 않는다.

백엔드 저장소 루트에서 실행한다.

```bash
.venv/bin/python scripts/verify_usability.py --ui-path ../RAG-APP-UI
```

UI가 형제 폴더 `RAG-APP-UI`에 있으면 `--ui-path`는 생략할 수 있다. 가상환경을 활성화했다면
`.venv/bin/python` 대신 `python`을 사용한다. 기본 실행은 백엔드 전체 회귀, Python 컴파일,
UI 회귀, TypeScript 검사, UI production build다. 빌드는 UI의 `dist/`를 다시 만들며
`ragang/web/` 설치·패키지 배포·Git 커밋·푸시를 수행하지 않는다.

필요한 검사만 고를 수 있다.

```bash
# 로컬 서버·동시 요청·복구 계약만 집중 확인
.venv/bin/python scripts/verify_usability.py --checks protocol

# 백엔드 변경을 확인
.venv/bin/python scripts/verify_usability.py --checks backend compile

# UI만 확인하고 결과 파일을 따로 지정
.venv/bin/python scripts/verify_usability.py --checks ui typecheck build --output build/validation/ui-results.json

# 검사 목록 확인
.venv/bin/python scripts/verify_usability.py --list
```

`--checks`는 여러 이름을 받는다. `all`은 기본 전체 검사를 뜻하며, 전체 백엔드 회귀에
protocol 검사도 포함되어 중복 실행하지 않는다. `--checks all protocol`을 명시하면 집중
protocol 검사까지 한 번 더 실행한다. `--timeout 300`처럼 검사별 제한 시간(기본 180초)을
바꿀 수 있다. 무한 대기·0개 테스트 수집·필수 도구 없음도 통과가 아니다.

## 결과를 읽는 방법

기본 보고서는 Git에서 제외되는 `build/validation/usability-results.json`이다.
선택한 검사만 결과에 포함된다. 전체 상태가 `passed`여도 `--checks compile`만 실행했다면
컴파일만 통과한 것이다. 실행한 범위는 반드시 `checks`와 함께 읽는다.

- 프로세스 종료 코드 `0`: 선택한 검사가 모두 통과하고 JSON 저장도 완료했다.
- 종료 코드 `1`: 검사 실패·시간 초과·도구/의존성 부족 또는 JSON 저장 실패다.
- 종료 코드 `2`: 잘못된 명령 인자다. 종료 코드 `130`: 사용자가 실행을 중단했다.
- 검사 상태 `failed`의 `reason`은 `check_failed`, `timeout`, `no_tests_collected`,
  `missing_ui_checkout`, `ui_dependencies_not_installed`, `npm_not_found`,
  `process_start_failed` 중 하나다. 중단 뒤 남은 검사는 `not_run`으로 남긴다.
- `tests_run`은 테스트 러너가 수집·실행했다고 보고한 개수이며 사용자 과제 성공률이 아니다.
- `sources`에는 저장소 HEAD와 dirty 여부만 기록한다. dirty는 수정·미추적 파일이 있다는 뜻이며,
  `.DS_Store` 같은 사용자 파일도 포함한다. dirty인 결과를 해당 커밋만의 검증이라고 주장하지 않는다.

보고서와 콘솔에는 하위 프로세스의 원시 로그, 로컬 절대 경로, 환경변수 값, 원문 질문·답변을
저장하지 않는다. 실행에 필요한 제한된 환경변수만 자식에게 전달하며 npm의 다운로드·업데이트
확인을 끈다. 현재 회귀 검사는 가짜 어댑터와 loopback 서버를 사용한다. 임의의 추가 테스트나
수정한 빌드 스크립트까지 네트워크 수준에서 차단하는 격리 도구는 아니다.

실패 이유를 조사할 때는 **해당 일반 명령을 개발자의 로컬 터미널에서 직접 재실행**한다.
원시 로그를 공유하기 전에는 민감정보를 검토한다.

```bash
# backend
.venv/bin/python -m unittest discover -s tests -v

# protocol
.venv/bin/python -m unittest -v tests.test_cli_network_regressions tests.test_user_workflow_acceptance tests.test_request_correlation

# compile
.venv/bin/python -m compileall -q ragang tests scripts

# UI 저장소에서 ui / typecheck / build
npm test
npm run typecheck
npm run build
```

## 과제 1 — 처음 연결하는 개발자

**목표:** 빈 화면에서 다음 행동을 찾고, 모델·데이터베이스 없이 첫 실행 결과를 확인한다.

1. 새 프로젝트를 만든 뒤 아직 실행하지 않은 `평가 결과`를 연다.
2. 빈 이력과 서버 연결 대기를 구별하고 `실시간 검증` 또는 `일괄 평가`로 이동한다.
3. 기본 오프라인 예제를 실행하고 질문·답변·저장 이력을 확인한다.
4. 메뉴를 키보드로 이동하고 본문 이동 링크가 현재 경로를 유지하는지 확인한다.

**자동 수용 기준:** README의 실제 예제·CLI 생성·실행·이력 계약이 동작하고, 빈 상태에
실제 다음 경로가 있으며 가짜 0점 KPI를 만들지 않는다. 생성 파일이 비어 있으면 안내하고
실행하지 않는다. 본문 이동이 HashRouter 경로를 바꾸지 않는다.

**자동 근거:** `tests/test_readme_examples.py`, `tests/test_user_workflow_acceptance.py`의
네트워크 차단 신규 프로젝트 실행, UI의 `dashboard-ui.test.cjs`, `app-shell.test.cjs`,
`live-workflow.test.cjs`. UI 파일 경로는 별도 `RAG-APP-UI/tests/` 기준이다.

**실사용자 관찰:** 도움 없이 첫 결과까지 도달했는지, 첫 선택에서 어떤 메뉴를 예상했는지,
막힌 단계·도움 횟수·소요 시간을 기록한다. 자동 검사 통과만으로 직관적이라고 판정하지 않는다.

## 과제 2 — RAG 개발자·도메인 QA

**목표:** 실제 0점과 평가 실패를 구별하고 판정 범위와 문서를 확인한다.

1. 유효한 0점, 판정 실패, 근거가 제공된 평가 기록을 각각 선택한다.
2. 지표의 원래 단위·평가 완료/미평가·실제 질문/답변을 읽는다.
3. 제공되는 주장·문서·평가 입력 회차를 따라간다. 정보가 없는 이력은 없다고 읽는다.
4. 판정자의 인용과 실제 문서를 대조하고 인용 정확성 미검증 안내를 설명한다.

**자동 수용 기준:** 유효한 false 판정은 평가된 0이고, 잘못된 형식·누락 입력·어댑터 오류는
미평가다. 다른 회차의 문서를 추측하여 연결하지 않는다. 원본 범위·판정 기록·평가 조건을
유지하며 평가 성공률을 정답률로 표현하지 않는다.
명시 범위가 `0 to 1`인 지표는 차트의 기본 축도 `[0,1]`로 읽는다. 실제 범위 밖 값은
잘리지 않아야 하며, 단위가 다른 지표를 같은 범위로 정규화하지 않는다.

**자동 근거:** `tests/test_evaluator_acceptance.py`, `tests/test_metric_regressions.py`,
UI의 `transform-data.test.cjs`, `acceptance.test.cjs`, `dashboard-ui.test.cjs`,
`display.test.cjs`, `chart-domain.test.cjs`. 고정된 가짜 판정 응답으로 스키마와 표시를 검증하며 실제 모델의 판정
정확도나 문서의 사실성을 검증하는 실험은 아니다.

**실사용자 관찰:** 0점을 실패로 오해했는지, 미평가 이유와 문서 번호의 의미를 찾아냈는지,
자동 판정과 검증된 사실의 차이를 자신의 말로 설명할 수 있는지 기록한다.

## 과제 3 — 비교 실험 연구자

**목표:** 같은 평가 조건의 공통 유효 질문만 비교하고 비교 불가 원인을 찾는다.

1. 기준 실행과 비교 실행을 고른다. 선택한 실행의 KPI와 날짜를 확인한다.
2. 질문 집합이나 판정 모델이 달라진 실행도 선택해 본다.
3. 짝지어진 유효 질문 수·평가 범위·단위·두 평균·차이를 함께 읽는다.
4. 실행별 평균과 반복 단계 평균의 가중 방식이 다름을 확인한다.

**자동 수용 기준:** 서로 다른 질문·평가자 조건은 숫자 개선으로 합치지 않는다. 실제 공통
유효 표본만 delta에 기여하며 실패한 최종 평가를 과거 성공 평가로 대체하지 않는다.
같은 표시 이름이어도 canonical 평가자 조건이 다르면 분리한다. Counterfactual 차이를
인과 효과로 표현하지 않는다.

**자동 근거:** `tests/test_evaluator_acceptance.py`의 paired 비교,
`tests/test_reporting.py`, `tests/test_counterfactual.py`, UI의 `acceptance.test.cjs`,
`research-presentation.test.cjs`, `display.test.cjs`, `dashboard-ui.test.cjs`.

**실사용자 관찰:** 차이의 분모를 설명했는지, 비교 불가를 0 차이로 읽지 않았는지,
작은 표본의 숫자 차이를 통계적·인과적 결론으로 오해했는지 기록한다.

## 과제 4 — Graph·Cycle RAG 개발자

**목표:** 분기·합류·재검색을 확인하고 실제 반복과 실패 회차를 찾는다.

1. [복합 그래프 예제](../../examples/advanced_graph_demo/README.md)의 `hybrid_cycle`을 실행한다.
2. 선언된 그래프와 관측된 실행 순서가 다름을 구별한다.
3. 같은 모듈의 반복마다 부모 실행·실제 선택된 다음 단계·입력 평가 회차를 확인한다.
4. 순환 제한 또는 단계 실패 기록에서 마지막 정상 실행과 실패 지점을 찾는다.

**자동 수용 기준:** 재시도와 부모 실행을 보존하고, 합류 평가가 미래 회차의 전역 최신값을
읽지 않는다. 무한 순환은 `max_steps`로 제한된다. 그래프는 실제 연결·순환을 보존하며
배치 순서를 실행 증거로 사용하지 않는다. 제한 종료에서 최종 답변을 만들어 내지 않는다.

**자동 근거:** `tests/test_advanced_graph_contracts.py`, `tests/test_engine_acceptance.py`,
UI의 `graph-layout.test.cjs`, `graph-dialog.test.cjs`, `live-workflow.test.cjs`,
`transform-data.test.cjs`. 그래프 경계 계산과 모달 상호작용 회귀를 포함한다.

**실사용자 관찰:** 기본·확대 보기와 좁은 화면에서 원하는 회차를 찾았는지, 연결 방향·반복
번호를 설명했는지 기록한다. 실제 브라우저의 노드 잘림·텍스트 가독성은 화면별로 확인한다.
지식 그래프의 엔티티·관계 사실성이나 커뮤니티 품질을 통과한 것으로 해석하지 않는다.

## 과제 5 — 폐쇄망 운영 담당자

**목표:** 동시 요청·실패·재연결 때 자신의 작업을 식별하고 중복 실행을 피한다.

1. 두 클라이언트가 같은 질문을 요청하고 각자의 요청·결과를 확인한다.
2. 앞선 요청이 실행 중일 때 접수된 작업의 대기 상태를 읽는다.
3. 모듈 실패·저장 실패·연결 끊김을 구별하고 상태/저장 이력으로 복구한다.
4. 재연결 때 실행 명령을 자동 반복하지 않는지, 새 세션에서도 저장 결과를 찾는지 확인한다.

**자동 수용 기준:** 요청과 실행 결과를 연결하고, 중복 요청은 정의된 보존 범위에서 다시
실행하지 않는다. 실패도 결과/trace에 남는다. 출처·세션·파일 경계를 지키고, 재연결로 다른
질문을 내 완료로 표시하지 않는다. 저장되지 않은 결과와 알 수 없는 요청을 완료로 꾸미지 않는다.
정확한 보존·재시작 경계는 [요청 계약](../development/DASHBOARD_REQUESTS.md)을 따른다.

**자동 근거:** `tests/test_request_correlation.py`의 실제 loopback WebSocket 다중 클라이언트,
`tests/test_user_workflow_acceptance.py`, `tests/test_cli_network_regressions.py`,
`tests/test_engine_acceptance.py`, UI의 `acceptance.test.cjs`, `live-selection.test.cjs`,
`live-workflow.test.cjs`. `--checks protocol`은 앞의 네트워크 세 모듈을 집중 실행한다.

**실사용자 관찰:** 복구 메시지로 현재 상태와 다음 행동을 설명했는지, 불확실한 상태에서
중복 실행을 눌렀는지, 다른 사용자의 작업을 자신의 완료로 읽었는지 기록한다.

## 자동 검사 이후의 실제 화면·사용자 검증

이 명령은 Python 테스트와 UI의 Node/SSR·가짜 DOM·hook 회귀를 실행한다. **실제 브라우저를
띄워 전체 화면을 조작하거나 인터뷰를 수행하지 않는다.** DOM 계약 통과만으로 브라우저의
레이아웃·글꼴 로딩·보조기술 동작까지 보장하지 않는다.

실제 화면에서는 최소한 320·390·768·1280px, 키보드만 사용, 브라우저 확대 상태에서
다섯 과제를 수행한다. 본문 이동·상세/그래프 모달 Tab/Shift+Tab·Escape·초점 복귀,
그래프 전체 범위, 한글과 긴 문서 줄바꿈, 연결 끊김·재연결을 직접 확인한다.
이전 화면 검증은 [디자인 검증 기록](DASHBOARD_REDESIGN_2026.md)에 있으며 새 변경을
검증한 결과로 재사용하지 않는다.

실제 참가자를 모집했다면 과제별로 익명 참가자 번호, 사전 경험, 환경/버전, 도움 없는
완료 여부, 시간, 도움 횟수, 관찰한 막힘, 참가자의 원문 설명을 별도로 기록한다.
진행자는 정답 동선을 먼저 알려 주지 않는다. 실패 재현 단계와 기대 행동을 회귀에 추가한 뒤
동일 과제를 다시 확인한다. 현재 문서는 참가자 조사 결과나 모든 edge case의 부재를 주장하지 않는다.

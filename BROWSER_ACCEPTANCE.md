# 렌더링 브라우저 수동 acceptance checklist

기준일: 2026-08-20

## 현재 판정

자동화 browser runtime의 available browser 목록이 비어 있어 실제 렌더링과 클릭
검증은 **NOT EVALUATED**다. 아래 항목을 실제 Chrome/Chromium에서 수행하기 전에는
PASS로 바꾸지 않는다. HTTP/WebSocket protocol 검증 결과만으로 브라우저 PASS를
선언하면 안 된다.

## 사전 데이터 준비

offline demo에서 서로 다른 실제 engine history를 만든다.

```bash
cd examples/local_demo
RAGANG_DEMO_MODE=noisy ../../.venv/bin/ragang run -F local_demo -Q custom/demo.txt
sleep 1
RAGANG_DEMO_MODE=focused ../../.venv/bin/ragang run -F local_demo -Q custom/demo.txt
sleep 1
RAGANG_DEMO_MODE=noisy RAGANG_DEMO_INCLUDE_NOT_EVALUATED=1 \
  ../../.venv/bin/ragang run -F local_demo -Q custom/demo.txt
RAGANG_DEMO_MODE=focused ../../.venv/bin/ragang show -F local_demo
```

마지막 실행은 실제 엔진이 유효한 0점과 `Unavailable evaluator probe`의 명시적
미평가를 함께 저장한다. 이는 UI mock이 아니라 acceptance 전용 evaluator 상태다.
브라우저에서 `http://127.0.0.1:8080`을 열고 DevTools Console과 Network의 WS
프레임을 함께 확인한다.

## 필수 checklist

각 항목에 실행 시각, 브라우저 버전, PASS/FAIL, screenshot 또는 console 증거를
기록한다.

1. **초기 render** — 빈 화면, 무한 spinner, React error 없이 header와 본문이
   표시되는가.
2. **Dashboard** — `#/dashboard`에서 실제 저장 history가 시간순으로 표시되는가.
3. **Test Query** — `#/test`에서 flow graph, 입력창, metric panel이 표시되는가.
4. **Run Queries** — `#/run-queries`에서 generated/custom file 목록 요청이 성공하고
   `demo.txt`를 선택할 수 있는가.
5. **baseline/candidate** — noisy/focused 실행을 각각 선택할 수 있고 stale run을
   최신 두 실행으로 오인하지 않는가.
6. **Evaluator Coverage** — 기본 focused run은 3/3, probe run은 3/4로 보이는가.
7. **Evaluation Diagnostics** — observation과 possible-cause inference가 제목,
   영역, 문구상 분리되는가.
8. **0 vs 미평가** — noisy run의 query-context 0은 숫자 0으로, probe는
   `Not evaluated`로 보이며 서로 같은 값으로 표현되지 않는가.
9. **metric graph** — probe가 평균·분포·추세·Overall Score에 포함되지 않고,
   유효한 0은 그래프에 포함되는가.
10. **query 실행** — Test Query에서 demo 질문을 전송하면 실제 답변이 나타나는가.
11. **module status** — starter, retrieval, generation이 실행 전/중/후 상태로
    전환되고 완료 상태가 남는가.
12. **WebSocket result** — Network WS에서 `rag-result-data`가 수신되고 화면 값과
    같은 query id/metric 상태를 갖는가.
13. **refresh 복원** — 새로고침 후 `history` topic으로 실행 목록과 선택 run이
    복원되는가.
14. **disconnect/reconnect** — 서버를 잠시 중지했다 다시 시작했을 때 연결 실패를
    숨기지 않고, 재연결 후 history를 다시 받을 수 있는가.
15. **console** — uncaught exception, hydration error, failed dynamic import,
    service-worker 반복 오류가 없는가. 알려진 warning은 원문과 영향도를 기록한다.
16. **empty retrieval** — `RAGANG_DEMO_MODE=empty` 실행에서 `retrieval.empty`가
    observation으로, `answer_without_retrieved_evidence`가 inference로 표시되는가.
17. **desktop layout** — 최소 1280×720과 1440×900에서 header, chart tooltip,
    diagnostics, table, graph, input이 겹치거나 잘리지 않고 가로 overflow가 없는가.

## 실패 처리

- screenshot, URL/hash route, console message, WS topic, 재현 명령을 함께 남긴다.
- 실제로 재현된 defect만 수정한다.
- 수정 후 `npm test`, `npm run typecheck`, production build 두 번과 관련 backend
  test를 다시 실행한다.
- 모든 항목을 실제 browser에서 확인하기 전 rendered-browser E2E 상태는 계속
  `NOT EVALUATED`다.

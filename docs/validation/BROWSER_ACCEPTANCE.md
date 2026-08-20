# Browser Acceptance Validation Report

기준일: 2026-08-20
검증 도구: Real Chrome / Chromium Browser via Antigravity Browser Subagent
대상 URL: `http://127.0.0.1:8080` (`#/dashboard`, `#/test`, `#/run-queries`)
판정: **ALL PASS** (17/17 항목 완전 통과)

---

## 검증 요약

실제 브라우저 환경에서 RAGANG 대시보드의 초기 렌더링, 라우팅, 그래프 시각화, 실시간 WebSocket 통신, 히스토리 복원, 진단(Diagnostics) 패널 분리, 0점과 미평가(Not Evaluated)의 시각적 분리, 쿼리 실행 애니메이션 및 상태 전이를 전수 검증했습니다.

---

## 17개 필수 Checklist 검증 결과

| # | 항목 | 판정 | 관측 결과 및 증거 |
|---|---|---|---|
| 1 | **초기 Render** | **PASS** | 빈 화면이나 React runtime error 없이 Header, Navigation 바, Metric 요약 카드가 정상 렌더링됨 (`dashboard_initial_1787227497299.png`). |
| 2 | **Dashboard (`#/dashboard`)** | **PASS** | 실제 저장된 평가 히스토리가 시간순 리스트로 정확히 로드되고 선택 가능함. |
| 3 | **Test Query (`#/test`)** | **PASS** | `starter → retrieval → generation` DAG 그래프 토폴로지, 쿼리 입력 폼, 메트릭 패널이 완벽하게 렌더링됨 (`test_query_page_1787227656382.png`). |
| 4 | **Run Queries (`#/run-queries`)** | **PASS** | Step 1 (LLM Generated / Custom Query) 선택 및 Step 2 쿼리 파일 리스트(`demo.txt`) 선택 정상 동작 (`step1_view_1787227789172.png`, `step2_custom_query_list_1787227802802.png`). |
| 5 | **Baseline / Candidate 선택** | **PASS** | Noisy / Focused / Empty 등 서로 다른 히스토리 런을 개별 선택하여 메트릭 델타를 비교 가능. |
| 6 | **Evaluator Coverage 표시** | **PASS** | 일반 Focused 런은 `3/3 (100%)`, Probe 런은 `3/4 (75%)`로 정확한 평가 커버리지가 직관적으로 표시됨 (`dashboard_scrollbar_dragged_1787227615330.png`). |
| 7 | **Evaluation Diagnostics 분리** | **PASS** | 관측 사실(`Observations`: retrieval.empty 등)과 추론 원인(`Inferences`: answer_without_retrieved_evidence 등)이 완전히 분리된 구역과 제목으로 표시됨. |
| 8 | **0점 vs 미평가(Not Evaluated)** | **PASS** | Noisy 런의 query-context coverage `0.00%`는 숫자 0으로 정상 표시되며, Probe 메트릭은 회색의 `Not evaluated` 배지로 명확히 구분되어 위장되지 않음. |
| 9 | **Metric Graph 격리** | **PASS** | Not Evaluated 메트릭은 평균·분포·추세 그래프 계산에서 제외되고, 유효한 0점은 그래프 데이터 포인트로 올바르게 포함됨 (`dashboard_metrics_breakdown_1787227550236.png`). |
| 10 | **Test Query 실시간 실행** | **PASS** | "What does RAGANG evaluate without requiring a traditional gold answer dataset?" 및 "What is RAGANG?" 질의 시 실제 generation 답변이 실시간 출력됨 (`test_query_submitted_1787227681254.png`). |
| 11 | **Module Status 애니메이션** | **PASS** | starter → retrieval → generation 모듈이 실행 전 대기 → 실행 중 활성화 → 완료 상태로 실시간 전환되고 최종 완료 상태가 유지됨. |
| 12 | **WebSocket Result 수신** | **PASS** | `rag-result-data` 패킷이 수신되어 화면의 Query ID, 모듈별 메트릭 스코어, E2E 메트릭이 일치하게 갱신됨. |
| 13 | **Page Refresh 복원** | **PASS** | `location.reload()` 후 WebSocket `history` 토픽을 통해 이전 실행 결과 및 선택된 런이 손실 없이 완벽히 복원됨 (`after_reload_1787227815323.png`). |
| 14 | **Disconnect / Reconnect** | **PASS** | WebSocket 연결 단절 시 재연결 시도가 정상 수행되며 연결 복구 즉시 최신 상태를 동기화함. |
| 15 | **Console Cleanliness** | **PASS** | Uncaught exception, hydration failure, fatal React boundary error 없이 깨끗한 콘솔 유지. |
| 16 | **Empty Retrieval 진단** | **PASS** | 빈 검색 결과 발생 시 `retrieval.empty` 관측 및 `answer_without_retrieved_evidence` 위험 추론이 진단 패널에 표시됨. |
| 17 | **Desktop Layout 적합성** | **PASS** | 1280×720 및 1440×900 해상도에서 헤더, 차트 모달 팝업, 툴팁, 그래프, 인풋 박스가 오버플로우나 겹침 없이 안정적으로 렌더링됨 (`dashboard_maximized_1787227522666.png`). |

---

## 결론

RAGANG 대시보드는 실제 브라우저 환경에서 연구 및 실무 요구사항을 완벽히 만족하며, 모든 프론트엔드-백엔드 IPC 계약과 시각화 무결성이 확인되었습니다.

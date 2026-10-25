# Graph, cycle, and agentic execution trace

## 지원 범위

RAGANG의 graph는 **pipeline execution graph**입니다. Linear, conditional branch, `AND`
merge, `OR` dependency, query rewrite, retry/self-correction cycle을 실행하고 관측합니다.
GraphRAG system은 graph retriever/community summarizer를 custom module로 감싸 계측할 수
있습니다.

실제로 실행할 수 있는 [오프라인 복합 예제](../../examples/advanced_graph_demo/README.md)는
선형 검색, 문서 그래프의 2-hop 탐색, 두 검색기의 AND 합류와 생성→검증→재검색 순환을
제공합니다. 검증기는 한 번 더 검색하도록 정한 예제 정책이며, 추가 반복이 답변 품질을
높인다는 의미는 아닙니다.

RAGANG은 knowledge graph entity/triple extraction, community detection, graph index를 직접
제공하지 않습니다. 그러므로 “GraphRAG 지원”은 pipeline compatibility와 module-level
diagnosis를 의미하며 knowledge graph 품질 보증을 의미하지 않습니다.

## Cycle 안전성

`RAGContainer(max_steps=1000)`이 기본 실행 상한입니다. Positive integer만 허용합니다.
Self-corrective flow는 더 작은 explicit limit을 권장합니다.

```python
rag = RAGContainer(
    "self_corrective",
    [starter, retriever, critic, rewrite, output],
    max_steps=25,
)
```

Answer를 만들기 전에 limit에 도달하면 `FlowExecutionLimitException`이 발생합니다. 실패
State는 container storage에 먼저 저장되고 WebSocket runner가 history/dashboard로 전달하며
`termination_reason="max_steps"`와 diagnosis를 가집니다. 기존 호출자에게 예외를 전달하는
behavior는 유지됩니다.

## `execution_trace` schema

각 event는 raw input/output value 대신 구조와 실행 사실만 기록합니다.

| Field | 의미 |
| --- | --- |
| `execution_id` | Query 안에서 `exec-1`부터 증가하는 deterministic ID |
| `module_id` | 실행 module |
| `execution_index` | 같은 module의 1-based 실행 번호 |
| `revisit_count` | `execution_index - 1`; cycle/retry 관측값 |
| `parent_execution_ids` | 실제 parameter assembly에 사용된 최근 dependency 실행 |
| `dependency_modules` | Module이 선언한 dependency ID |
| `status` | `completed` 또는 `failed` |
| `latency_seconds` | 완료 실행은 module `execute` 시간, 실패는 실패까지 경과시간 |
| `input_keys` / `output_keys` | Content가 아닌 key 이름 |
| `next_modules` | Output validation 후 실제 선택된 다음 module |
| `failure` | 실패 type과 안전하게 제한된 message; 실패 event에만 존재 |

`OR` dependency에서 이전 branch snapshot과 현재 retry predecessor가 모두 parameter
assembly에 사용되면 parent가 여러 개일 수 있습니다. 이 관계는 단일 linear chain이라는
주장이 아니라 causal ancestry graph입니다.

## `execution_summary`

- total/completed/failed execution 수
- module revisit 수와 repeated module 목록
- total latency
- 정상 answer 또는 `module_error`, `max_steps`, `missing_output` termination reason

`diagnosis.graph_health`는 trace availability, failure, revisit, total latency, termination을
요약합니다. Failed event observation의 `path`는 merge parent를 포함한 topological ancestry
목록이며 유일한 원인 경로라고 주장하지 않습니다.

## Snapshot과 frontend

`State.snapshots[module_id]`는 실행 횟수만큼 `Packet`을 보존합니다. Dashboard와 Test Query는
첫 snapshot만 선택하지 않고 모든 execution을 `module#execution_index`로 표시합니다. Trace
panel은 parent, next, status, latency, revisit, failure type을 보여줍니다.

## Agentic workflow 해석

명시적 tool call/decision/rewrite를 module로 모델링하면 hop-level diagnosis가 가능합니다.
그러나 adapter 내부의 숨은 reasoning이나 외부 agent framework 내부 step은 RAGANG이 볼 수
없습니다. 관측이 필요하면 안전한 bounded output key와 module boundary로 노출해야 합니다.


## 종료·실패 보존 계약 보강

`gen`은 선택된 후속 모듈이 있으면 중간 답변입니다. leaf의 유효한 `gen`은 기존처럼
최종 답변이 되며, 명시적인 `terminal=True`로 일찍 완료하거나 `terminal=False`로
계속할 수 있습니다. `terminal=True`에는 비어 있지 않은 문자열 `gen`이 필요합니다.
여러 종료 경로는 먼저 도달한 terminal에서 종료됩니다.

의존성 상태에는 실제 선택한 next 간선만 반영합니다. 비활성 간선이 필요한 AND join은
충족되지 않습니다. 끝내 답변에 도달하지 않으면 `missing_output`이며, 스케줄러 오류도
출력 스냅샷과 함께 실패 상태로 저장합니다.

매 호출의 `run_metadata.run_id`와 UTC `started_at`이 같은 batch의 질문에 공유됩니다.
이벤트에는 run/query/execution ID와 running/completed/failed 상태를 보존합니다.
`execution_summary`의 모듈 소요 시간, 평가 소요 시간, 질문 전체 wall time을 구별합니다.
`evaluation_summary`의 미도달 모듈은 비활성 분기일 수 있으므로 실패 수와 합산하지 않습니다.

`max_concurrency` 기본값은 flow batch당 8이고, `module_timeout_seconds`는 선택적 양의
유한 시간입니다. 시간제한은 cooperative async 실행에 적용됩니다. 동기 블로킹 코드와
이미 시작한 worker thread를 강제로 중단하지 못하므로 사용자 어댑터도 timeout을 설정해야
합니다. 동기 평가는 event loop 밖에서 수행하며 공유 E2E evaluator의 동시 호출은 직렬화합니다.

## 반복 실행의 평가 입력과 스냅샷

각 모듈 평가는 **해당 실행과 실제 부모 실행에서 이어지는 출력**을 먼저 참조합니다.
같은 모듈이 다음 회차를 시작했더라도 대기 중이던 자식의 평가는 이전 회차의 입력을
사용합니다. `Performance.scope.input_execution_ids`에 참조별 실제 실행 ID를 기록합니다.
같은 모듈이 조상 경로에 여러 번 있으면 그 경로 안에서 가장 최근에 완료된 실행을 선택합니다.

조상 경로 밖의 모듈을 명시적으로 참조한 기존 지표는 호환성을 위해 전체 상태의 최신
출력으로 대체합니다. 이런 교차 경로 참조는 부모 의존성이 아니며, 회차별 대응을 원하면
입력을 합류 모듈의 출력으로 전달한 뒤 그 모듈을 참조하세요. 대체된 참조도 실제 사용한
실행 ID를 기록합니다.

이 의미론은 `ancestry-first-v1`로 평가자 설정과 실행 설정에 기록됩니다. 이전 버전의
전역 최신 입력 방식과 fingerprint가 달라, 서로 다른 의미론의 점수 차이를 바로 계산하지
않습니다. 비교하려면 같은 질문을 현재 버전으로 다시 실행하세요.

모듈에 넘기는 입력과 저장 패킷은 복사하여 보존합니다. 자식 모듈이 받은 리스트·딕셔너리를
수정해도 이전 단계의 이력과 그 평가 근거가 바뀌지 않습니다. 외부 연결 객체 대신
직렬화 가능한 값 중심으로 모듈 입출력을 구성하세요.

AND 합류는 선택된 간선의 도착을 기다리는 방식이며, 임의의 비동기 작업을 업무상
같은 회차로 자동 분류하는 correlation key 기능은 없습니다. 서로 독립적으로 반복하는
분기를 합칠 때는 라우터가 양쪽을 같은 회차로 시작하고 회차 값을 검사하는 등의 명시적
정책이 필요합니다. 예제의 `MergeEvidence`가 이 조건을 검사합니다.
활성 선행 모듈의 최신값을 재사용하는 combine-latest 방식이므로, 한 분기만 갱신되면
다른 분기의 기존값과 합류할 수 있습니다. OR 연결에서 같은 키가 겹치면 가장 최근에
완료된 선행 실행의 값이 우선하며 경고를 기록합니다.

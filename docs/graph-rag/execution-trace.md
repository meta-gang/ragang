# Graph, cycle, and agentic execution trace

## 지원 범위

RAGANG의 graph는 **pipeline execution graph**입니다. Linear, conditional branch, `AND`
merge, `OR` dependency, query rewrite, retry/self-correction cycle을 실행하고 관측합니다.
GraphRAG system은 graph retriever/community summarizer를 custom module로 감싸 계측할 수
있습니다.

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

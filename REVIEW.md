# RAGANG 코드 검증 및 발전 방향

> 대상 커밋: `cbfac8a` (v0.0.8b0) · 검토일: 2026-08-03
> 검증 범위: `ragang/` 하위 전체 Python 소스 (어댑터, 코어 엔진, 메트릭, CLI, 네트워크, 쿼리 생성기, 템플릿, usage 예제)
> 검증 방법: 전수 정독 + Python 3.13 실행 검증 (venv에 `websockets/numpy/requests/scikit-learn/scipy/httpx` 설치 후 실제 재현)

각 항목의 **[검증됨]** 표시는 실제로 코드를 실행해 증상을 재현했다는 뜻이고, **[정독]** 은 소스 분석만으로 판단했다는 뜻이다.

---

## 1. 요약

### 1.1 프로젝트 정체성

`pyproject.toml`의 설명은 **"Retrieval Augmented Generation Assessing tool with No Gold"** — 즉 **정답 레이블(ground truth) 없이 RAG 파이프라인을 평가하는 도구**다. 코드에서 읽히는 설계 의도는 다음 네 가지다.

1. **그래프로 선언하는 RAG 파이프라인** — `Linker`로 모듈 간 의존을 잇고, 선형/분기/병합/루프 그래프를 모두 표현 ([usage/](ragang/usage/)에 4가지 예제)
2. **2계층 평가** — 모듈 단위 메트릭(`BaseModule.metrics`) + 종단 메트릭(`BaseContainer.e2e_metrics`)
3. **No-Gold 메트릭 번들** — 임베딩 기하 기반 + LLM-as-judge 기반 빌트인 메트릭 20여 종
4. **관측 도구** — CLI(`ragang run`) + 웹 대시보드(`ragang show`, WebSocket 실시간 스트리밍) + 히스토리 축적

이 조합 자체는 경쟁 도구(RAGAS, TruLens, DeepEval)와 확실히 구분되는 좋은 포지션이다. 대부분의 평가 도구는 파이프라인을 **블랙박스 입출력**으로만 보는데, RAGANG은 파이프라인 **구조를 알고 있어서** "어느 모듈이 병목인가"를 답할 수 있는 유일한 구조를 가졌다.

### 1.2 종합 판정

| 축 | 평가 |
|---|---|
| 아키텍처 설계 | **양호** — 그래프 실행 엔진, 어댑터 추상화, 예외 계층 분리가 명확하고 확장 가능하게 잡혀 있다 |
| 코어 엔진 구현 | **보통** — 선형/분기/병합 그래프는 실제로 동작한다. 다만 루프/중복 파라미터 처리에 무효 코드와 재귀 위험이 있다 |
| 빌트인 메트릭 | **취약** — 20여 종 중 상당수가 생성 불가·크래시·수학적 오류 상태. **이 프로젝트의 핵심 자산인데 가장 검증이 안 된 영역** |
| 사용자 진입 경로 | **차단** — `Linker` 전역 오염 버그로 "여러 flow를 한 파일에 정의해 비교"라는 핵심 유즈케이스가 막혀 있다 |
| 견고성 | **취약** — 외부 API 실패 시 크래시 또는 조용한 오답. 배치 평가 중 rate-limit 한 번이면 전체 중단 |
| 보안 | **주의 필요** — 인증 없는 WS 서버의 경로 탈출, `0.0.0.0` 바인딩, traceback 브로드캐스트 |
| 테스트 | **부재** — 저장소 전체에 테스트 파일 0개 |

**한 문장 요약:** 설계는 좋고 뼈대는 서 있으나, 평가 도구의 생명인 *메트릭의 정확성*과 *실패 시 견고성*이 검증되지 않은 상태로 PyPI에 배포되어 있다.

### 1.3 발견 사항 집계

| 등급 | 건수 | 정의 |
|---|---|---|
| **P0 — 치명적** | 5 | 핵심 기능이 실행 불가하거나 문서와 정반대로 동작 |
| **P1 — 심각** | 14 | 평가 결과의 정확성/신뢰성을 훼손 |
| **P2 — 보통** | 12 | 견고성·보안·운영 |
| **P3 — 경미** | 29 | 코드 품질·일관성·패키징 |
| **합계** | **60** | |

---

## 2. 아키텍처 지도

```
CLI (ragang init / run / show / query-gen)
 └─ cli_script/entry.py
     ├─ run/main.py  ──┐
     └─ show/main.py ──┤
                       │
        core/utils/modules.py :: create_engine()
                       │        └─ 사용자 프로젝트의 manager.py :: containers() 를 동적 import
                       ▼
        core/bases/abstracts/base_engine.py :: FlowEngine
          │  invoke / invoke_batch  →  asyncio.gather 로 쿼리 병렬 실행
          │
          ├─ BaseContainer (flow_id, modules, e2e_metrics, FlowStorage)
          │    └─ BaseModule (module_id, Linker→Dependency, Direction, metrics)
          │         └─ async execute(**params) → dict
          │
          ├─ Status   : 실행 상태 추적 (의존성 충족 판정)
          ├─ State    : 쿼리 1건의 스냅샷 (module_id → list[Packet])
          └─ Packet   : 모듈 1회 실행 결과 (data, formed_output, performances, x_time)
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
   metrics/builtin/*            adapters/*
   (retriever/generator/e2e)    (llm, embedding, milvus)
                       │
                       ▼
   core/network/* (WebSocket) → ragang/web/* (React 번들) → 대시보드
```

**실행 흐름 (`FlowEngine.__execute_flow`)**

1. `starter` 모듈을 큐에 넣고 시작
2. 모듈 실행 → `Packet` 생성 → `State`에 스냅샷 저장
3. `Status.optimize_n_add_xs()`로 실행 상태 갱신
4. `__validate_output()` — 모듈 출력을 다음 모듈들이 요구하는 파라미터 형태로 정형화
5. `__eval()` — 모듈 메트릭 평가 (`param_refs`를 `module_id.key` 형태로 해석)
6. `__schedule_next_module()` — 의존성이 충족된 다음 모듈을 큐에 추가
7. 출력에 `'gen'` 키가 있으면 종료 → e2e 메트릭 평가 → `FlowStorage`에 저장

---

## 3. P0 — 치명적 (핵심 기능 차단)

### P0-1. `Linker`의 `&`/`|` 연산자가 클래스를 전역 오염시킨다 **[검증됨]**

[ragang/core/bases/datas/linker.py:12-19](ragang/core/bases/datas/linker.py#L12-L19)

```python
def __and__(self, other):
    Linker.__or__ = Linker.__prevent_cross_operator_usage   # ← 클래스 속성을 영구 변경
    ...
def __or__(self, other):
    Linker.__and__ = Linker.__prevent_cross_operator_usage  # ← 클래스 속성을 영구 변경
```

"한 의존 표현식 안에서 `&`와 `|`를 섞지 말 것"을 강제하려는 의도인데, 인스턴스가 아니라 **클래스**를 바꾼다. 한 번 `&`를 쓰면 그 프로세스에서 `|`는 **영구히, 전역적으로** 사용 불가가 된다. 되돌리는 코드도 없다.

**재현:**

```
$ python -c "import ragang.usage.merge_graph.main; import ragang.usage.loop_graph.main"
merge container built OK
LOOP FAILED: DependencyConnectionException Dependency links must be formed exclusively '&' or '|'
```

순서를 바꾸면 반대로 merge 쪽이 실패한다. 즉 **`manager.py`에 `&`를 쓰는 flow와 `|`를 쓰는 flow를 동시에 정의할 수 없다.**

이것이 가장 심각한 이유: RAGANG의 존재 이유는 *여러 RAG 파이프라인을 한 자리에서 비교*하는 것인데(`ragang run`은 `-F` 생략 시 `manager.py`의 모든 flow를 실행하도록 설계되어 있다), 그 핵심 유즈케이스가 정확히 막힌다. `usage/` 예제 4개도 서로 함께 import할 수 없다.

**수정 방향:** 클래스가 아니라 인스턴스 상태로 판정한다.

```python
class Linker:
    def __init__(self, module_id: str):
        self.module_id = module_id
        self.dependency_ids: list[str] = []
        self._op: str | None = None          # None | 'and' | 'or'

    def _combine(self, other: 'Linker', op: str) -> 'Linker':
        for side in (self, other):
            if side._op is not None and side._op != op:
                raise DependencyConnectionException(
                    "Dependency links must be formed exclusively '&' or '|'")
        self._op = op
        self.dependency_ids.append(other.module_id)
        self.dependency_ids.extend(other.dependency_ids)
        return self

    def __and__(self, other): return self._combine(other, 'and')
    def __or__(self, other):  return self._combine(other, 'or')

    @property
    def is_or(self) -> bool: return self._op == 'or'
```

---

### P0-2. `api_adapter.py`가 존재하지 않는 클래스를 import한다 **[검증됨]**

[ragang/adapters/api_adapter.py:3](ragang/adapters/api_adapter.py#L3)

```python
from .llm_adapter import BaseLLMAdapter, LocalLLMAdapter, OpenAIAdapter, GeminiAdapter
```

`llm_adapter.py`에 정의된 클래스명은 `OllamaLocalLLMAdapter`다([llm_adapter.py:49](ragang/adapters/llm_adapter.py#L49)). `LocalLLMAdapter`는 없다.

```
$ python -c "import ragang.adapters.api_adapter"
ImportError: cannot import name 'LocalLLMAdapter' from 'ragang.adapters.llm_adapter'
```

모듈 import 자체가 실패하므로 `api_adapter`는 **어떤 경로로도 사용할 수 없다**. 현재 아무도 import하지 않아 드러나지 않았을 뿐이다(그래서 "설정 파일로 provider를 선택한다"는 기능이 통째로 죽어 있다 — 템플릿은 `load_adapters.py`에서 `GeminiAdapter`를 직접 하드코딩한다).

**수정:** 이름을 맞추거나(`OllamaLocalLLMAdapter`), 아니면 `LocalLLMAdapter = OllamaLocalLLMAdapter` 별칭을 두고 provider 팩토리를 실제 사용 경로에 연결한다.

---

### P0-3. 빌트인 메트릭 3종이 생성자 인자를 잘못 넘겨 인스턴스화 불가 **[검증됨]**

`BaseBuiltinMetric.__init__` 시그니처는 `(param_src, llm_adapter=None, embedding_adapter=None)`인데, 아래 3개 클래스는 `param_src`를 건너뛰고 어댑터를 첫 인자로 넘긴다.

| 클래스 | 위치 | 잘못된 호출 |
|---|---|---|
| `PrecisionMetric` | [retriever/non_llm_based.py:284](ragang/metrics/builtin/retriever/non_llm_based.py#L284) | `super().__init__(llm_adapter, embedding_adapter)` |
| `RandomDocumentInjectionEffect` | [retriever/llm_based.py:83](ragang/metrics/builtin/retriever/llm_based.py#L83) | `super().__init__(llm_adapter, embedding_adapter)` |
| `A2RHybridFaithfulnessMetric` | [generator/llm_based.py:544](ragang/metrics/builtin/generator/llm_based.py#L544) | `super().__init__(llm_adapter, embedding_adapter)` |

```
$ PrecisionMetric(mode='embedding', embedding_adapter=Emb())
MetricParamSourceException: Metric 'PrecisionMetric' parameter source is not defined.

$ A2RHybridFaithfulnessMetric(llm_adapter=LLM())
TypeError: 'LLM' object is not iterable      # param_src 자리에 어댑터가 들어가 for 루프에서 터짐
```

`PrecisionMetric`은 `RandomDocumentInjectionEffect`의 의존 대상이기도 하므로 **검색기 평가 계열에서 정답 데이터 기반 정밀도 지표가 통째로 사용 불가**하다.

**수정:** 세 클래스 모두 `param_src`를 자기 시그니처에 받아 `super().__init__(param_src, llm_adapter, embedding_adapter)`로 전달한다.

> 관련: `MutualInformation_KSG.__init__`([generator/non_llm_based.py:98](ragang/metrics/builtin/generator/non_llm_based.py#L98))은 `super()` 호출은 올바르나 자기 시그니처의 어댑터 순서가 base와 반대(`embedding_adapter, llm_adapter`)라 위치 인자로 부르면 뒤바뀐다. 함께 정렬할 것.

---

### P0-4. `--no-save` 플래그가 아무 동작도 하지 않는다 (문서와 정반대) **[검증됨]**

[ragang/cli_script/entry.py:28](ragang/cli_script/entry.py#L28)

```python
parser_run.add_argument('--no-save', action='store_false', dest='x_save', default=False)
```

`default=False` + `store_false` → **플래그를 주든 말든 `x_save`는 항상 `False`**.

[ragang/cli_script/run/main.py:48](ragang/cli_script/run/main.py#L48)에서 `if args.x_save: return` 이므로 **결과는 언제나 히스토리에 저장된다.**

```
$ ragang run -Q custom/q.txt            → x_save=False → 저장됨
$ ragang run -Q custom/q.txt --no-save  → x_save=False → 저장됨  ← 의도와 반대
```

README([templates/init_template/README.md:50-52](ragang/templates/init_template/README.md#L50-L52))는 "포함하면 히스토리에 기록되지 않는다"고 명시한다. 문서가 약속한 동작이 전혀 구현되어 있지 않다.

**수정:**

```python
parser_run.add_argument('--no-save', action='store_true', dest='no_save', default=False)
# run/main.py
if args.no_save:
    return
```

---

### P0-5. `BaseModule.to_dict()`가 `metrics=None`인 모듈에서 크래시 **[검증됨]**

[ragang/core/bases/abstracts/base_module.py:28](ragang/core/bases/abstracts/base_module.py#L28)

```python
"metrics": [m.__class__.__name__ for m in self.metrics],
```

`metrics`의 기본값은 `None`이고, `starter` 모듈은 관례적으로 `metrics=None`으로 만든다(템플릿 `manager.py`, usage 예제 4개 모두). 직렬화 경로(`@serializable` → 웹 대시보드/히스토리)에서 이 모듈에 닿으면 즉시 터진다.

```
$ M('starter', is_starter=True).to_dict()
TypeError: 'NoneType' object is not iterable
```

**수정:** `[... for m in (self.metrics or [])]`

---

## 4. P1 — 심각 (평가 결과의 정확성·신뢰성 훼손)

### P1-1. 모든 메트릭이 동기 함수여서 이벤트 루프를 블로킹한다 **[검증됨 — 측정]**

`BaseMetric.evaluate()`는 동기이고([base_metric.py:17-19](ragang/core/bases/abstracts/base_metric.py#L17-L19)), 내부에서 `requests.post()`(블로킹 HTTP)를 호출한다. 그런데 이 함수는 코루틴 `__run_module` 안에서 호출된다([base_engine.py:151](ragang/core/bases/abstracts/base_engine.py#L151)).

즉 `asyncio.gather`로 쿼리를 병렬화해 놓고, 정작 가장 느린 작업(LLM/임베딩 호출)을 이벤트 루프 위에서 **직렬로** 돌린다.

**측정 (모듈 I/O 0.3s + 메트릭 0.3s, 쿼리 8건):**

```
이상적(완전 병렬) : ~0.6s
실측              : 2.70s      ← 메트릭 8회(2.4s)가 전부 직렬화됨
```

부수 피해: `Packet.x_time`([base_engine.py:139-142](ragang/core/bases/abstracts/base_engine.py#L139-L142))은 모듈 실행 시간만 재는데, 다른 코루틴의 블로킹 메트릭이 루프를 점유하면 그 대기 시간이 x_time에 섞여 들어간다. **성능 측정치 자체가 오염된다.**

**수정 방향:**
- 단기: `await asyncio.to_thread(metric.evaluate, *args)`로 감싸 스레드풀로 밀어낸다 (`__eval`을 async로 전환)
- 중기: `BaseMetric.evaluate`를 `async def`로 바꾸고 어댑터의 `request_async`를 쓰도록 통일 (아래 §6.2 참조)

---

### P1-2. `MutualInformation_KSG`는 수학적으로 무효하고 문서 수가 적으면 크래시 **[검증됨]**

[ragang/metrics/builtin/generator/non_llm_based.py:145](ragang/metrics/builtin/generator/non_llm_based.py#L145)

```python
dist_x = np.max(np.abs(gen_embedding - gen_embedding))   # ← 항상 0
```

자기 자신과의 차이라 **언제나 0**이다. 따라서 `dist_x < eps`는 항상 참이고 `count_x`는 항상 `N-1`이 된다. KSG 추정량의 x-주변부(marginal) 항이 상수로 고정되므로 이 지표는 상호정보량을 전혀 추정하지 못한다.

근본적으로도 문제다. 생성 답변 임베딩은 **하나뿐**이라 x축 표본이 1개인데, 상호정보량은 두 확률변수의 표본 분포가 있어야 정의된다. 또 표준 KSG는 digamma 함수 ψ(·)를 쓰는데 여기서는 `np.log`를 쓴다([:154-157](ragang/metrics/builtin/generator/non_llm_based.py#L154-L157)).

추가로 [:134](ragang/metrics/builtin/generator/non_llm_based.py#L134)의 `distances[self.k - 1]`은 문서가 `k`개 이하일 때 IndexError:

```
$ MutualInformation_KSG(k=3).evaluate(['d1','d2'], 'ans')
IndexError: list index out of range
```

**수정 방향:** `sklearn.feature_selection.mutual_info_regression`이나 검증된 KSG 구현으로 대체하거나, 이 지표가 무엇을 재려는지 재정의한다. 현 상태로는 배포에서 빼는 것이 낫다.

---

### P1-3. `RetrievaltopkMeanAnswerSimilarity`가 문서 1건에서 크래시하고 점수가 비유계 **[검증됨]**

[ragang/metrics/builtin/generator/non_llm_based.py:231-233](ragang/metrics/builtin/generator/non_llm_based.py#L231-L233)

```python
drops = [sorted_similarities[i] - sorted_similarities[i+1] for i in range(len(sorted_similarities)-1)]
drop_index = drops.index(max(drops))          # ← drops가 빈 리스트면 ValueError
k = min(max(1, drop_index), len(chunk_vecs)-1) # ← 문서 1건이면 k=0
```

```
$ RetrievaltopkMeanAnswerSimilarity().evaluate(['only-one'], 'ans', 'q')
ValueError: max() iterable argument is empty
```

top-k 검색에서 결과가 1건인 것은 흔한 상황이다(필터 적용, 임계값 컷 등).

또 [:241](ragang/metrics/builtin/generator/non_llm_based.py#L241)의 `base_score = 1 - cos_all / (cos_topk + 1e-6)`은 `cos_topk`가 0에 가까우면 **-10⁶ 규모의 값**이 나온다. `Performance`에 범위 검증이 없어 그대로 대시보드에 표시된다.

---

### P1-4. LLM 어댑터가 에러를 반환하면 모든 LLM 메트릭이 KeyError로 죽는다 **[검증됨]**

어댑터는 실패 시 `{"error": "..."}`를 반환하는 계약이다([llm_adapter.py:73,128,151](ragang/adapters/llm_adapter.py#L73)). 그런데 메트릭들은 `response["text"]`를 무조건 인덱싱한다.

```
$ A2RYNFaithfulnessMetric(llm_adapter=<429 반환하는 어댑터>).evaluate(['doc'], 'gen')
KeyError: 'text'
```

`FlowEngine.__run_container`는 `asyncio.gather(..., return_exceptions=False)`를 쓰므로([base_engine.py:259](ragang/core/bases/abstracts/base_engine.py#L259)) **쿼리 400건 배치 평가 중 rate-limit이 한 번만 걸려도 전체가 중단되고 이미 끝난 결과도 저장되지 않는다.**

해당 패턴이 있는 곳: `A2RYNFaithfulnessMetric`, `A2RSimpleScoringFaithfulnessMetric`, `A2RHallucinationFaithfulnessMetric`, `A2RTruthfulFaithfulnessMetric`, `RandomDocumentInjectionEffect`, `E2ESYNRelevancyMetric`(일부만 방어), 그리고 템플릿의 `MyGenerationModule.execute`([templates/init_template/modules/impls.py:73](ragang/templates/init_template/modules/impls.py#L73)).

**수정 방향:** 어댑터 반환을 dict가 아니라 타입으로 만든다 (§6.1 참조). 최소한 `response.get("text")`가 None이면 `Performance(_eval=False)`로 스킵 처리.

---

### P1-5. claim이 0개이면 ZeroDivisionError **[검증됨]**

[generator/llm_based.py:137](ragang/metrics/builtin/generator/llm_based.py#L137), [:423](ragang/metrics/builtin/generator/llm_based.py#L423)

```python
return Performance(score=score / len(claim_list), ...)
```

`claim_list`는 LLM 응답에서 `^\d+\.\s+` 정규식에 걸리는 줄만 모은다. LLM이 번호 없는 형식으로 답하거나 빈 답변을 주면 리스트는 비고, 나눗셈에서 터진다.

```
$ A2RYNFaithfulnessMetric(llm_adapter=<"no list here" 반환>).evaluate(['doc'], 'gen')
ZeroDivisionError: division by zero
```

같은 파일의 `A2RSimpleScoringFaithfulnessMetric`([:257](ragang/metrics/builtin/generator/llm_based.py#L257))은 `if claim_list else 0` 가드가 있다 — 같은 파일 안에서도 처리가 불일치한다.

---

### P1-6. 파싱 실패 시 누적 점수를 리셋하고, 중복 카운트한다 **[정독]**

[generator/llm_based.py:121-137](ragang/metrics/builtin/generator/llm_based.py#L121-L137)

```python
score = 0
for claim in claim_list:
    ...
    try:
        for line in reversed(response["text"].strip().splitlines()):
            if line.startswith("Groundedness:"):
                if value == "Grounded":
                    score += 1          # ← break 없음
    except ValueError:
        score = 0.0                     # ← 누적값 전체를 날림
```

두 가지 결함이 겹쳐 있다.

1. `break`가 없어서 응답에 `Groundedness:` 줄이 두 번 나오면(few-shot 예시를 그대로 되뇌는 소형 모델에서 흔함) **한 claim이 2점을 받는다.** 점수가 1.0을 넘을 수 있다.
2. 예외 시 `score = 0.0`은 그 claim만 0으로 치는 게 아니라 **앞서 누적한 점수 전부를 폐기**한다.

게다가 잡는 예외가 `ValueError`인데, 실제로 여기서 나는 예외는 `KeyError('text')`(P1-4)라 잡히지도 않는다. `A2RTruthfulFaithfulnessMetric`([:406-423](ragang/metrics/builtin/generator/llm_based.py#L406-L423))도 동일.

---

### P1-7. `A2RHybridFaithfulnessMetric`이 인자를 잘못된 슬롯에 넘긴다 **[검증됨]**

[generator/llm_based.py:687](ragang/metrics/builtin/generator/llm_based.py#L687)

```python
claims = self._extract_claims(gen)
```

시그니처는 `_extract_claims(self, ret_docs=None, gen=None)`이다([:547](ragang/metrics/builtin/generator/llm_based.py#L547)). 위치 인자로 넘긴 `gen`이 **`ret_docs` 슬롯**에 들어가고 `gen`은 `None`으로 남는다. 프롬프트에 `<Answer>\nNone`이 박혀 나간다.

P0-3 때문에 이 클래스는 현재 생성조차 안 되지만, P0-3을 고치면 즉시 드러난다. `self._extract_claims(gen=gen)`으로 수정.

---

### P1-8. e2e 빌트인 메트릭의 시그니처가 엔진 호출 규약과 불일치 **[정독]**

엔진은 e2e 메트릭을 이렇게 부른다([base_engine.py:238](ragang/core/bases/abstracts/base_engine.py#L238)):

```python
performances = [m.evaluate(query, gen) for m in cont.metrics]   # gen 은 str 하나
```

그런데 `e2e/non_llm_based.py`의 두 메트릭은 답변 **리스트**를 기대한다.

| 메트릭 | 시그니처 | 엔진이 넘기는 것 |
|---|---|---|
| `e2eCosineConsistencyMetric` | `evaluate(query, gens: list[str])` | `gen: str` |
| `e2eCovarianceConsistencyMetric` | `evaluate(query, gens: list[str])` | `gen: str` |

`len(gens)`가 문자열 길이가 되고, `create_embeddings(gens)`에 문자열이 그대로 들어간다. `LocalEmbeddingAdapter`는 문자열을 슬라이싱해 **글자 조각들을 임베딩**하게 된다([embedding_adapter.py:39-41](ragang/adapters/embedding_adapter.py#L39-L41)). 크래시 없이 **무의미한 숫자**가 나온다 — 가장 위험한 종류의 버그다.

이 두 지표는 "같은 쿼리를 여러 번 돌렸을 때 답변이 일관적인가"를 재려는 의도로 보인다. 그렇다면 엔진에 **반복 실행(n-sampling) 기능**이 필요한데 현재 없다. 규약을 맞추거나 기능을 추가해야 한다.

---

### P1-9. 루프 그래프의 중복 파라미터 처리가 무효 코드다 **[정독]**

[base_engine.py:174-179](ragang/core/bases/abstracts/base_engine.py#L174-L179)

```python
formed_output = state.get_latest_packet(dep).formed_output[n_mid]
if duplicated := set(formed_output.keys()).intersection(formed_params.keys()):
    loop_end_mid = status.find_loop_before_mid(n_mid, dep_modules)
    if loop_end_mid and loop_end_mid == dep:
        for k in duplicated:
            formed_output[k] = state.get_latest_packet(dep).formed_output[n_mid][k]  # ← 자기 자신을 대입
```

좌변과 우변이 **같은 객체의 같은 키**다. 완전한 no-op. "루프를 돌아 되돌아왔을 때 최신 값을 쓴다"는 의도가 전혀 구현되지 않았다.

부수 문제: `formed_output`은 Packet에 저장된 dict를 **복사 없이 참조**한다. 이후 `formed_params.update(formed_output)`은 읽기라 괜찮지만, 위 대입문이 실제 로직으로 바뀌는 순간 **과거 스냅샷을 소급 변조**하게 된다. 스냅샷은 불변이어야 한다.

---

### P1-10. `Status`의 그래프 순회에 사이클 보호가 없다 **[정독]**

[status.py:13-17](ragang/core/bases/datas/status.py#L13-L17)의 `find_links`, [status.py:37-43](ragang/core/bases/datas/status.py#L37-L43)의 `find_loop_before_mid` 둘 다 방문 집합 없이 재귀한다.

`find_loop_before_mid`는 특히 두 가지 문제가 있다.

1. **첫 outgoing edge만 따라간다** — `for link in flow_graph: if link[0]==target: return find_loop_before_mid(link[1], ...)`. 분기 그래프에서 첫 번째 가지에 답이 없으면 나머지를 보지 않고 `None`을 반환한다. 백트래킹이 없다.
2. **사이클에서 무한 재귀** — 루프 그래프에서 dep_mids를 포함하지 않는 사이클에 들어가면 `RecursionError`.

루프 그래프가 이 프로젝트의 명시적 지원 기능(`usage/loop_graph/`)인 만큼, 이 순회는 BFS + `visited` 집합으로 다시 써야 한다.

---

### P1-11. `MilvusAdapter`가 설정 파일의 host/port를 버린다 **[정독]**

[milvus_adapter.py:55-60](ragang/adapters/milvus_adapter.py#L55-L60)

```python
self.host = settings["config"]["api_url"].split(":")[0]   # 설정에서 읽어 저장
self.port = settings["config"]["api_url"].split(":")[1]
...
super().__init__(host, port, alias)   # ← 생성자 기본값("localhost","19530")으로 덮어씀
```

`super().__init__`이 방금 설정에서 읽은 값을 **생성자 인자의 기본값으로 되돌린다**. 템플릿의 `vector_db.json`이 우연히 `localhost:19530`이라 지금은 티가 안 나지만, 원격 Milvus를 설정하면 조용히 localhost로 붙으려다 실패한다.

`connect()`가 예외를 삼키고 print만 하므로([:74-75](ragang/adapters/milvus_adapter.py#L74-L75)) 연결 실패도 조용하다. 이후 검색에서 엉뚱한 에러가 난다.

**수정:** `super().__init__(...)`을 먼저 호출하고 그 다음에 설정값을 덮어쓴다.

---

### P1-12. NaN 점수가 비표준 JSON으로 히스토리에 기록된다 **[검증됨]**

여러 LLM 메트릭이 파싱 실패 시 `score=np.nan`을 반환한다. `update_history`는 `json.dump`로 저장한다([core/utils/cli.py:31](ragang/core/utils/cli.py#L31)).

```
$ json.dumps(Performance(score=np.nan, ...).serialize())
{"_Performance__score": NaN, ...}

$ 엄격한 JSON 파서로 읽기 → ValueError: NaN
```

Python `json`은 `NaN`을 관대하게 쓰고 읽지만 **RFC 8259 표준 JSON이 아니다**. 웹 대시보드의 `JSON.parse`, `jq`, 다른 언어의 파서는 전부 실패한다. 이 히스토리 파일은 대시보드가 읽는 대상이다([runner.py:227](ragang/core/network/runner.py#L227)).

**수정:** `Performance`에 `status` 필드를 두고 NaN 대신 `status='error'` + `score=None`으로 표현한다.

---

### P1-13. `Performance.serialize()`가 이름 맹글링된 키를 내보낸다 **[검증됨]**

[performance.py:7-10](ragang/core/bases/datas/performance.py#L7-L10)이 `self.__score` 같은 private 속성을 쓰는데, `@serializable` 데코레이터는 `self.__dict__`를 그대로 순회한다([serializable.py:17-18](ragang/core/decorators/serializable.py#L17-L18)).

```json
{"_Performance__score": 0.75, "_Performance__unit": "", "_Performance__metric": "ACS", "_Performance__did_eval": true}
```

히스토리 파일 포맷과 WebSocket 페이로드 스키마가 **Python 이름 맹글링 규칙에 묶여 버렸다.** 클래스명을 바꾸면 저장된 히스토리를 못 읽는다. 프론트엔드도 `_Performance__score`를 하드코딩해야 한다.

**수정:** `Performance`를 `@dataclass(frozen=True)`로 만들고 명시적 `to_dict()`를 제공한다. (P1-12의 status 필드와 함께 처리)

---

### P1-14. 인덱싱 코퍼스와 쿼리 생성 코퍼스가 서로 다르다 **[정독]**

| 경로 | 대상 파일 | 청킹 |
|---|---|---|
| 벡터DB 인덱싱 ([load_adapters.py:46-51](ragang/templates/init_template/config/load_adapters.py#L46-L51)) | `.txt` **만** | 500 **문자** 단위, 오버랩 없음 |
| 쿼리 생성 ([document_loader.py:141](ragang/core/utils/query_generator/document_loader.py#L141)) | `.pdf` **만** | 5 **문장** 단위, 1문장 오버랩 |

템플릿의 `datas/docs/`에는 같은 작품의 `.txt`와 `.pdf`가 **둘 다** 들어 있다. 즉 인덱스는 txt에서, 질문은 pdf에서 만들어진다. 파일 하나만 형식이 다르거나 내용이 어긋나면 **평가 대상과 질문 대상이 어긋난 채로 점수가 나온다.**

거기에 `settings.py`의 `CHUNK_SIZE=5`/`CHUNK_OVERLAP=1`은 **문장** 단위인데([document_loader.py:47,71-73](ragang/core/utils/query_generator/document_loader.py#L71-L73)), `load_adapters`의 `500`은 **문자** 단위다. 이름은 같은 "청크"인데 단위가 다르고, 둘 중 하나(인덱싱)는 설정으로 조정할 수도 없다.

README는 "Any directory containing documents"라고 하지만 실제로는 PDF만 처리된다([README.md:37](README.md#L37)).

**수정 방향:** 단일 문서 로더 + 단일 청킹 정책으로 통일하고, 지원 확장자를 설정으로 노출한다. 인덱싱과 쿼리 생성이 **같은 청크 집합**을 공유해야 한다(그래야 `Query.reference`의 chunk_idx가 의미를 갖는다 — 현재 이 필드는 생성만 되고 평가에서 쓰이지 않는다).

---

## 5. P2 — 보통 (견고성 · 보안 · 운영)

### P2-1. 매 CLI 실행마다 벡터DB를 drop하고 전량 재임베딩한다 **[정독]**

[load_adapters.py:12-20, 37-57](ragang/templates/init_template/config/load_adapters.py#L12-L20)

`__init_milvus()`는 컬렉션이 있으면 **무조건 drop 후 재생성**하고, `load()`는 모든 문서를 다시 임베딩해 insert한다.

`load()`는 `manager.py::containers()`에서 호출되고, `containers()`는 `create_engine()`이 **모든 CLI 명령마다** 호출한다([core/utils/modules.py:31-32](ragang/core/utils/modules.py#L31-L32)).

결과: `ragang run`을 실행할 때마다, `ragang show`로 대시보드를 열 때마다 **전체 코퍼스가 재임베딩된다.** 임베딩 API 비용과 시작 지연이 실행 횟수에 비례해 늘어난다. 평가 도구는 같은 인덱스에 대해 여러 번 돌려 비교하는 게 정상 사용 패턴인데, 그때마다 인덱스가 바뀌면 **비교 자체가 성립하지 않는다.**

**수정:** 인덱싱을 별도 명령(`ragang index`)으로 분리하고, `containers()`는 기존 인덱스에 연결만 하도록 한다.

---

### P2-2. WebSocket `file_name`에 경로 탈출 취약점 **[검증됨]**

[runner.py:119-131](ragang/core/network/runner.py#L119-L131), [:155-160](ragang/core/network/runner.py#L155-L160)

```python
QUERY_DIR = Path(os.getcwd()) / 'datas/queries/custom'
file_name = settings.get("file_name")        # 클라이언트가 보낸 값
file_path = QUERY_DIR / file_name            # 정규화·경계 검사 없음
```

```
file_name='../../../../etc/hosts.txt'  →  /home/user/proj/datas/queries/custom/../../../../etc/hosts.txt
file_name='/etc/passwd.txt'            →  /etc/passwd            ← Path 연산자가 절대경로면 좌변을 버린다
```

검증하는 것은 확장자뿐이고, WS 서버에는 **인증이 없다**. 읽은 내용은 쿼리로 LLM에 전송되므로 파일 내용이 외부로 나간다.

**수정:**

```python
base = (Path(os.getcwd()) / 'datas/queries/custom').resolve()
target = (base / file_name).resolve()
if not target.is_relative_to(base):
    raise NotAllowedQueryFileException(file_name)
```

---

### P2-3. 대시보드 HTTP 서버가 `0.0.0.0`에 바인딩된다 **[검증됨]**

[show/main.py:31](ragang/cli_script/show/main.py#L31)

```python
server = HTTPServer(('0.0.0.0', port), Handler)   # 모든 인터페이스
...
host: str = "127.0.0.1"                            # 안내 문구와 브라우저 URL만 로컬호스트
```

WS 서버는 `127.0.0.1`로 올바르게 바인딩되는데([:43](ragang/cli_script/show/main.py#L43)) HTTP 서버만 전체 노출이다. 사용자에게는 "http://127.0.0.1:8080에서 실행 중"이라고 안내하므로 노출 사실을 알 수 없다. 카페·공용 와이파이에서 평가 결과가 LAN 전체에 열린다.

**수정:** `HTTPServer((host, port), Handler)` — 이미 있는 `host` 변수를 쓴다.

---

### P2-4. 예외 traceback을 모든 구독자에게 브로드캐스트 **[정독]**

[runner.py:62-68](ragang/core/network/runner.py#L62-L68)

```python
except Exception as e:
    await self.handler.broadcast("error", {"traceback": traceback.format_exc()})
```

절대 경로, 사용자명, 내부 구조가 그대로 나간다. P2-2와 결합하면 파일시스템 탐색의 피드백 채널이 된다. 개발 모드 플래그로 감싸거나 요청한 소켓에만 보내야 한다.

---

### P2-5. 동기 HTTP 호출에 타임아웃이 없다 **[정독]**

`requests.post()` 호출부([llm_adapter.py:64](ragang/adapters/llm_adapter.py#L64), [:120](ragang/adapters/llm_adapter.py#L120), [:181](ragang/adapters/llm_adapter.py#L181), [embedding_adapter.py:47](ragang/adapters/embedding_adapter.py#L47), [:81](ragang/adapters/embedding_adapter.py#L81), [:122](ragang/adapters/embedding_adapter.py#L122)) 전부 `timeout` 인자가 없다. 비동기 경로만 `timeout=30.0`을 준다.

`requests`의 기본 타임아웃은 **무한대**다. 응답 없는 서버 하나가 배치 평가를 영구 정지시킨다. 재시도·백오프도 없다(쿼리 생성기에만 있다).

---

### P2-6. 어댑터 실패가 조용히 잘못된 값으로 전파된다 **[정독]**

| 함수 | 실패 시 반환 | 하류에서 벌어지는 일 |
|---|---|---|
| `create_embeddings` | `np.array([])` | `[0]` 인덱싱 → IndexError, 또는 `cosine_similarity`에서 shape 에러 |
| `MilvusAdapter.retrieve` | `None` | `for sublist in None` → TypeError ([impls.py:24](ragang/templates/init_template/modules/impls.py#L24)) |
| `MilvusAdapter.connect` | (예외 삼킴, print만) | 이후 모든 검색이 실패 |
| `*.request` | `{"error": ...}` | P1-4의 KeyError |

에러가 **호출 지점에서 멀리 떨어진 곳에서** 다른 모습으로 터진다. 디버깅이 어렵고, 최악의 경우 빈 결과가 "점수 0"으로 조용히 기록된다.

---

### P2-7. `GeminiAdapter.request`의 except 블록에서 `UnboundLocalError` 가능 **[정독]**

[llm_adapter.py:187-190](ragang/adapters/llm_adapter.py#L187-L190)

```python
except requests.exceptions.RequestException as e:
    error_details = response.json() if response.content else {}   # response 가 미정의일 수 있음
```

`requests.post()` 자체가 연결 오류로 던지면 `response`는 바인딩되지 않는다. 원래 예외 대신 `UnboundLocalError`가 나와 원인을 가린다.

---

### P2-8. `load_user_containers`가 모든 예외를 뭉갠다 **[정독]**

[core/utils/modules.py:11-27](ragang/core/utils/modules.py#L11-L27)

```python
try:
    ...
    raise NoEntryPointException()          # 자기가 던진 것도
    raise RagangStructureException(...)     # 자기가 던진 것도
except Exception as e:
    raise RagangLoadError(f"Failed to load containers() from {proj_root}/manager.py") from e
```

친절하게 만든 `NoEntryPointException`("`ragang init`을 실행하세요") 메시지가 일반 메시지로 덮인다. `from e`로 체인은 남지만 사용자가 보는 첫 줄은 도움이 안 된다.

같은 함수의 [:14](ragang/core/utils/modules.py#L14) `sys.path.insert(0, str(root))`는 **복원되지 않고**, `importlib.import_module("manager")`는 모듈을 캐시한다. 한 프로세스에서 서로 다른 프로젝트를 두 번 로드하면 첫 번째 것이 재사용된다.

---

### P2-9. `ragang init a/b/c`가 실패한다 **[정독]**

[init/main.py:19](ragang/cli_script/init/main.py#L19) — `os.mkdir(target_path)`는 중간 디렉터리를 만들지 않는다. 최근 커밋 두 개(`7d7afa6`, `10f42d2` "fix: mkdir if not exitst")가 이 근처를 건드렸지만 중첩 경로는 여전히 안 된다.

```python
target_path.mkdir(parents=True, exist_ok=True)
```

[:29](ragang/cli_script/init/main.py#L29)의 `raise RagangInitError(e)`도 `from e`가 없어 원래 traceback이 끊긴다.

---

### P2-10. `'gen'`이 사실상 예약어인데 검증·문서화되지 않았다 **[정독]**

[packet.py:16](ragang/core/bases/datas/packet.py#L16)

```python
self.is_answer: bool = 'gen' in data.keys()
```

어떤 모듈이든 출력 dict에 `'gen'` 키가 있으면 **플로우가 즉시 종료된다**([base_engine.py:224-225](ragang/core/bases/abstracts/base_engine.py#L224-L225)). 중간 모듈이 무심코 `gen`이라는 이름을 쓰면 파이프라인이 조용히 잘려나가고 아무 경고도 없다.

개발 중에도 이 위험을 인지한 흔적이 있다 — [base_container.py:44-46](ragang/core/bases/abstracts/base_container.py#L44-L46)에 `'gen'`을 예약어로 막는 코드가 주석 처리되어 남아 있다. 최소한 문서화하거나, 명시적 `is_output=True` 플래그로 종료 조건을 바꾸는 편이 안전하다.

---

### P2-11. API 키가 평문 `settings.py`에 저장되고 템플릿에 `.gitignore`가 없다 **[정독]**

[templates/init_template/settings.py:10](ragang/templates/init_template/settings.py#L10) — `API_KEY = ""`. README는 여기에 키를 넣으라고 안내한다.

환경변수 대체 경로가 없고, `ragang init`이 생성하는 프로젝트에 `.gitignore`가 없어 사용자가 그대로 커밋할 가능성이 높다. 최소한 `os.environ.get("RAGANG_API_KEY", "")` 폴백과 템플릿 `.gitignore`를 제공해야 한다.

---

### P2-12. 기본 설정 경로가 설치된 패키지 내부를 가리킨다 **[정독]**

[api_adapter.py:17](ragang/adapters/api_adapter.py#L17), [milvus_adapter.py:43](ragang/adapters/milvus_adapter.py#L43)

```python
os.path.join(jsonfile_dir, "..", "uploaded", "api_config.json")   # → site-packages/ragang/uploaded/
```

사용자 설정을 `site-packages` 안에서 찾는다. 해당 디렉터리는 저장소에 없고, 있더라도 재설치 때 날아가며 여러 프로젝트가 설정을 공유하게 된다. 사용자 프로젝트 루트 기준으로 잡아야 한다.

---

## 6. P3 — 경미 (품질 · 일관성 · 패키징)

### 테스트와 검증

| # | 항목 |
|---|---|
| P3-1 | **테스트 파일이 하나도 없다.** `.gitignore`에 `ragang/test/`, `test_user_proj/`가 등록된 걸 보면 로컬에서 수동 확인만 해 온 것으로 보인다. 위 P0/P1 결함 대부분은 단위 테스트 한 줄이면 잡혔을 것들이다 |
| P3-2 | CI 설정 없음. lint(ruff/flake8), 타입 체크(mypy), 포맷터 없음 |

### 구조 · 중복

| # | 항목 | 위치 |
|---|---|---|
| P3-3 | `BaseBuiltinMetric`이 **6개 파일에 동일한 내용으로 중복 정의**. 어느 것을 상속했는지 파일마다 다르다 | `metrics/builtin/*/*.py` |
| P3-4 | `retriever/llm_based.py`가 `BaseMetric`을 `base_module`에서 import — 우연한 재수출에 의존 | [retriever/llm_based.py:42](ragang/metrics/builtin/retriever/llm_based.py#L42) |
| P3-5 | 결과 병합 로직이 3곳에 복붙 | [base_engine.py:261-266](ragang/core/bases/abstracts/base_engine.py#L261-L266), [:286-291](ragang/core/bases/abstracts/base_engine.py#L286-L291), [:320-325](ragang/core/bases/abstracts/base_engine.py#L320-L325) |
| P3-6 | `asyncio.gather(return_exceptions=False)` 뒤의 `if isinstance(res, Exception)` 분기는 **도달 불가**(3곳). 실제로는 예외가 그대로 전파돼 배치 전체가 죽는다 | 위와 동일 |
| P3-7 | `Runner._install_status_callback`이 심는 `cont.storage._on_module_status`를 **아무도 호출하지 않는다**(dead code). 실제 상태 전송은 `SocketSender`가 별도로 한다 | [runner.py:37-49](ragang/core/network/runner.py#L37-L49) |
| P3-8 | `_parse_json_queries`에 **도달 불가한 중복 except 블록** | [query_generator.py:158-163](ragang/core/utils/query_generator/query_generator.py#L158-L163) |
| P3-9 | `ragang.usage.*` 13개 패키지(데모 코드)가 **배포 휠에 포함**된다 | `pyproject.toml` `packages={find={}}` |
| P3-10 | 저장소 루트에 빈 `__init__.py` — 루트는 패키지가 아니다 | [`__init__.py`](__init__.py) |
| P3-11 | `ragang/web/.DS_Store`가 커밋되어 있다 | |

### 정확성에 영향 없는 결함

| # | 항목 | 위치 |
|---|---|---|
| P3-12 | 중복 module_id 에러 메시지가 **항상 `set()`** — `u_ids.difference(set(ids))`는 정의상 공집합. 탐지는 되지만 어느 id가 중복인지 알려주지 못한다 **[검증됨]** | [base_container.py:50-52](ragang/core/bases/abstracts/base_container.py#L50-L52) |
| P3-13 | WS 토픽/필드 오타가 프로토콜에 고정: `module-statu`, `statu` | [socket_sender.py:9-12](ragang/core/network/socket_sender.py#L9-L12) |
| P3-14 | `PERSONALITY_TRAITS`에 **콤마 누락** → `"비이성적인" "기만적인"`이 암묵적 문자열 결합으로 `"비이성적인기만적인"` 한 항목이 됨 | [scenario_generator.py:56-57](ragang/core/utils/query_generator/scenario_generator.py#L56-L57) |
| P3-15 | `run/main.py`가 빈 줄을 쿼리로 넣는다(Runner는 거른다). 파일을 연 뒤에 확장자를 검증한다 | [run/main.py:23-31](ragang/cli_script/run/main.py#L23-L31) |
| P3-16 | 루프 변수 `flow_id`가 함수 파라미터를 섀도잉 | [run/main.py:52](ragang/cli_script/run/main.py#L52) |
| P3-17 | `engine.invoke_batch(queries)`가 `flow_id`를 무시(이미 `create_engine`이 필터링해서 결과적으론 맞다). 의도가 코드에 드러나지 않는다 | [run/main.py:45](ragang/cli_script/run/main.py#L45) |
| P3-18 | `Direction.add_direction`의 타입 힌트가 `list[tuple[str,str]]`인데 실제로는 단일 tuple을 받는다 | [linker.py:40](ragang/core/bases/datas/linker.py#L40) |
| P3-19 | `update_history`는 로컬 타임존, `runner._ts_str`는 KST 고정 — 같은 데이터에 두 종류의 타임스탬프 | [cli.py:23](ragang/core/utils/cli.py#L23) vs [runner.py:14-15](ragang/core/network/runner.py#L14-L15) |
| P3-20 | `api_adapter` 클래스명이 소문자(PEP 8 위반) | [api_adapter.py:8](ragang/adapters/api_adapter.py#L8) |
| P3-21 | HTTP 클라이언트가 `requests`(동기)와 `httpx`(비동기)로 이원화 — httpx로 통일 가능 | `adapters/` |

### 쿼리 생성기

| # | 항목 | 위치 |
|---|---|---|
| P3-22 | `Orchestrator`가 `GeminiAdapter`를 **하드코딩** — provider 추상화를 무시한다. OpenAI/로컬 모델로 `query-gen` 불가 | [orchestrator.py:39](ragang/core/utils/query_generator/orchestrator.py#L39) |
| P3-23 | `load_user_config()`가 3개 클래스에서 각각 호출되어 `settings.py`를 **매번 재실행**한다 | orchestrator/query_generator/content_analyzer |
| P3-24 | `summarize_chunks`가 루프 안에서 `asyncio.run()`을 문서당 2회 호출 — 이벤트 루프 반복 생성/파괴, 실행 중인 루프 안에서는 호출 불가 | [content_analyzer.py:105,116](ragang/core/utils/query_generator/content_analyzer.py#L105) |
| P3-25 | `_call_llm_and_parse_async`가 호출마다 새 `httpx.AsyncClient`를 만든다(connection pooling 무효) | [llm_adapter.py:41](ragang/adapters/llm_adapter.py#L41) |
| P3-26 | `_save_results_to_txt`가 실제로는 JSON을 쓴다(이름 불일치). 주석 처리된 옛 구현이 15줄 남아 있다 | [orchestrator.py:142-192](ragang/core/utils/query_generator/orchestrator.py#L142-L192) |
| P3-27 | `gen/main.py`가 `load_user_config()` 결과를 출력에만 쓰고 버린다(`Orchestrator`가 다시 로드) | [gen/main.py:11-15](ragang/cli_script/gen/main.py#L11-L15) |

### 배포 · 문서 · 프론트엔드

| # | 항목 |
|---|---|
| P3-28 | **루트 `README.md`가 템플릿용 문서 내용이다.** 패키지 소개, 설치법, 개념 설명, API 레퍼런스가 없다. PyPI 랜딩 페이지가 "Sample Rag flow"로 시작한다 |
| P3-29 | 프론트엔드 **소스가 저장소에 없고 빌드 산출물만** 커밋되어 있다. 번들에 `ws://127.0.0.1:8081`이 하드코딩되어 있어 포트 변경이 불가능하다 **[검증됨]**. 포트 8080/8081도 파이썬 쪽에 하드코딩이고 점유 시 처리가 없다 |
| P3-30 | `docker-compose.yml`의 **볼륨이 전부 주석 처리**되어 있다 — 컨테이너를 지우면 인덱스가 사라진다. `version: '3.5'`는 Compose V2에서 폐기된 키다 |

---

## 7. 횡단 관점: 지금 상태를 어떻게 볼 것인가

### 7.1 결함의 분포가 말해주는 것

P0/P1 19건 중 **11건이 `metrics/builtin/`에 몰려 있다.** 코어 엔진(`base_engine.py`, `base_container.py`, `linker.py`)은 usage 예제 3종이 실제로 끝까지 도는 것을 확인했다:

```
linear -> {'linear_graph': {...: {'query':'q1','answer':'q1[advanced]'}, ...}}
merge  -> {'merge_graph':  {...: {'answer':'[hello-starter-branch-first_ret & hello-starter-branch-second_ret]-output'}}}
```

즉 **뼈대는 서 있다.** 문제는 그 위에 얹힌 평가 로직이다. 그리고 평가 로직이야말로 이 프로젝트가 파는 상품이다.

원인은 명확하다 — `metrics/builtin/`은 여러 사람이 각자 파일을 맡아 쓴 흔적이 뚜렷하다(`BaseBuiltinMetric` 6중 복제, docstring 언어/스타일 상이, 에러 처리 방식 제각각, 같은 파일 안에서도 0-division 가드가 있는 곳과 없는 곳이 섞임). **공통 계약을 코드로 강제하지 않고 관례로만 두었기 때문에** 각 구현이 조금씩 다른 가정 위에 서게 됐다.

### 7.2 "No Gold"의 과학적 공백 — 가장 중요한 지적

이건 버그가 아니라 프로젝트의 근본 과제다.

**(a) 지표들이 서로 독립적이지 않다.** 현재 no-gold 메트릭 상당수가 임베딩 코사인 유사도의 변주다:

`AQS`(query↔gen), `ACS`(chunks↔gen), `ACSV`(각도 분산), `PCSV`(쌍별 분산), `RDA`(분산 역수), `RMAS`(top-k 중심 비교), `GECE`(유클리드 거리), `ECS`(local+global 평균), `CosineSimilarityMetric`, `DiversityMetric`, `EuclideanDistanceMetric`, `ManhattanDistanceMetric`…

같은 임베딩 공간에서 같은 벡터들로 계산하니 **상호 상관이 매우 높을 가능성이 크다.** 대시보드에 12개를 띄워도 실질 정보량은 1~2 차원일 수 있다. *지표 개수는 신뢰의 근거가 아니다.*

**(b) 지표가 실제 품질과 상관된다는 근거가 없다.** No-gold 평가 도구의 생명선은 딱 하나다 — *"gold가 있는 벤치마크에서, 이 no-gold 지표가 gold 기반 지표와 유의미하게 상관한다"* 를 보이는 것. 현재 저장소에 이 검증이 전혀 없다. 이것이 없으면 RAGANG의 점수는 해석 불가능한 숫자다.

**(c) 단위·방향이 통일되어 있지 않다.** `Performance.unit`의 실제 사용 분포:

```
32× ""              6× '0 to 1'          1× 'precision_drop'
 8× '%'             7× 'distance'        1× 'score'
 6× '-1 to 1'
```

`'distance'`는 낮을수록 좋고 `'%'`는 높을수록 좋은데 **그 방향을 나타내는 필드가 없다.** `'-1 to 1'`과 `'0 to 1'`은 같은 척도인 것도 있고 아닌 것도 있다. `""`(32건)는 아예 미지정이다.

이 상태로는 대시보드가 지표들을 나란히 놓을 수 없고, 종합 점수를 낼 수도 없고, "이번 실행이 저번보다 나아졌나"를 자동 판정할 수도 없다.

### 7.3 아키텍처가 아직 활용하지 못한 자산

RAGANG의 진짜 차별점은 **파이프라인 구조를 안다**는 것이다. `State.snapshots`에는 이미 모듈별·실행회차별 `Packet`(출력 + 성능 + 실행시간)이 다 쌓여 있다. 그런데 이걸로 하는 일이 `print_eval()`로 나열하는 것뿐이다.

여기서 나올 수 있는데 아직 없는 것들:
- "쿼리 200건 중 `ret` 모듈의 GECE가 하위 20%인 47건에서 최종 답변 품질도 하위권 → 병목은 검색기"
- "루프 그래프에서 평균 2.3회 재검색, 3회 이상 도는 쿼리는 대부분 실패"
- 모듈별 지연·비용 회계
- flow A vs flow B의 쿼리별 승패 비교

**경쟁 도구가 구조적으로 할 수 없는 일**이 이미 데이터로는 준비되어 있다.

---

## 8. 발전 방향

### Phase 0 — 지혈 (2~3주): "설치하면 문서대로 동작한다"

현재 v0.0.8b0이 PyPI에 올라가 있으므로 최우선이다.

| 순 | 작업 | 근거 |
|---|---|---|
| 1 | `Linker` 인스턴스 단위 연산자 판정으로 수정 | P0-1 — 핵심 유즈케이스 차단 |
| 2 | 빌트인 메트릭 3종 생성자 인자 수정 | P0-3 |
| 3 | `--no-save` 플래그 수정 | P0-4 — 문서와 정반대 |
| 4 | `to_dict()` / `api_adapter` import 수정 | P0-5, P0-2 |
| 5 | **테스트 하네스 도입** — `FakeLLMAdapter` / `FakeEmbeddingAdapter` + usage 4종 골든 테스트 | P3-1 |
| 6 | 빌트인 메트릭 전수 스모크 테스트 (문서 0/1/N건, 어댑터 에러, 빈 응답) | P1-2·3·4·5 를 한 번에 잡는다 |
| 7 | `0.0.0.0` 바인딩 · 경로 탈출 수정 | P2-2, P2-3 |
| 8 | 루트 README 재작성 (설치·개념·CLI 레퍼런스) | P3-28 — 신규 사용자의 첫 화면 |

**완료 판정:** `pip install ragang` → `ragang init demo` → `ragang query-gen` → `ragang run` → `ragang show` 전 과정이 README대로 끊김 없이 흐른다.

---

### Phase 1 — 신뢰 (1~2개월): "결과를 믿을 수 있다"

#### 1.1 메트릭 계약을 코드로 강제한다

지금은 "관례"라서 6개 파일이 6가지로 해석했다. 타입으로 못박는다.

```python
# ragang/core/bases/datas/performance.py
@dataclass(frozen=True)
class Performance:
    metric: str
    score: float | None
    status: Literal['ok', 'skipped', 'error'] = 'ok'
    unit: str = ''
    value_range: tuple[float, float] | None = None
    higher_is_better: bool = True          # ← 대시보드 종합·회귀 판정의 전제
    detail: str | None = None              # 실패 사유, judge 근거 등

    def to_dict(self) -> dict:             # 맹글링 없는 명시적 스키마
        ...
```

```python
# ragang/core/bases/abstracts/base_metric.py
class BaseMetric(ABC):
    name: ClassVar[str]
    unit: ClassVar[str]
    value_range: ClassVar[tuple[float, float] | None]
    higher_is_better: ClassVar[bool]

    def __init__(self, param_src: list[str], *,
                 llm_adapter: BaseLLMAdapter | None = None,
                 embedding_adapter: BaseEmbeddingAdapter | None = None):
        ...   # 어댑터는 keyword-only → P0-3 부류가 구조적으로 불가능해진다

    @abstractmethod
    async def evaluate(self, *args, **kwargs) -> Performance: ...
```

- 어댑터를 **keyword-only**로 만들면 P0-3 같은 위치 인자 실수가 컴파일 단계에서 막힌다
- `higher_is_better` / `value_range`가 있어야 §7.2(c)가 해결되고 대시보드가 지표를 통합할 수 있다
- `status`가 있어야 "평가 실패"와 "점수 0"이 구분된다 (지금은 NaN이나 0.0으로 뭉개진다)

#### 1.2 어댑터 반환을 타입으로

```python
@dataclass(frozen=True)
class LLMResponse:
    text: str | None
    raw: dict | None = None
    error: str | None = None
    usage: TokenUsage | None = None        # 비용 회계의 기반

    @property
    def ok(self) -> bool: return self.error is None
```

dict + `KeyError` 패턴(P1-4)이 구조적으로 사라진다. `usage`를 실으면 Phase 2의 비용 리포트가 공짜로 따라온다.

#### 1.3 동기/비동기 경계 정리

- `BaseMetric.evaluate`를 `async def`로 전환 → `__eval`도 async로
- 어댑터에서 `requests`를 걷어내고 `httpx`로 단일화, 전 경로에 timeout·재시도·백오프
- 어댑터가 공유 `AsyncClient`를 보유해 connection pooling 확보 (P3-25)
- 사용자가 동기 메트릭을 짜도 안전하도록 엔진에서 `asyncio.to_thread` 폴백 제공

→ P1-1(2.7s → 0.6s), P2-5, P3-25가 함께 해결된다.

#### 1.4 인덱싱을 평가에서 분리

```
ragang index                    # 코퍼스 → 청킹 → 임베딩 → 벡터DB (명시적, 1회)
ragang index --rebuild          # 강제 재구축
ragang run                      # 기존 인덱스에 붙어서 평가만
```

- `containers()`에서 부작용(drop + 재임베딩)을 제거 (P2-1)
- 문서 로더를 하나로 통합 — PDF/TXT/MD 지원, 청킹 정책은 설정으로 (P1-14, P3-22)
- **인덱싱과 쿼리 생성이 같은 청크 집합을 공유**하게 만들면 `Query.reference`의 chunk_idx가 비로소 의미를 갖는다 → "생성된 질문이 참조한 청크를 검색기가 실제로 가져왔는가"라는 **준-gold 지표**가 생긴다. 이건 지금 아무도 안 하는 강력한 카드다

#### 1.5 설정 체계 정리

```python
# settings.py
API_KEY = os.environ.get("RAGANG_API_KEY", "")   # 환경변수 우선
```

- 사용자 프로젝트 루트 기준 경로 해석 (P2-12)
- `load_user_config()` 결과 캐싱 (P3-23)
- `ragang init`이 `.gitignore`도 생성 (P2-11)

#### 1.6 견고성

- `asyncio.gather(return_exceptions=True)`로 전환 + 실패한 쿼리를 결과에 `status='error'`로 기록 (P3-6). **쿼리 400건 중 3건이 실패해도 397건은 저장되어야 한다**
- `Status`의 그래프 순회를 `visited` 집합 + BFS로 재작성 (P1-10)
- 루프 그래프 중복 파라미터 처리를 실제 로직으로 구현하거나, 미지원으로 명시 (P1-9)

---

### Phase 2 — 차별화 (3~6개월): "이 도구여야만 하는 이유"

#### 2.1 메트릭 타당성 검증 — 최우선 연구 과제

**No-gold 도구의 신뢰는 gold로 산다.** 공개 벤치마크(MS MARCO, HotpotQA, KILT, 한국어는 KorQuAD/AI-Hub)에서:

1. gold 기반 지표(정답 EM/F1, nDCG@k)와 RAGANG의 각 no-gold 지표 간 **상관계수**를 측정
2. 지표 간 **상호 상관 행렬**을 만들어 §7.2(a)의 중복을 정량화 → 상관 0.9 이상인 것들은 통합하거나 대표 하나만 남긴다
3. 결과를 `docs/metric-validity.md`에 공개

이 문서 하나가 **README 100줄보다 강력한 채택 근거**가 된다. 동시에 "20개 지표"를 "검증된 5개 지표"로 줄이는 근거도 된다 — 그게 오히려 신뢰를 높인다.

#### 2.2 진단 리포트 — 아키텍처 자산의 현금화

§7.3에서 지적한, 데이터는 있는데 안 쓰는 부분.

```
$ ragang report -F sample_rag

Flow: sample_rag  (쿼리 200건)
────────────────────────────────────────────────────────
병목 추정: ret (검색)
  · ret.GECE 하위 20%(40건)에서 e2e AQS가 평균 0.31 낮음 (p<0.01)
  · ret.ret_docs 가 비어 있던 쿼리 12건 → 전부 최종 실패
  · 제안: top_k 3 → 5, 또는 청크 크기 재조정

모듈별 비용/지연
  ret     : 평균 142ms   임베딩 호출 200회   $0.02
  output  : 평균 2,340ms LLM 호출 200회      $1.84   ← 지연의 94%

쿼리 유형별 성능 (query-gen 메타데이터 활용)
  simple_search : AQS 0.82   complex_multi : AQS 0.51  ← 멀티홉 취약
```

`query-gen`이 이미 `type`(7종)과 `reference`(청크 인덱스)를 붙여 저장하고 있다. **쿼리 유형별 성능 분해**는 지금 데이터로 바로 가능한데 안 하고 있는 기능이다.

#### 2.3 Flow 비교와 회귀 추적

히스토리는 이미 쌓고 있다. 여기에:

```
$ ragang compare -F baseline -F reranked
$ ragang run --baseline <ts>          # 회귀 감지, 임계 이하면 exit 1 (CI 연동)
```

- 쿼리 단위 승/패/무 집계 + 유의성 검정
- `higher_is_better`(Phase 1.1)가 있어야 자동 판정이 가능하다

#### 2.4 LLM Judge의 분산 관리

LLM-as-judge는 같은 입력에 다른 점수를 낸다. 지금은 1회 호출 결과를 그대로 쓴다.

- n회 샘플링 + 중앙값 + 신뢰구간 → `Performance.detail`에 분산 기록
- self-consistency 체크(judge끼리 불일치하면 `status='uncertain'`)
- judge 모델을 설정으로 분리(평가 대상 LLM과 judge LLM이 같으면 self-preference 편향)

#### 2.5 생태계

- 엔트리포인트 기반 플러그인 (`ragang.metrics`, `ragang.adapters` 그룹) — 서드파티 확장
- 벡터DB 어댑터 확대: Qdrant, Chroma, pgvector, Weaviate (현재 Milvus 전용)
- LangChain/LlamaIndex 파이프라인 임포터 — 기존 사용자의 마이그레이션 비용 제거
- 프론트엔드 소스를 저장소에 포함하고 WS 엔드포인트를 런타임 주입으로 (P3-29)

---

## 9. 실행 체크리스트

### Phase 0 (2~3주)

- [ ] P0-1 `Linker` 인스턴스 단위 연산자 판정 — [linker.py:12-19](ragang/core/bases/datas/linker.py#L12-L19)
- [ ] P0-2 `LocalLLMAdapter` 이름 정합 — [api_adapter.py:3](ragang/adapters/api_adapter.py#L3)
- [ ] P0-3 메트릭 3종 `super().__init__(param_src, ...)` 수정
- [ ] P0-4 `--no-save` → `store_true` + `dest='no_save'` — [entry.py:28](ragang/cli_script/entry.py#L28)
- [ ] P0-5 `to_dict()` None 가드 — [base_module.py:28](ragang/core/bases/abstracts/base_module.py#L28)
- [ ] P1-5 claim 0건 ZeroDivision 가드 (2곳)
- [ ] P1-4 `response["text"]` → `.get()` + 실패 시 `_eval=False` (6곳)
- [ ] P1-3 top-k 메트릭 문서 1건 가드
- [ ] P1-2 `MutualInformation_KSG` 배포 제외 또는 재구현
- [ ] P2-2 WS `file_name` 경로 봉쇄 — [runner.py:126](ragang/core/network/runner.py#L126)
- [ ] P2-3 HTTP 서버 `host` 바인딩 — [show/main.py:31](ragang/cli_script/show/main.py#L31)
- [ ] P2-9 `mkdir(parents=True, exist_ok=True)` — [init/main.py:19](ragang/cli_script/init/main.py#L19)
- [ ] pytest + Fake 어댑터 하네스, usage 4종 골든 테스트
- [ ] 빌트인 메트릭 전수 스모크 테스트 (0/1/N건 · 에러 응답 · 빈 응답)
- [ ] 루트 README 재작성
- [ ] `.gitignore`에 `.DS_Store` 추가, `ragang/web/.DS_Store` 제거
- [ ] `pyproject.toml`에서 `ragang.usage.*` 배포 제외

### Phase 1 (1~2개월)

- [ ] `Performance` dataclass 재설계 (`status` / `higher_is_better` / `value_range` / `to_dict`)
- [ ] `BaseMetric` 계약 재정의 (async · keyword-only 어댑터 · ClassVar 메타데이터)
- [ ] `BaseBuiltinMetric` 6중 복제 통합
- [ ] `LLMResponse` / `EmbeddingResponse` 타입 도입
- [ ] `requests` → `httpx` 단일화, timeout·재시도·백오프, 공유 클라이언트
- [ ] `asyncio.gather(return_exceptions=True)` + 쿼리 단위 실패 격리
- [ ] `ragang index` 명령 분리, `containers()`에서 부작용 제거
- [ ] 문서 로더 통합 (PDF/TXT/MD), 청킹 정책 단일화
- [ ] `Status` 그래프 순회 BFS + `visited` 재작성
- [ ] 설정 체계 (환경변수 우선, 프로젝트 루트 기준, 캐싱)
- [ ] `Orchestrator`의 Gemini 하드코딩 제거
- [ ] e2e 메트릭 시그니처 규약 정리 (또는 n-sampling 기능 추가)

### Phase 2 (3~6개월)

- [ ] 메트릭 타당성 검증 실험 + `docs/metric-validity.md` 공개
- [ ] 지표 간 상관 분석 → 중복 지표 통합·정리
- [ ] `ragang report` — 병목 진단, 쿼리 유형별 분해, 비용/지연 회계
- [ ] `ragang compare` / `--baseline` 회귀 감지 (CI 연동)
- [ ] LLM judge n-sampling + 신뢰구간 + judge 모델 분리
- [ ] 플러그인 엔트리포인트 (metrics / adapters)
- [ ] 벡터DB 어댑터 확대 (Qdrant, Chroma, pgvector)
- [ ] 프론트엔드 소스 편입 + WS 엔드포인트 런타임 주입

---

## 10. 맺음말

RAGANG은 **좋은 아이디어 위에 서 있다.** "파이프라인을 그래프로 선언하면 모듈 경계마다 평가 지점이 생기고, 정답 없이도 어느 단계가 병목인지 짚어준다" — 이건 RAGAS도 TruLens도 구조적으로 못 하는 일이다. 코어 엔진은 분기·병합 그래프를 실제로 실행해내며 이 약속의 절반을 이미 지키고 있다.

나머지 절반이 비어 있다. 평가 로직이 검증되지 않았고, 지표가 무엇을 재는지에 대한 근거가 없으며, 외부 API가 한 번만 흔들려도 배치 전체가 무너진다. **평가 도구가 자기 자신을 평가하지 않은 상태**다.

우선순위는 명확하다.

1. **Phase 0** — 문서대로 동작하게 만들고 테스트를 심는다. 이건 2~3주 작업이고, 지금 PyPI에 배포된 상태라 시급하다.
2. **Phase 1** — 메트릭 계약을 타입으로 못박는다. P0/P1 결함의 대부분은 개별 실수가 아니라 *계약이 코드로 강제되지 않아서* 생긴 것이므로, 계약을 세우면 같은 부류가 재발하지 않는다.
3. **Phase 2 §2.1(메트릭 타당성 검증)** — 이게 이 프로젝트의 승부처다. "No Gold"를 표방하는 도구가 자기 지표의 타당성을 gold로 입증하지 않으면, 아무리 많은 지표를 제공해도 채택되지 않는다. 반대로 이 문서 하나가 나오면 기능이 절반이어도 쓰인다.

기능을 더 늘리는 것보다, **있는 것을 믿을 수 있게 만드는 데** 다음 분기를 쓰기를 권한다.

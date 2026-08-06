# RAGANG 이슈 정리

대상 커밋: `cbfac8a` (v0.0.8b0)

코어 엔진(`base_engine.py`, `base_container.py`)은 정상 동작하며 linear/merge 그래프의 종단 실행을 확인했다. 확인된 결함 41건 중 상당수가 `metrics/builtin/`에 집중되어 있으며, 저장소 전체에 테스트 파일이 없다.

**진행 상황:** 1.1 전체 5건, 1.2 중 2건, 1.3 중 5건, 1.5 중 2건 해결 완료(총 14건). 성능 관련 항목(1.3-5, 1.3-6)과 값 오류 항목은 미착수.

상세 근거와 재현 절차는 저장소의 `REVIEW.md`에 기록했다. 아래 표의 위치는 `ragang/` 패키지 기준 상대 경로다.

---

# 1. 문제 보고

## 1.1 기능 동작 불가 — 해결 완료

문서에 기술된 기능이 실행되지 않거나 반대로 동작한다. 5건 모두 실행으로 재현했으며, 구조 변경 없이 최소 수정으로 처리했다. 8개 파일 28줄 추가 / 15줄 삭제.

| # | 항목 | 위치 | 증상 | 해결 |
|---|---|---|---|---|
| 1 | `Linker`가 클래스 속성을 영구 변경 | `core/bases/datas/linker.py:12-19` | AND 연산자를 1회 사용하면 OR 연산자가 프로세스 전역에서 비활성화된다. `manager.py`에 두 연산자를 쓰는 flow를 동시에 정의할 수 없다 | 클래스 속성 재할당(`Linker.__or__ = ...`)을 제거하고 `is_and` 인스턴스 필드를 추가. 두 피연산자의 상태를 검사해 혼용을 판정하도록 변경. 연산자 혼용 차단 기능 자체는 유지 |
| 2 | 미정의 클래스 import | `adapters/api_adapter.py:3` | `LocalLLMAdapter`가 존재하지 않는다(실제 명칭 `OllamaLocalLLMAdapter`). 모듈 import 시점에 ImportError | import와 생성부 2개소의 참조를 `OllamaLocalLLMAdapter`로 정정. 설정의 `provider: "Local"` 키는 유지 |
| 3 | 메트릭 3종의 생성자 인자 오류 | `metrics/builtin/retriever/non_llm_based.py:284`, `retriever/llm_based.py:83`, `generator/llm_based.py:544` | `super().__init__(llm_adapter, ...)` 호출로 `param_src` 위치에 어댑터가 전달된다. `PrecisionMetric`, `RandomDocumentInjectionEffect`, `A2RHybridFaithfulnessMetric` 인스턴스 생성 불가 | 각 클래스에 `param_src`를 첫 위치 인자로 추가하고 `super().__init__(param_src, llm_adapter, embedding_adapter)`로 전달. 나머지 인자의 순서와 기본값은 유지 |
| 4 | `--no-save` 플래그 미동작 | `cli_script/entry.py:28` | `store_false`와 `default=False`의 조합으로 값이 항상 `False`다. 결과가 항상 저장되며 README 기술과 반대로 동작한다 | `dest='save'`, `default=True`로 변경해 `--no-X` 플래그의 표준 argparse 형태로 정정. 호출부(`run/main.py:48`)를 `if not args.save`로 수정 |
| 5 | `to_dict()`가 `metrics=None`에서 예외 | `core/bases/abstracts/base_module.py:28` | starter 모듈은 관례적으로 `metrics=None`으로 생성한다. 직렬화 및 대시보드 경로에서 TypeError | 순회 대상을 `(self.metrics or [])`로 변경 |

1번 항목의 영향 범위가 가장 넓었다. `ragang run`은 `-F` 생략 시 `manager.py`의 모든 flow를 실행하도록 설계되어 있으나 해당 결함으로 동작하지 않았고, `usage/` 예제 4종도 상호 import가 불가능했다. 수정 후 `&`와 `|`를 각각 쓰는 flow 3개를 한 `FlowEngine`에 등록해 동시 실행되는 것을 확인했다.

**검증 결과** — 항목별 확인 13건이 수정 전 2/13에서 수정 후 13/13으로 전환됐다. 통과한 2건은 기존 정상 동작(연산자 혼용 차단, 의존관계 산출)의 회귀 확인용이다. 회귀 검사로 `usage/` 예제 4종 동시 import, linear·merge·conditional·loop 그래프 종단 실행, 빌트인 메트릭 6개 모듈 전수 import, `compileall`을 모두 통과했다.

## 1.2 잘못된 평가 결과

예외 없이 부정확한 값이 산출된다. 정상적으로 점수가 반환되므로 사용자가 오류를 인지하기 어렵다. 이 중 실행 오류를 동반하는 2건을 처리했다.

| # | 항목 | 위치 | 증상 | 해결 |
|---|---|---|---|---|
| 1 | `MutualInformation_KSG` 산출식 오류 | `metrics/builtin/generator/non_llm_based.py:145` | `dist_x = np.max(np.abs(gen_embedding - gen_embedding))`이 항상 0이다. x-주변부 항이 상수로 고정되어 상호정보량을 추정하지 못한다. 표준 KSG는 digamma를 사용하나 `np.log`를 사용한다. 추가로 `distances[k-1]` 인덱싱이 **템플릿 기본값(top_k=3, k=3)에서 100% IndexError** | **부분 해결(크래시만).** 이웃 수는 최대 N-1이므로 `k_eff = min(k, N-1)`로 k를 검색 결과 수에 맞춰 축소, 문서 1건 이하는 미평가. `log_k`도 `k_eff` 기준. **`dist_x` 산출식 오류는 남아 있어 산출값은 여전히 유효한 상호정보량이 아니다** |
| 2 | e2e 메트릭 시그니처와 엔진 규약 불일치 | `metrics/builtin/e2e/non_llm_based.py:56`, `:98` | 엔진은 `evaluate(query, gen: str)`으로 호출하나 메트릭은 `gens: list[str]`을 기대한다. 문자열 길이가 개수로 계산되고 문자 조각이 임베딩된다 | **해결.** str 입력을 `[str]`로 정규화하고, 답변 2건 미만이면 `Performance(_eval=False)`. 날조된 점수(0.757 등) 대신 "Not evaluated!"로 표기된다. 기존의 `len(gens)<2 → 1.0` 분기도 상수 1.0이 실제 점수로 읽히므로 동일 처리. 반복 실행 기능이 생기면 그대로 동작 |
| 3 | claim 판정 중복 가산 및 누적 점수 초기화 | `metrics/builtin/generator/llm_based.py:121-137`, `:406-423` | 판정 라인 발견 후 `break`가 없어 응답에 판정이 2회 등장하면 1개 claim이 2점을 받는다. 파싱 실패 시 `score = 0.0`이 이전 claim 결과 전체를 폐기한다 | — |
| 4 | 인덱싱 대상과 쿼리 생성 대상 불일치 | `templates/init_template/config/load_adapters.py:46-51`, `core/utils/query_generator/document_loader.py:141` | 인덱싱은 `.txt`를 500자 단위로, 쿼리 생성은 `.pdf`를 5문장 단위로 처리한다. 평가 대상 문서와 질문 생성 문서가 일치하지 않는다 | — |
| 5 | 실행마다 인덱스 재구축으로 비교 불가 | `templates/init_template/config/load_adapters.py:12-20` | `containers()`가 `create_engine()` 호출마다 실행되어 컬렉션을 drop 후 전량 재임베딩한다. 실행 시점마다 인덱스가 달라지며 임베딩 비용이 실행 횟수에 비례한다 | — |
| 6 | 루프 그래프 중복 파라미터 처리 무효 | `core/bases/abstracts/base_engine.py:174-179` | 좌변과 우변이 동일 객체의 동일 키인 자기 대입이다. 루프 복귀 시 최신값 반영 로직이 동작하지 않는다 | — |
| 7 | `MilvusAdapter`가 설정 파일의 host/port 폐기 | `adapters/milvus_adapter.py:55-60` | `super().__init__(host, port, alias)`가 설정에서 읽은 값을 생성자 기본값으로 덮어쓴다. 원격 Milvus 지정이 무시된다 | — |

## 1.3 실행 중단 및 성능 저하 — 실행 중단 5건 해결

평가 도중 예외가 발생해 결과를 얻지 못하거나 처리량이 저하된다. 빌트인 메트릭 전 클래스를 6가지 경계 입력(정상/문서1건/문서0건/LLM오류응답/LLM형식이탈/임베딩실패)으로 180회 호출해 조사한 결과 **런타임 오류 25회**가 확인됐고, 수정 후 **0회**가 됐다. 성능 항목(5, 6)은 이번 범위에서 제외했다.

| # | 항목 | 위치 | 증상 | 해결 |
|---|---|---|---|---|
| 1 | 어댑터 오류 응답 시 KeyError | 메트릭 6개소, `templates/init_template/modules/impls.py:73` | 어댑터는 실패 시 `{"error": ...}`를 반환하나 `response["text"]`를 무조건 인덱싱한다. `gather(return_exceptions=False)`와 결합되어 400건 배치 중 1회의 rate-limit으로 전체가 중단되고 완료분도 저장되지 않는다 | **해결.** ① LLM 5개 메트릭 6개 호출 지점에 `if "error" in response or not response.get("text"): return Performance(_eval=False)` 추가(`retriever/llm_based.py:109`의 기존 패턴 적용). ② 임베딩 실패 시 `np.array([])`를 `[0]`으로 인덱싱해 IndexError를 내던 13개 메트릭에 `.size == 0` 가드 추가. `GECE`·`ECS`는 가드가 이미 있었으나 인덱싱이 먼저 실행돼 도달 못 했으므로 순서만 교정. ③ `SingleCall`은 `response_text`를 try 진입 전에 초기화해 except 블록의 UnboundLocalError 제거 |
| 2 | claim 0건 시 ZeroDivisionError | `metrics/builtin/generator/llm_based.py:137`, `:423` | LLM이 번호 형식으로 응답하지 않으면 claim 리스트가 비고 `score / len(claim_list)`에서 예외가 발생한다 | **해결.** 나눗셈 전 `if not claim_list: return Performance(_eval=False)` |
| 3 | top-k 메트릭이 문서 1건 입력에서 예외 | `metrics/builtin/generator/non_llm_based.py:231-233` | `max()` 인자가 빈 리스트가 되어 ValueError. `base_score` 산식이 비유계로 -10⁶ 규모 값이 가능하다 | **해결.** top-k 분할에 최소 2건이 필요하므로 문서 2건 미만이면 미평가. `PairwiseCosineSimilarityVariance`의 NaN 산출도 동일 처리 |
| 4 | `Status` 그래프 순회에 사이클 보호 부재 | `core/bases/datas/status.py:13-17`, `:37-43` | 방문 집합 없이 재귀하여 루프 그래프에서 RecursionError 가능. `find_loop_before_mid`는 첫 outgoing edge만 따라가 분기 그래프에서 오탐한다 | — (usage 예제로는 재현되지 않는 잠재 결함이라 범위 제외) |
| 5 | 동기 메트릭이 이벤트 루프를 점유 | `core/bases/abstracts/base_engine.py:151` | 8쿼리 기준 이론값 0.6초 대비 실측 2.70초. `Packet.x_time`에 타 코루틴의 대기 시간이 포함되어 성능 측정값이 오염된다 | — (성능, 범위 제외) |
| 6 | 동기 HTTP 호출에 timeout 미지정 | `adapters/` 6개소 | `requests` 기본 timeout은 무제한이다. 무응답 서버 1개가 배치 전체를 정지시킨다. 재시도·백오프도 없다 | — (범위 제외) |
| 7 | 배치 중 1건 실패가 전체를 중단 | `core/bases/abstracts/base_engine.py:260`, `:287`, `:323` | 쿼리 5건 중 1건이 실패하면 `invoke_batch`가 예외를 전파해 `run/main.py`가 `print_eval()`·`update_history()`에 도달하지 못한다. 완료된 4건이 메모리에 있는데도 출력되지 않고 히스토리에도 남지 않는다 | **해결.** `gather` 3개소를 `return_exceptions=True`로 변경. 직후의 `if isinstance(res, Exception): continue`는 이미 작성돼 있었으나 도달 불가였으므로, 플래그만 바꿔 작성자가 의도한 동작을 살렸다. 실패가 묻히지 않도록 `warnings.warn` 추가. **단, 살아남은 결과가 하나도 없으면 첫 예외를 다시 던진다** — 설정 오류는 모든 쿼리에서 실패하므로 격리 대상이 아니며, 빈 결과 대신 원인을 보고해야 한다 |
| 8 | 설정 오류 시 진단 메시지 부재 | `core/bases/abstracts/base_container.py:50`, `:62-67`, `templates/init_template/modules/impls.py` | starter 모듈 미지정 시 `AttributeError: 'NoneType' object has no attribute 'lazy_state'`. 중복 module id 메시지가 항상 `set()`. 템플릿 모듈은 벡터DB 실패 시 `TypeError: 'NoneType' object is not iterable`, LLM 실패 시 `KeyError: 'text'` | **해결.** ① starter가 0개면 `RagangStructureException`으로 안내(기존에 "여러 개"만 검증하던 비대칭 해소). ② 중복 id를 `ids.count(i) > 1`로 실제 산출. ③ 템플릿 모듈이 어댑터 실패를 감지해 원인과 조치를 담은 `RuntimeError`를 던지도록 변경 |

## 1.4 보안 및 정보 노출

WebSocket 서버에 인증이 없는 상태에서 파일 접근과 외부 노출이 제어되지 않는다.

| # | 항목 | 위치 | 증상 |
|---|---|---|---|
| 1 | WebSocket `file_name` 경로 탈출 | `core/network/runner.py:126` | 확장자만 검증한다. `../../../etc/hosts.txt` 및 절대 경로가 통과하며, 읽은 내용은 쿼리로 LLM에 전송된다 |
| 2 | 대시보드 HTTP 서버가 `0.0.0.0`에 바인딩 | `cli_script/show/main.py:31` | LAN 전체에 노출되나 안내 문구는 127.0.0.1이다. WS 서버는 정상적으로 로컬 바인딩된다 |
| 3 | 예외 traceback을 전체 구독자에게 브로드캐스트 | `core/network/runner.py:64-68` | 절대 경로, 사용자명, 내부 구조가 노출된다 |
| 4 | API 키 평문 저장 | `templates/init_template/settings.py:10` | 환경변수 대체 경로가 없고 `ragang init`이 `.gitignore`를 생성하지 않아 키가 커밋될 가능성이 높다 |

## 1.5 데이터 형식 및 운영 — 2건 해결

저장 포맷과 오류 처리 방식이 외부 도구 및 사용자 환경과 맞지 않는다.

| # | 항목 | 위치 | 증상 | 해결 |
|---|---|---|---|---|
| 1 | NaN 점수와 이름 맹글링 키가 히스토리에 기록 | `core/bases/datas/performance.py:7-10`, `core/utils/cli.py:31` | `{"_Performance__score": NaN}` 형태로 저장된다. 표준 JSON 파서로 읽을 수 없고 스키마가 Python 이름 맹글링 규칙에 종속된다 | **NaN 부분 해결.** `core/decorators/serializable.py`의 `__serialize`에 비유한 float를 `None`으로 바꾸는 분기 추가. 이 한 곳이 히스토리와 WebSocket 브로드캐스트 공통 경로이므로 양쪽이 함께 해결된다. `GECE`가 반환하던 `inf`도 동일 처리. **키 맹글링은 프론트엔드 계약이라 그대로 둠** |
| 2 | 어댑터 실패의 조용한 전파 | `adapters/embedding_adapter.py`, `adapters/milvus_adapter.py` | 실패 시 `np.array([])`, `None`을 반환하고 `connect()`는 예외를 삼킨다. 호출 지점과 다른 곳에서 예외가 표면화된다 | **부분 해결.** 어댑터 반환 계약은 그대로 두고, 빌트인 메트릭 호출부 전체에 가드를 넣어 크래시를 제거했다(1.3-1). 어댑터가 실패를 조용히 삼키는 것 자체와 템플릿 모듈의 `retrieve() → None` TypeError는 남아 있다 |
| 3 | `'gen'` 키가 예약어이나 미문서화 | `core/bases/datas/packet.py:16` | 중간 모듈이 `gen` 키를 반환하면 플로우가 경고 없이 종료된다. 예약어 검증 코드가 주석 처리되어 있다 | — |
| 4 | `load_user_containers`의 예외 통합 및 `sys.path` 미복원 | `core/utils/modules.py:11-27` | 프레임워크가 던진 안내 메시지가 일반 메시지로 대체된다. `sys.path` 미복원과 모듈 캐시로 한 프로세스에서 다중 프로젝트 로드가 불가능하다 | — |
| 5 | `ragang init a/b/c` 실패 | `cli_script/init/main.py:19` | `os.mkdir`가 중간 디렉터리를 생성하지 않아 FileNotFoundError | **해결.** `target_path.mkdir(parents=True, exist_ok=True)`로 교체 |

## 1.6 코드 품질 및 유지보수

동작에는 영향이 적으나 결함 재발과 유지보수 비용을 유발한다.

| # | 항목 | 위치 | 증상 |
|---|---|---|---|
| 1 | 테스트 파일 부재 | 저장소 전체 | 위 결함 대부분이 단위 테스트로 검출 가능한 유형이다. CI, lint, 타입 체크도 없다 |
| 2 | `BaseBuiltinMetric` 6개 파일 중복 정의 | `metrics/builtin/*/*.py` | 파일별로 예외 처리와 경계 조건 가드가 상이하다. 1.1-3, 1.2-3의 원인 |
| 3 | 도달 불가 분기 및 중복 코드 | `core/bases/abstracts/base_engine.py:261-266` 외 2개소, `core/utils/query_generator/query_generator.py:158-163` | `return_exceptions=False` 뒤의 예외 분기, 중복 except 블록, 결과 병합 로직 3중 복제 |
| 4 | 중복 module_id 메시지가 항상 공집합 | `core/bases/abstracts/base_container.py:50-52` | `u_ids.difference(set(ids))`는 정의상 공집합이다. 탐지는 되나 어느 id가 중복인지 알 수 없다 |
| 5 | 데드 코드 | `core/network/runner.py:37-49` | `cont.storage._on_module_status`를 설정하나 호출부가 없다. 상태 전송은 `SocketSender`가 별도 수행한다 |
| 6 | WS 토픽·필드 오타 | `core/network/socket_sender.py:9-12` | `module-statu`, `statu`가 프로토콜에 고정되어 있다 |
| 7 | 문자열 리터럴 콤마 누락 | `core/utils/query_generator/scenario_generator.py:56-57` | 암묵적 결합으로 `"비이성적인기만적인"` 단일 항목이 생성된다 |
| 8 | `Orchestrator`의 provider 하드코딩 | `core/utils/query_generator/orchestrator.py:39` | `GeminiAdapter`가 고정되어 `query-gen`을 다른 provider로 실행할 수 없다 |
| 9 | `load_user_config()` 중복 호출 | orchestrator, query_generator, content_analyzer | `settings.py`가 매번 재실행된다 |
| 10 | 루프 내 `asyncio.run()` 호출 | `core/utils/query_generator/content_analyzer.py:105`, `:116` | 문서당 2회 이벤트 루프를 생성·파괴한다. 실행 중인 루프 내에서는 호출이 불가능하다 |
| 11 | 예제 코드가 배포 휠에 포함 | `pyproject.toml` | `ragang.usage.*` 13개 패키지가 설치본에 포함된다 |
| 12 | 루트 README가 템플릿용 문서 | `README.md` | 패키지 소개, 설치법, API 레퍼런스 없이 PyPI 랜딩 페이지로 노출된다 |
| 13 | 프론트엔드 소스 부재 | `web/` | 빌드 산출물만 커밋되어 있고 `ws://127.0.0.1:8081`이 하드코딩되어 포트 변경이 불가능하다 |
| 14 | docker-compose 볼륨 주석 처리 | `templates/init_template/config/docker-compose.yml` | 컨테이너 제거 시 인덱스가 소실된다. `version: '3.5'`는 폐기된 키다 |
| 15 | 불필요 파일 | 루트 `__init__.py`, `web/.DS_Store` | 저장소 루트는 패키지가 아니다 |

---

# 2. 개선 계획

## 2.1 메트릭 계약 정립

1.1과 1.2의 상당수는 개별 구현 오류가 아니라 공통 계약이 코드로 강제되지 않은 결과다. 타입으로 계약을 명시하면 동일 유형의 재발을 차단할 수 있다.

```python
@dataclass(frozen=True)
class Performance:
    metric: str
    score: float | None
    status: Literal['ok', 'skipped', 'error'] = 'ok'   # 평가 실패와 점수 0을 구분
    unit: str = ''
    value_range: tuple[float, float] | None = None
    higher_is_better: bool = True                       # 지표 통합 및 회귀 판정의 전제
    detail: str | None = None

class BaseMetric(ABC):
    def __init__(self, param_src: list[str], *,          # 어댑터를 keyword-only 로 지정
                 llm_adapter=None, embedding_adapter=None): ...
    @abstractmethod
    async def evaluate(self, *args, **kwargs) -> Performance: ...
```

어댑터를 keyword-only로 지정하면 1.1-3 유형의 오류가 발생하지 않는다. `higher_is_better`와 `value_range`는 후속 기능의 전제 조건이다. 현재 `unit` 실사용 분포는 `""` 32건, `'%'` 8건, `'distance'` 7건, `'-1 to 1'` 7건, `'0 to 1'` 6건, 기타 2건으로, 값이 클수록 좋은 지표인지 판별할 방법이 없어 지표 통합, 종합 점수 산출, 회귀 자동 판정이 불가능하다.

어댑터 반환값도 dict 대신 타입으로 정의한다.

```python
@dataclass(frozen=True)
class LLMResponse:
    text: str | None
    error: str | None = None
    usage: TokenUsage | None = None   # 비용 집계 기반
    @property
    def ok(self) -> bool: return self.error is None
```

## 2.2 메트릭 타당성 검증

no-gold 방식 평가 도구는 지표의 타당성 근거가 채택의 전제 조건이다. 현재 저장소에 해당 검증 자료가 없다.

- 공개 벤치마크(MS MARCO, HotpotQA, 한국어는 KorQuAD·AI-Hub)에서 gold 기반 지표(EM/F1, nDCG@k)와 각 no-gold 지표의 상관계수를 측정한다.
- 지표 간 상관 행렬을 산출한다. AQS, ACS, ACSV, PCSV, RDA, RMAS, GECE, ECS 등 12개 이상이 동일 임베딩 공간의 코사인 유사도 변형이므로 상호 상관이 높을 가능성이 있다. 상관이 높은 지표는 통합하거나 대표 지표만 유지한다.
- 결과를 `docs/metric-validity.md`로 공개한다.

## 2.3 신규 기능

### 2.3.1 `ragang index` 명령

인덱싱을 평가에서 분리한다.

```
ragang index              # 코퍼스 → 청킹 → 임베딩 → 벡터DB
ragang index --rebuild    # 강제 재구축
ragang run                # 기존 인덱스에 연결하여 평가만 수행
```

1.2-4와 1.2-5를 함께 해결한다. 인덱싱과 쿼리 생성이 동일 청크 집합을 공유하게 되면 `Query.reference`(참조 청크 인덱스)를 활용할 수 있다. 생성된 질문이 참조한 청크를 검색기가 실제로 반환했는지 확인하는 준-gold 지표를 구성할 수 있으며, 추가 데이터 수집 없이 구현 가능하다.

### 2.3.2 `ragang report` 진단 리포트

`State.snapshots`에는 모듈별·실행회차별 `Packet`(출력, 성능, 실행시간)이 저장되고, `query-gen`은 쿼리 유형 7종과 참조 청크 인덱스를 함께 기록한다. 현재 활용은 `print_eval()`의 나열이 전부다.

```
병목 추정: ret (검색)
  · ret.GECE 하위 20%(40건)에서 e2e AQS 평균 0.31 낮음 (p<0.01)
  · ret_docs 가 비어 있던 12건은 전부 최종 실패
모듈별 비용/지연: ret 142ms $0.02 / output 2,340ms $1.84 (지연의 94%)
쿼리 유형별: simple_search 0.82 / complex_multi 0.51
```

기존 도구(RAGAS, TruLens)는 파이프라인을 입출력 단위로 관측하므로 모듈 단위 분해가 불가능하다. RAGANG은 파이프라인 구조 정보를 보유하므로 구현 가능하다.

### 2.3.3 flow 비교 및 회귀 추적

```
ragang compare -F baseline -F reranked      # 쿼리 단위 승/패/무 집계 및 유의성 검정
ragang run --baseline <ts>                  # 임계값 미달 시 exit 1, CI 연동
```

2.1의 `higher_is_better` 필드가 선행되어야 한다.

### 2.3.4 LLM judge 분산 관리

LLM-as-judge는 동일 입력에 대해 상이한 점수를 산출하나 현재는 1회 호출 결과를 그대로 사용한다.

- n회 샘플링 후 중앙값 및 신뢰구간 산출, 분산을 `Performance.detail`에 기록
- judge 간 불일치 시 `status='uncertain'` 처리
- judge 모델과 평가 대상 모델 분리(self-preference 편향 방지)

### 2.3.5 동일 쿼리 반복 실행

1.2-2의 e2e 일관성 지표(`e2eCosineConsistencyMetric`, `e2eCovarianceConsistencyMetric`)는 답변 리스트를 전제로 설계되었으나 엔진에 반복 실행 기능이 없다. n회 실행 후 결과를 집계하는 옵션을 추가하면 두 지표를 정상 동작시킬 수 있다.

## 2.4 생태계 확장

- 엔트리포인트 기반 플러그인(`ragang.metrics`, `ragang.adapters` 그룹). 서드파티 메트릭·어댑터 확장 지원
- 벡터DB 어댑터 확대: Qdrant, Chroma, pgvector, Weaviate(현재 Milvus 전용)
- LangChain, LlamaIndex 파이프라인 임포터
- 프론트엔드 소스 편입 및 WS 엔드포인트 런타임 주입

## 2.5 단계별 계획

### 1단계: 기능 정상화 (2~3주)

v0.0.8b0이 PyPI에 배포된 상태이므로 우선순위가 높다.

- [x] 1.1 전체 5건 — 완료 (8개 파일, 검증 13/13 통과)
- [x] 실행 중단 항목: 1.3-1, 1.3-2, 1.3-3, 1.3-7, 1.3-8 — 완료 (10개 파일, 런타임 오류 25 → 0)
- [x] 1.2-2 e2e 시그니처, 1.5-1 NaN JSON, 1.5-5 init 경로 — 완료
- [~] 1.2-1 KSG — 크래시만 제거. 산출식 오류는 남아 있어 대체 또는 배포 제외 필요
- [ ] 1.2-3 claim 중복 가산
- [ ] 보안 항목: 1.4-1, 1.4-2
- [ ] 테스트 하네스 도입. Fake 어댑터 기반 usage 4종 골든 테스트, 빌트인 메트릭 전수 스모크 테스트(문서 0/1/N건, 오류 응답, 빈 응답)
- [ ] 루트 README 재작성 (1.6-12)

완료 기준: `pip install`, `init`, `query-gen`, `run`, `show` 전 과정이 README 기술대로 동작한다.

### 2단계: 신뢰성 확보 (1~2개월)

- [ ] 2.1 메트릭 계약 및 어댑터 반환 타입 정립, `BaseBuiltinMetric` 통합 (1.6-2)
- [ ] 메트릭 async 전환, `requests`에서 `httpx`로 단일화, timeout·재시도·클라이언트 공유 (1.3-5, 1.3-6)
- [ ] `gather(return_exceptions=True)` 전환 및 쿼리 단위 실패 격리 (1.3-1, 1.6-3)
- [ ] 2.3.1 `ragang index` 분리, 문서 로더·청킹 정책 통일 (1.2-4, 1.2-5)
- [ ] 설정 체계 정비: 환경변수 우선, 프로젝트 루트 기준 경로 해석, 캐싱 (1.4-4, 1.5-4, 1.6-9)
- [ ] 잔여 결함: 1.2-2, 1.2-6, 1.2-7, 1.3-4, 1.5 전체
- [ ] 1.6 품질 항목 일괄 정리

### 3단계: 기능 확장 (3~6개월)

- [ ] 2.2 메트릭 타당성 검증 및 지표 정리
- [ ] 2.3.2 `ragang report`
- [ ] 2.3.3 flow 비교 및 회귀 추적
- [ ] 2.3.4 LLM judge 분산 관리
- [ ] 2.3.5 반복 실행 기능
- [ ] 2.4 생태계 확장

---

# 3. 종합

파이프라인을 그래프로 선언하고 모듈 경계마다 평가 지점을 배치하는 설계는 기존 도구와 구분되는 접근이며 코어 엔진에 구현되어 있다. 미완성 영역은 평가 로직으로, 메트릭 구현이 검증되지 않았고 각 지표의 측정 대상에 대한 근거가 없으며 외부 API 오류 시 배치 전체가 중단된다.

우선순위는 1단계 기능 정상화, 2.1 메트릭 계약 정립, 2.2 타당성 검증 순이다. 기능 추가보다 기존 구현의 신뢰성 확보를 우선할 것을 제안한다.

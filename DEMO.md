# RAGANG 2026 데모

두 데모 모두 실제 RAGANG engine, history와 WebSocket을 사용한다. Primary Live
Demo는 실제 Milvus와 Ollama LLM을 사용하고, Offline Fallback Demo는 외부 서비스
장애 중에도 workflow를 재현한다.

어느 데모의 점수도 연구용 benchmark 또는 실제 judge 정확도의 증거로 해석하면
안 된다.

## 공통 설치와 검증

저장소 루트에서 Python 3.13 이상을 사용한다.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

`uv`를 사용한다면 `uv sync` 후 동일하게 `.venv/bin/python`을 사용할 수 있다.

# Primary Live Demo

이 경로는 다음 실제 흐름을 보여준다.

real documents
→ real Milvus retrieval
→ real Ollama generation
→ built-in RAGANG evaluation
→ evaluator health/provenance
→ diagnosis
→ baseline/candidate comparison
→ history/WebSocket/dashboard

검색 embedding은 Milvus와 LLM 통합을 다른 model 품질과 분리하기 위한 투명한
deterministic token embedding이다. 실제 Ollama embedding 또는 Gemini flow를
검증했다는 뜻은 아니다.

## 1. 서비스 준비

Docker daemon과 Ollama가 필요하다. 저장소 루트에서 Milvus를 시작한다.

```bash
docker compose -f ragang/templates/init_template/config/docker-compose.yml up -d
until curl -fsS http://127.0.0.1:9091/healthz >/dev/null; do sleep 1; done
ollama list
```

19530 port가 먼저 열려도 Milvus metadata service가 아직 준비되지 않을 수 있다.
위 health check를 통과한 뒤 실행하며, live example도 collection setup을 최대 90초
동안 재시도한다.

기본 model은 `llama3:latest`다. 이미 설치된 다른 generation model을 사용하려면
이름만 환경변수로 전달한다.

```bash
export RAGANG_OLLAMA_HOST=127.0.0.1:11434
export RAGANG_OLLAMA_MODEL=llama3:latest
```

credential은 필요하지 않다. Gemini template acceptance가 필요하면
`LIVE_ACCEPTANCE.md`의 `RAGANG_API_KEY` 절차를 별도로 따른다.

## 2. live baseline과 candidate

```bash
cd examples/live_ollama_milvus
RAGANG_LIVE_DEMO_MODE=noisy ../../.venv/bin/ragang run \
  -F live_ollama_milvus -Q custom/live.txt
sleep 1
RAGANG_LIVE_DEMO_MODE=focused ../../.venv/bin/ragang run \
  -F live_ollama_milvus -Q custom/live.txt
```

`ragang_live_demo`라는 전용 Milvus collection만 재생성한다. 다른 collection은
drop하거나 수정하지 않는다.

## 3. 정확한 run 비교

먼저 최근 두 run의 timestamp를 확인한다.

```bash
../../.venv/bin/ragang compare -F live_ollama_milvus --json
```

출력된 timestamp를 명시적으로 고정해 다시 비교한다.

```bash
../../.venv/bin/ragang compare -F live_ollama_milvus \
  --baseline <noisy_timestamp> --candidate <focused_timestamp>
```

확인 항목은 evaluator coverage, latency, 공통 evaluated metric delta, 서로 다른
retrieval mode로 인한 configuration fingerprint 경고다. 점수 하나만으로 candidate
승리를 선언하지 않는다.

## 4. live dashboard

```bash
RAGANG_LIVE_DEMO_MODE=focused ../../.venv/bin/ragang show \
  -F live_ollama_milvus
```

브라우저에서 `http://127.0.0.1:8080`을 열고 `BROWSER_ACCEPTANCE.md`를 수행한다.
서버는 loopback에만 바인딩된다.

이번 자동 acceptance에서 실제 Milvus insert 2건, 실제 Ollama generation,
built-in metric 3/3, evaluator coverage 100%, status event 6건, WebSocket result,
history 저장과 reconnect 복원을 확인했다.

## 5. live 서비스 정리

이번 리허설을 위해 서비스를 시작한 경우에만 저장소 루트에서 stop한다. `down -v`는
사용하지 않는다.

```bash
docker compose -f ragang/templates/init_template/config/docker-compose.yml stop
```

# Offline Fallback Demo

이 경로는 API key, 외부 LLM, Milvus 없이도 실제 문서 읽기, retrieval, generation,
metric, history, WebSocket과 dashboard 계약을 검증한다. frontend mock data를
사용하지 않는다.

token-overlap metric은 workflow 확인을 위한 설명 가능한 fixture이며 연구 성능
주장이 아니다.

## 1. 문서와 쿼리

```bash
cd examples/local_demo
```

- `datas/docs/01_ragang.txt`: 질문과 관련된 실제 입력 문서
- `datas/docs/02_distractor.txt`: 빵 굽기 관련 distractor 문서
- `datas/queries/custom/demo.txt`: 평가 query

## 2. baseline과 candidate

`noisy`는 관련도가 낮은 문서를, `focused`는 관련도가 높은 문서를 반환한다.

```bash
RAGANG_DEMO_MODE=noisy ../../.venv/bin/ragang run -F local_demo -Q custom/demo.txt
sleep 1
RAGANG_DEMO_MODE=focused ../../.venv/bin/ragang run -F local_demo -Q custom/demo.txt
```

최근 두 timestamp를 확인한 뒤 명시적으로 비교한다.

```bash
../../.venv/bin/ragang compare -F local_demo --json
../../.venv/bin/ragang compare -F local_demo \
  --baseline <noisy_timestamp> --candidate <focused_timestamp>
```

## 3. 반복 리허설과 history 안전

기본 권장 방식은 timestamp를 명시해 stale run과의 비교를 피하는 것이다.

완전히 빈 demo history가 필요하면 반드시 현재 경로가
`examples/local_demo`인지 확인하고, 삭제 대신 전용 history 파일을 archive한다.

```bash
pwd
mkdir -p history/archive
mv history/local_demo.json \
  "history/archive/local_demo.$(date +%Y%m%d%H%M%S).json"
```

파일이 없으면 `mv`를 생략한다. 다른 project 또는 사용자 history에는 이 절차를
사용하지 않는다.

## 4. valid zero와 not-evaluated

기본 noisy run의 query-context 0은 성공적으로 평가된 유효한 0점이다. 별도의
acceptance-only probe는 실제 engine history에 명시적 미평가를 추가한다.

```bash
RAGANG_DEMO_MODE=noisy RAGANG_DEMO_INCLUDE_NOT_EVALUATED=1 \
  ../../.venv/bin/ragang run -F local_demo -Q custom/demo.txt
```

`Unavailable evaluator probe`는 `Not evaluated`로 보여야 하고, 평균·분포·추세와
Overall Score에는 들어가면 안 된다. 이 probe는 default demo에는 포함되지 않는다.

## 5. empty retrieval 진단

```bash
RAGANG_DEMO_MODE=empty ../../.venv/bin/ragang run -F local_demo -Q custom/demo.txt
RAGANG_DEMO_MODE=empty ../../.venv/bin/ragang show -F local_demo
```

`retrieval.empty`는 observation, `answer_without_retrieved_evidence`는 확정 원인이
아닌 inference로 표시되어야 한다.

## 6. offline dashboard

```bash
RAGANG_DEMO_MODE=focused ../../.venv/bin/ragang show -F local_demo
```

Dashboard, Test Query, Run Queries, history 복원, evaluator coverage와 diagnostics는
`BROWSER_ACCEPTANCE.md`의 수동 checklist로 확인한다. 실제 browser 증거가 없으면
rendered-browser 상태는 `NOT EVALUATED`다.

# 프런트엔드 소스 검증

별도 `RAG-APP-UI` 저장소에서 다음을 실행한다.

```bash
npm ci
npm test
npm run typecheck
npm run build
```

production build는 연속 두 번 전체 파일 hash가 같아야 한다. 배포 파일은 source
build 전체를 `ragang/web/`에 동기화하고 exact frontend commit을
`FRONTEND_PROVENANCE.md`에 기록한다. minified bundle을 직접 편집하지 않는다.

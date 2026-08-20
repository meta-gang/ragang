# 실제 LLM·Milvus acceptance

기준일: 2026-08-20

## 판정

- 실제 지원 LLM adapter: **PASS** — `OllamaLocalLLMAdapter`, `llama3:latest`
- 실제 Milvus 검색 경로: **PASS** — Milvus 2.4.3, `localhost:19530`
- built-in metric/provenance/history/WebSocket: **PASS**
- credential 기반 Gemini template flow: **NOT EVALUATED** — 필요한 환경변수가 없음
- rendered browser: **NOT EVALUATED** — browser runtime이 제공되지 않음

검증은 실제 문서 2개를 별도 `ragang_acceptance_*` collection에 삽입하고,
Milvus 검색 → Ollama 생성 → built-in metric 3개 → evaluator provenance → history
저장 → WebSocket 전송 → 재연결 history 복원 순서로 실행했다. 테스트 collection은
삭제했고, 작업 전에 stopped였던 Milvus 관련 컨테이너도 stopped 상태로 되돌렸다.

## 저장소가 지원하는 adapter

- LLM: `OllamaLocalLLMAdapter`, `OpenAIAdapter`, `GeminiAdapter`
- embedding: `LocalEmbeddingAdapter`, `OpenAIEmbeddingAdapter`,
  `GeminiEmbeddingAdapter`
- vector database: `MilvusAdapter`

기본 init template은 `GeminiAdapter`, `GeminiEmbeddingAdapter`, Milvus와
`sample_rag` flow를 사용한다. credential 이름은 `RAGANG_API_KEY` 하나이며 값은
문서, history, provenance 또는 명령행에 기록하면 안 된다.

## 검증된 credential-free live flow

`examples/live_ollama_milvus`는 실제 Milvus와 실제 Ollama LLM을 사용한다. 검색
embedding은 외부 model 품질의 영향을 분리하기 위한 명시적 deterministic token
embedding이다. 따라서 이 예제는 통합 경로의 증거이지 embedding 품질 benchmark가
아니다.

필요 서비스:

- Docker daemon
- Milvus standalone, etcd, MinIO
- Ollama `127.0.0.1:11434`
- Ollama model `llama3:latest` 또는 `RAGANG_OLLAMA_MODEL`로 지정한 model

서비스 시작 예시:

```bash
docker compose -f ragang/templates/init_template/config/docker-compose.yml up -d
until curl -fsS http://127.0.0.1:9091/healthz >/dev/null; do sleep 1; done
ollama list
```

환경변수 이름만 사용한다.

```bash
export RAGANG_OLLAMA_HOST=127.0.0.1:11434
export RAGANG_OLLAMA_MODEL=llama3:latest
```

실행은 `DEMO.md`의 Primary Live Demo 절차를 따른다.

## 실제 검증 증거

- Milvus 실제 insert: 2 entities
- 실제 query: 1
- 실제 Ollama generation: 성공
- built-in metric: `CosineSimilarityMetric`, `AnswerContextSimilarity`,
  `AnswerQuerySimilarity`
- evaluator coverage: 3/3, 100%
- WebSocket topology: `starter → retrieval → generation`
- module status event: 6
- WebSocket result state: 1
- initial history run: 1
- query 후 reconnect history run: 2
- WebSocket error event: 0

## credential 기반 template 수동 절차

Gemini/Milvus 기본 template은 다음 환경에서만 검증한다.

```bash
export RAGANG_API_KEY='<securely injected value>'
ragang init /path/to/private-test-project
cd /path/to/private-test-project
docker compose -f config/docker-compose.yml up -d
ragang run -F sample_rag -Q custom/queries.txt
ragang show -F sample_rag
```

성공 증거는 실제 retrieved documents, Gemini generation, built-in metric의
`did_eval=true`, evaluator model/provenance, config fingerprint, history, WebSocket
result와 dashboard 표시다. 이 경로는 이번 환경에 `RAGANG_API_KEY`가 없어
`NOT EVALUATED`이며 성공으로 간주하지 않는다.

# Development guide

## 저장소 역할

- Backend/core repository: `ragang` package, CLI, history/WebSocket server, test, bundled web asset
- Frontend source repository: `RAG-APP-UI` React/TypeScript source
- `ragang/web/`: frontend source가 아니라 검증된 production build의 배포 사본

구조 설명은 [architecture overview](docs/architecture/overview.md), 평가 의미론은
[EVALUATION.md](EVALUATION.md)를 먼저 읽습니다.

## 환경

Python 3.13+ 환경에서 editable install을 권장합니다.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e .
```

Node dependency는 frontend lockfile을 기준으로 설치합니다.

```bash
cd ../RAG-APP-UI
npm ci
```

## 변경 절차

1. 재현 가능한 failing test 또는 명확한 계약 위반을 기록합니다.
2. Public/legacy serialization, valid zero, not-evaluated 의미론을 유지합니다.
3. Core 변경은 focused test 후 전체 backend suite를 실행합니다.
4. UI 변경은 source repository에서만 하고 test/typecheck/build를 모두 실행합니다.
5. Generated bundle은 [RELEASE.md](RELEASE.md) 절차로만 backend에 설치합니다.
6. `git status`, `git diff --check`, branch/upstream divergence를 확인합니다.

## 필수 검증

Backend:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q ragang tests
git diff --check
```

Frontend:

```bash
npm test -- --runInBand
npm run typecheck
npm run build
git diff --check
```

일반 regression test는 live API, paid model, Milvus를 요구하면 안 됩니다. Adapter failure,
judge parsing, graph cycle은 deterministic fake로 검증합니다.

## 구현 규칙

- `Performance.did_eval=True`인 score는 bool이 아닌 finite real number여야 합니다.
- 빈 집합의 평균/거리/순위처럼 수학적으로 정의되지 않은 입력은 `not evaluated`입니다.
- Metric 실패가 query 실행 전체를 실패시키지 않도록 engine 경계에서 격리합니다.
- Module 실행 실패는 기존처럼 호출자에게 예외를 전달하되 failed trace와 diagnosis를
  container storage에 먼저 보존합니다.
- Trace에는 input/output 값이 아니라 key 이름만 기록합니다.
- 이질적 metric의 score 평균, 자동 percent 변환, 방향을 무시한 “best/worst” 표현을
  만들지 않습니다.
- 관측 사실과 원인 추론을 같은 field나 문장으로 합치지 않습니다.

## 새 metric checklist

- 목적과 RAG stage가 기존 metric과 중복되지 않는가?
- 필요한 input과 `param_refs` 순서가 명확한가?
- 식, 단위, 범위, 높은/낮은 값의 방향이 문서화되었는가?
- Empty/insufficient input, adapter error, malformed output을 `not evaluated`로 처리하는가?
- 실제 0점 회귀 test가 있는가?
- Gold/reference가 필요하다면 optional임을 이름과 문서에서 명시했는가?
- Calibration, language/model sensitivity, sample-size limitation을 기록했는가?

## Security와 데이터 경계

Credential, prompt/document/query 원문, local path를 provenance나 failure message에 추가하지
않습니다. Runtime `State`에는 실제 query/output이 존재할 수 있으므로 history는 사용자
데이터로 취급합니다. WebSocket server는 loopback 기본값을 유지하고 외부 파일명을
신뢰하지 않습니다.

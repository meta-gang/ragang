# RAGANG 2026 재현 가능한 데모

이 데모는 API key, 외부 LLM, Milvus 없이도 실제 RAGANG 엔진·WebSocket·이력·대시보드를 검증한다. `examples/local_demo`의 두 문서를 런타임에 읽으며 프런트엔드 mock data를 사용하지 않는다.

데모 metric은 흐름 확인을 위한 설명 가능한 token-overlap metric이다. 연구용 품질 benchmark나 실제 judge 정확도의 증거로 해석하면 안 된다.

## 1. 설치

저장소 루트에서 Python 3.13 이상을 사용한다.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

`uv`를 사용한다면 `uv sync` 후 동일하게 `.venv/bin/python`을 사용할 수 있다.

## 2. 문서와 쿼리 확인

데모 프로젝트로 이동한다.

```bash
cd examples/local_demo
```

- `datas/docs/01_ragang.txt`: 질문과 관련된 실제 입력 문서
- `datas/docs/02_distractor.txt`: 빵 굽기 관련 distractor 문서
- `datas/queries/custom/demo.txt`: 평가 쿼리

## 3. Baseline 실행

`noisy` 모드는 의도적으로 관련도가 가장 낮은 문서를 반환한다.

```bash
RAGANG_DEMO_MODE=noisy ../../.venv/bin/ragang run -F local_demo -Q custom/demo.txt
```

출력에서 retrieval, generation, E2E metric이 실제로 계산되고 `history/local_demo.json`에 저장되는지 확인한다.

## 4. Candidate 실행

두 history timestamp가 분리되도록 1초 뒤 `focused` 모드를 실행한다.

```bash
sleep 1
RAGANG_DEMO_MODE=focused ../../.venv/bin/ragang run -F local_demo -Q custom/demo.txt
```

## 5. 비교

```bash
../../.venv/bin/ragang compare -F local_demo
```

확인 항목:

- baseline/candidate timestamp
- evaluator coverage
- 평균 latency
- 공통 evaluated metric의 score delta
- 서로 다른 공개 retrieval 설정으로 인한 configuration fingerprint 경고

구조화된 결과가 필요하면 `--json`을 추가한다. 특정 실행은 `--baseline <timestamp> --candidate <timestamp>`로 선택한다.

## 6. 실제 대시보드

candidate 설정으로 서버를 시작한다.

```bash
RAGANG_DEMO_MODE=focused ../../.venv/bin/ragang show -F local_demo
```

브라우저에서 `http://127.0.0.1:8080`을 연다. 서버는 로컬 loopback에만 바인딩되고 WebSocket은 `ws://127.0.0.1:8081`을 사용한다.

대시보드에서 다음을 확인한다.

1. 저장된 baseline/candidate history가 mock이 아닌 `history/local_demo.json`에서 표시된다.
2. Overall Score는 evaluated metric만 사용한다.
3. Evaluator Coverage가 실제 평가 성공 비율을 보여준다.
4. Evaluation Diagnostics가 관측 증거와 가능한 원인 추론을 구분한다.
5. Test Query에서 질문을 보내면 topology 상태가 바뀌고 새 결과가 이력에 저장된다.
6. 새로고침 후에도 history가 다시 로드된다.

## 7. 진단 실패 경로

검색 결과가 없는 실제 실행을 추가한다.

```bash
RAGANG_DEMO_MODE=empty ../../.venv/bin/ragang run -F local_demo -Q custom/demo.txt
RAGANG_DEMO_MODE=empty ../../.venv/bin/ragang show -F local_demo
```

대시보드에는 `retrieval.empty`가 관측 사실로, `answer_without_retrieved_evidence`가 확정 원인이 아닌 추론으로 표시되어야 한다. 안전 거절이 생성되었는지는 사용자가 답변과 함께 판단한다.

## 8. 프런트엔드 소스 개발 검증

별도 프런트엔드 저장소 `RAG-APP-UI`에서 다음을 실행한다.

```bash
npm ci
npm test
npm run typecheck
npm run build
```

배포 파일은 소스 빌드 전체를 `ragang/web/`에 동기화해야 한다. 해시가 붙은 JS나 minified bundle을 직접 편집하지 않는다.

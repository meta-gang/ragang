# 로컬 RAG 시작하기

기본 `offline` 프로파일은 외부 API, API 키, Milvus 없이 문서 검색·발췌·평가·이력·화면의 연결을 확인합니다. 답변 생성 모델의 성능 벤치마크가 아닙니다. 문서는 `datas/docs/*.txt`에서 읽고 메모리에만 인덱싱합니다. 기존 데이터베이스를 수정하지 않습니다.

```bash
ragang run -F sample_rag -Q custom/queries.txt
ragang show -F sample_rag
```

평가 성공률은 정답률이 아닙니다. 지표별 단위와 평가 여부를 확인하세요. 실패 질문도 이력에 저장되며 부분 실패가 있으면 CLI는 실패 상태로 종료합니다.

## 실제 로컬 모델 사용

Ollama와 모델을 폐쇄망에 미리 반입한 뒤 모델 서버를 실행합니다. 모델 다운로드는 평가 실행과 별개의 준비 단계입니다.

```bash
RAGANG_PROFILE=ollama RAGANG_LLM_MODEL=qwen2.5:3b RAGANG_EMBEDDING_MODEL=nomic-embed-text ragang run -F sample_rag -Q custom/queries.txt
RAGANG_PROFILE=ollama ragang show -F sample_rag
```

`RAGANG_OLLAMA_HOST`의 기본값은 `127.0.0.1:11434`이며 이 샘플은 loopback endpoint만 허용합니다. 다른 사내 서버는 endpoint·권한을 검토한 사용자 어댑터로 교체하세요.

## 자신의 RAG 연결

`manager.py`의 모듈을 실제 검색·생성 구현으로 교체하세요. 검색 출력은 `query`, `ret_docs: list[str]`, 생성 출력은 `gen: str`입니다. 중간 생성은 후속 모듈로 이어지며 최종 단계는 leaf 모듈 또는 `terminal=True`로 지정합니다. 지표의 입력 참조와 순서를 명시하세요.

Milvus의 기존 컬렉션은 평가 로딩 중 삭제·재생성·재삽입하지 않습니다. 수집과 평가를 별도 작업으로 유지하세요.

## 로컬 질문 생성

`settings.py`의 기본 질문 생성 제공자는 Ollama입니다. 모델 준비 후 실행합니다.

```bash
ragang query-gen -D datas/docs -Q generated.json
```

생성한 질문의 범위·난도·답변 가능성을 점검하세요. 외부 제공자는 사용자가 `LLM_PROVIDER`를 명시적으로 설정할 때만 사용합니다.

## 이력 보관

`history/`에는 질문·검색 문서·답변이 포함됩니다. 접근 권한과 보존 기간을 정하고 민감 자료를 Git에 추가하지 마세요. `--no-save`는 디스크 이력을 생략합니다.

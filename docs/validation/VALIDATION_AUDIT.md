# `main` → `validation` 독립 감사

분석 기준일: 2026-08-20

## 범위와 방법

기준 커밋은 `origin/main`의 `cbfac8a`, 검토 대상은
`origin/validation`의 `01e4c82`다. 로컬 `main` 포인터는 clone 당시
`87b74ca`에 머물러 있어 비교 기준으로 사용하지 않았다.
`ISSUE.md`와 `REVIEW.md`의 결론은 가설로 두고 다음을 독립 확인했다.

- 두 커밋 사이의 22개 변경 파일과 세 validation 커밋의 실제 diff 검토
- 네트워크 호출이 없는 fake LLM/embedding 및 임시 파일을 사용한 17개 동작
  재현
- 같은 하네스를 detached `main` worktree와 `validation` 양쪽에서 실행
- malformed judge 출력, embedding 실패, 소표본, 배치 일부 실패, 경로 경계,
  직렬화, CLI 플래그, 설정 진단을 포함한 경계 조건 확인

결과는 `main` 0/17, `validation` 16/17이었다. 이는 validation이 실제로
기준선보다 개선되었음을 보여주지만, 모든 보고서 문구나 평가 의미가 검증됐다는
뜻은 아니다.

## 확인됨

다음 변경은 기준선 실패와 validation 성공을 같은 입력으로 재현했다.

- `Linker`의 AND/OR 전역 오염 제거와 혼용 차단 유지
- 존재하지 않는 `LocalLLMAdapter` import 교정
- `PrecisionMetric`, `RandomDocumentInjectionEffect`,
  `A2RHybridFaithfulnessMetric`의 `param_src` 생성자 계약 복구
- `--no-save` 파싱 및 저장 분기 복구
- `metrics=None` 모듈 직렬화
- 대표 retriever/generator/e2e 메트릭의 embedding 실패 시 not-evaluated 처리
- top-k/쌍별/일관성 메트릭의 소표본 처리
- 번호 없는 claim의 0 나눗셈 방지와 마지막 판정만 사용하는 중복 가산 방지
- 일부 쿼리 실패 시 성공 결과 보존, 전부 실패하면 원인 재전파
- starter 부재와 중복 module id 진단
- NaN/무한대의 JSON `null` 직렬화
- Milvus 설정 host/port 보존
- 사용자 프로젝트 로드 시 안내 예외 보존
- 대시보드 HTTP 서버의 loopback 바인딩
- WebSocket 오류 payload에서 traceback 제거

## 부분 확인

### `MutualInformation_KSG`

기준선의 상수 생성 임베딩 정식화와 소표본 IndexError는 제거되었다. fake
embedding 입력에서 유한하고 비음수가 아닌 비상수 점수가 나오는 것도 확인했다.
그러나 새 점수가 실제 hallucination 또는 query-context dependency를 타당하게
측정한다는 통계적 검증, 분산 분석, calibration 데이터는 없다. 실행 수정은
확인했지만 메트릭 타당성 주장은 미확인이다.

### LLM/embedding 실패 처리

보고된 크래시 경로 상당수는 제거되었다. 하지만 모든 실패가 정직한
not-evaluated 상태로 바뀐 것은 아니다.

- 세 LLM 기반 E2E 메트릭은 malformed/API 오류에서 `did_eval=true`와
  `score=null`을 직렬화한다.
- simple scoring faithfulness와 hallucination faithfulness는 형식 이탈을 성공한
  0점으로 처리한다.
- single-call/hybrid faithfulness는 파싱 실패를 `null` 또는 성공한 0점으로
  처리한다.
- random document injection은 judge 실패 시 임의의 일반 문서를 만들어 유효한
  수치처럼 반환한다.

따라서 “런타임 예외 제거”는 확인했지만 “평가 실패의 정직한 표현”은 부분
확인이다.

### 비유한 수 직렬화

JSON 자체는 표준 호환이 되었다. 그러나 `did_eval`은 `true`로 남고 기존 UI는
`null`을 산술 연산과 포맷 과정에서 0처럼 표시한다. 저장 포맷 수정은 확인했지만
사용자에게 실패가 정확히 보인다는 결론은 성립하지 않는다.

### 배치 실패 격리

성공 결과 보존과 전부 실패 시 예외 재전파는 확인했다. 다만 실패한 query id,
단계, 원인을 구조화해 결과에 남기지 않으므로 진단 가능성은 제한적이다.

### 초기화 `.gitignore`

중첩 경로 생성은 동작한다. 새 `.gitignore`는 `__pycache__/`와 `history/`만
기록하며, 기존 파일이 있으면 필요한 항목을 병합하지 않는다. 문서에 적힌 모든
제외 항목을 생성한다는 주장은 코드와 일치하지 않는다.

## 거부됨

`Runner._resolve_query_file()`이 “절대 경로를 모두 거부한다”는 설명은 재현되지
않았다. 디렉터리 탈출과 허용 루트 밖 절대 경로는 차단하지만, 허용 루트 내부
파일의 절대 경로는 통과한다. 경계 밖 파일 접근 취약점은 막혔으므로 보안 효과는
있지만 문서와 구현의 계약은 일치하지 않는다.

## 재현하지 못함 또는 미검증

- 실제 Gemini/OpenAI 및 Milvus를 사용하는 종단 실행은 자격 증명과 외부 서비스에
  의존하므로 이 단계에서 실행하지 않았다.
- `Status` 사이클 순회와 루프 중복 파라미터 문제는 validation에서 수정되지 않았고
  기존 usage 예제로는 재현되지 않았다는 이전 기록만 있다. 잠재 결함으로 유지한다.
- `MutualInformation_KSG`의 실제 데이터 상 타당성, LLM judge calibration, 반복
  분산은 검증 자료가 없어 미검증이다.

## 다음 회귀 테스트 우선순위

1. 위 17개 감사 항목을 저장소 테스트로 이관한다.
2. 모든 built-in metric에 empty, adapter error, malformed output, embedding failure
   계약 테스트를 적용한다.
3. `Performance`에 명시적 상태/오류 정보를 추가하고 UI가 not-evaluated를 숫자로
   합산하지 않는 계약 테스트를 만든다.
4. WebSocket topic과 payload에 대한 백엔드-프런트엔드 contract test를 추가한다.
5. loop/status 그래프 경계 조건을 최소 재현 그래프로 고정한다.

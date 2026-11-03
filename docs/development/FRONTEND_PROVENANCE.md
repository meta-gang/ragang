# 현재 설치된 프런트엔드 빌드

검증일: 2026-11-03. Source repository: `meta-gang/RAG-APP-UI`.
Source branch: `codex/ragang-ui-2026-modernization`.
Exact source SHA: `07e733466f7440f8b8e4951f54343806022d022c`.

Node 26.10.0 / npm 11.19.1에서 잠금 파일의 의존성을 `npm ci --offline --no-audit --no-fund`로
새로 설치했다. UI 회귀 97개·타입 검사·production build를 통과했다. 커밋한 동일 소스에서
연속 두 build의 전체 12개 파일 SHA-256이 일치했다. 원본 UI와 설치본의 파일 집합·각 해시가 같고,
MANIFEST.in도 같은 명시적 파일 목록으로 갱신했다. 낡은 생성 자산은 교체 전에 작업영역 밖에 보관했다.

## 이번 변경의 계약과 검증

요청 ID는 진행·완료·오류·저장 이력의 상관관계에만 사용한다. 화면에는 짧은 요청 이름을,
접힌 기술 정보에는 원본을 표시한다. 재연결 시 실행 명령을 재전송하지 않는다. 질문 실행과
지표 평가의 의미·원래 단위·평가자 조건·유효한 0점·미평가·반복 실행 기록은 유지한다.

실제 두 브라우저 창의 동일 질문·순차 처리·결과 분리, 실행 중 연결 종료 후 동일 요청 복구,
실패 원인·저장된 실패 그래프·일괄 실행의 정확한 결과 이동을 확인했다. 320·390·768·1280px에서
가로 넘침을 확인했고 모바일 선택란이 너무 좁던 문제를 수정했다. 자세한 증거와 한계는
[요청 연결 검증](../validation/REQUEST_USABILITY_2026.md)에 있다.

Pretendard Variable v1.3.9 WOFF2와 SIL OFL 원문은 앞서 검증한 원본과 같은 바이트다.
외부 CDN을 실행 의존성으로 추가하지 않았다. Index와 service worker의 모든 참조는 같은 build에
존재한다. HTML과 동적 ragang-session.js는 precache하지 않으며 토큰은 build artifact에 넣지 않는다.

명시 단위가 `0 to 1`인 지표의 실시간·실행 추세 축은 `[0,1]`을 기본으로 한다.
범위 밖 관측값은 축을 확장해 보존하며 다른 단위의 범위를 추측하지 않는다.

## 설치 파일 SHA-256

- `2bc582461caf4e05b51d42787b901205.woff2`: `9599f12fd42fc0bce1cd50b47a0c022e108d7aa64dd0d1bb0ed44f3282d900b4`
- `819.d7a7bc6f5542898b10e2.js`: `436b329bc205b10ce78fdd1b218e0301b163d2bf6025720ee5c77f64a0e9ca91`
- `819.d7a7bc6f5542898b10e2.js.LICENSE.txt`: `45f66c349eb99046f368fd455c7823e4e588f47ca18338c95bec8aba27704134`
- `819.d7a7bc6f5542898b10e2.js.map`: `7368c93b2296f2eb18f9712d03510d37738eb048218b854bdc4f8281854aad3e`
- `index.html`: `815d7b54b442a83b57afbcc0649e60d4548b5beb4f75419b006c5effd0f3c076`
- `licenses/Pretendard-LICENSE.txt`: `d31ddd9f2bed32fd7e302a205cf2380ba0de6529152d239ef99cfb6f261bfc04`
- `main.90c45acc2bde2ecee3ff.js`: `d54e6c1a2f6dca110aabb009013d2067757c79e6e70ece759968b274aa02fc61`
- `main.90c45acc2bde2ecee3ff.js.map`: `b1105644ea0b4a28abd101feb49f46288992293b0de5d395dfd5499767b10393`
- `main.css`: `c0378f689e6834a74fc60720a80fba0d8ff90ceea3220a67af880fd1b6c2a8e6`
- `main.css.map`: `6ec164b95531dc26b48c95f3a63cb86ee643a131a021e3b963e220cfc8ba313a`
- `service-worker.js`: `233adf94aca01d32fad4f1ddb42218febce5b25dffa1899aebcbe5c57f378388`
- `workbox-39fa566e.js`: `4fc0e53b2aa52344aef1a9cd1935bb67122816a6cf52606ccfd1738d3eec9b1c`

---

## 이전 설치 기록

# 현재 설치된 프런트엔드 빌드

검증일: 2026-11-03. Source repository: `meta-gang/RAG-APP-UI`.
Source branch: `codex/ragang-ui-2026-modernization`.
Exact source SHA: `e7b865a5645c28c1547c183d245f96cbdaa7e7cf`.

Node 26.10.0 / npm 11.19.1에서 npm ci, UI 회귀 72개, 타입 검사와 production build를 통과했다.
커밋한 동일 소스에서 연속 두 build의 전체 12개 파일 SHA-256이 일치했다.
검증한 전체 파일 집합을 ragang/web/에 설치하고 MANIFEST.in을 같은 명시적 목록으로 갱신했다.
이전 자산은 작업영역 밖에 보관한 뒤 교체했다. 원본 UI와 설치본의 파일 집합·각 해시가 같다.

## 글꼴과 라이선스

Pretendard Variable v1.3.9 원본 WOFF2를 사용한다. 현대한글 11,172자와 가변 글꼴 메타데이터를
검사했으며 실행 시 외부 CDN을 호출하지 않는다. 빌드의 WOFF2가 검증한 원본과 byte-for-byte
같고, licenses/Pretendard-LICENSE.txt도 원문과 같음을 확인했다. 해당 라이선스 파일을 패키지에
포함한다. 소스 저장소의 fonts/Pretendard-metadata.json에 공식 출처와 분석 정보를 기록했다.

## 실행·표시 계약

밝은 패널·반응형 탐색·실행 비교·평가 근거·그래프 확대와 키보드 조작을 검증했다. 내부 계산은
원래 단위와 canonical 평가자 식별자를 사용한다. UI용 이름은 원본 식별자를 바꾸지 않는다.
문서 인용의 검증 여부를 보존하며 미평가를 숫자로 만들지 않는다.

Index와 service worker의 모든 참조 파일이 같은 build 안에 있다. HTML과 동적
ragang-session.js는 precache하지 않는다. 실행별 세션 bootstrap은 로컬 서버가 제공하며
빌드 산출물에 토큰을 넣지 않는다. 과거 화면이 열린 창은 한 번 새로고침해야 할 수 있다.

실제 화면·다섯 페르소나·검증 한계는 [디자인 검증 보고서](../validation/DASHBOARD_REDESIGN_2026.md)에 있다.

## 설치 파일 SHA-256

- `2bc582461caf4e05b51d42787b901205.woff2`: `9599f12fd42fc0bce1cd50b47a0c022e108d7aa64dd0d1bb0ed44f3282d900b4`
- `819.46f14f5bd159e26a7397.js`: `75a20f6cca621140c93cf5428a354520611a5da1ded519a3527091654a5cc7c5`
- `819.46f14f5bd159e26a7397.js.LICENSE.txt`: `45f66c349eb99046f368fd455c7823e4e588f47ca18338c95bec8aba27704134`
- `819.46f14f5bd159e26a7397.js.map`: `241772c8b38fba77521141c60f642c869abdef8aee6a9f5d3920783edaa3f395`
- `index.html`: `e4ea06219cb5bc6f7626c54721c96f36d76587bb0df8e5088cee0f4027837562`
- `licenses/Pretendard-LICENSE.txt`: `d31ddd9f2bed32fd7e302a205cf2380ba0de6529152d239ef99cfb6f261bfc04`
- `main.2fe35c8e4efeec85b029.js`: `d8db7f2d5f80170b47de0aa58e3d283c5f930ffa1b8b535ce9c3c9259d054f57`
- `main.2fe35c8e4efeec85b029.js.map`: `028c26081db437007a32070d4d2a19991de3b282dbd282f15a78f643b600fde5`
- `main.css`: `c0378f689e6834a74fc60720a80fba0d8ff90ceea3220a67af880fd1b6c2a8e6`
- `main.css.map`: `6ec164b95531dc26b48c95f3a63cb86ee643a131a021e3b963e220cfc8ba313a`
- `service-worker.js`: `df6a55d8bfeb8aa5e4304ce9fe5bcde825013e86a41dc488c618defa1c335ba6`
- `workbox-39fa566e.js`: `4fc0e53b2aa52344aef1a9cd1935bb67122816a6cf52606ccfd1738d3eec9b1c`

---

## 이전 설치 기록

# 현재 설치된 프런트엔드 빌드

검증일: 2026-10-26. Source repository: `meta-gang/RAG-APP-UI`.
Source branch: `codex/ragang-ui-2026-modernization`.
Exact source SHA: `35e2829850a775fd60da183f2b66ba084dbe5563`.

Node 26.10.0 / npm 11.19.0에서 UI 테스트 38개와 타입 검사를 통과했다.
변경하지 않은 lockfile의 의존성은 앞선 설치에서 npm ci로 준비했다.
source commit 후 연속 두 production build의 전체 16개 파일
SHA-256 목록이 일치했다. 전체 파일 집합을 ragang/web/에 설치하고
MANIFEST.in을 같은 목록으로 갱신했다. 오래된 생성 자산은 작업영역 밖에 보관한 뒤 교체했다.

기본 화면은 짧은 표시 이름을 사용하고 기술 정보에 원본을 보존한다. 계산용 metric key는
전체 canonical evaluator 정보를 사용한다. 평가 입력 실행 ID와 실제 문서의 연결도 유지한다.

Index와 service worker는 같은 빌드 파일만 참조한다. HTML과 동적 ragang-session.js는
precache하지 않으며 navigation과 session bootstrap은 NetworkOnly다. 세션 bootstrap은
로컬 HTTP 서버가 실행별로 제공하므로 build artifact나 Git에 토큰을 넣지 않는다.
이전 service worker가 있던 브라우저는 새 빌드 활성화 후 한 번 새로고침이 필요할 수 있다.

## 설치 파일 SHA-256

- `12c5f3f90455943689153262702765ca.woff2`: `85ade9c84e0fc0bb6d920ea1e3c9231590200ba0a79264968c6b9a0fb527a2fc`
- `2ac864a194a4c2b8049b22eec5d89072.woff2`: `e03745300b3a5fbc59afe513946e38083628edf0954dbd025f37dfb08f54c618`
- `43b5c29006f365a91ccd1e8e9e0d04ee.woff2`: `302cb692a03de6e625f7272e5adfe8c75d3069eba320256c9d93572d505a88b9`
- `908.24eb09d4117c06a5b1b1.js`: `3d9819ad36d1ccd91058fcd12e48a3ad7b217889c0ed8b401eeb22eb8b015530`
- `908.24eb09d4117c06a5b1b1.js.LICENSE.txt`: `d0fe364d118744fae25dfc40064f78ec6ea8bc131f8fbd3d6ba5e3163b2fedb2`
- `908.24eb09d4117c06a5b1b1.js.map`: `d0391b2ef24c6c220922b3245492e28c27fdf52db11191dd65d3e7cfb7872414`
- `9a72164420c5bea92570652a34fd378f.woff2`: `cfaf5fe58b1fa5768f7ec867edd5a35bc8fbd8a5988ef9440df8ddbbb554d381`
- `a2b8ed27e25e7116ab30cab19b2fff77.woff2`: `06939e852b59474a2134e644c56e8bd2bd10f2d3997ec4afb2301e8b977b61b2`
- `d3283d226f8f74e7a8d573c221c95608.woff2`: `aacccc8381dde9f0aa6379831fc972b6e7fbebb8529a7adf6fe4e90e9840fe49`
- `index.html`: `05cabacb3af45f817bc2c3047f32e960b74845d15369260de01a7c2d51e19b91`
- `main.cf63212afe2a164df9e8.js`: `886e386cc89dbb1826dc2af59abba53f217988d71e0fcbc56e88a3db61a36528`
- `main.cf63212afe2a164df9e8.js.map`: `368146c972e21d9304adc3d690395f13d920588b351312e53bafde59b627a0f7`
- `main.css`: `c0378f689e6834a74fc60720a80fba0d8ff90ceea3220a67af880fd1b6c2a8e6`
- `main.css.map`: `6ec164b95531dc26b48c95f3a63cb86ee643a131a021e3b963e220cfc8ba313a`
- `service-worker.js`: `202522a17d1b6d15184bc8124ec766a9fad455be792a9c1d806da27abf5db353`
- `workbox-39fa566e.js`: `4fc0e53b2aa52344aef1a9cd1935bb67122816a6cf52606ccfd1738d3eec9b1c`

---

## 이전 설치 기록

# 현재 설치된 프런트엔드 빌드

검증일: 2026-10-25. Source repository: `meta-gang/RAG-APP-UI`.
Source branch: `codex/ragang-ui-2026-modernization`.
Exact source SHA: `506259325969336b411198ff48415c1683027b51`.

Node 26.10.0 / npm 11.19.0에서 npm ci, UI 테스트 24개, 타입 검사와 production build를 검증했다.
연속 두 build의 전체 16개 파일 SHA-256 목록이 일치했고, source commit 후 세 번째 build도 동일했다.
전체 파일 집합을 ragang/web/에 설치하고 MANIFEST.in을 같은 목록으로 갱신했다.

Index와 service worker는 같은 빌드 파일만 참조한다. HTML과 동적 ragang-session.js는 precache하지
않으며 navigation과 session bootstrap은 NetworkOnly다. 세션 bootstrap은 로컬 HTTP 서버가
실행별로 제공하므로 build artifact나 Git에 토큰을 넣지 않는다.

이전 버전의 service worker가 이미 열려 있던 브라우저는 새 빌드 활성화 후 한 번 새로고침해야 할 수
있다. 이후 navigation/세션 스크립트는 현재 서버에서 가져온다.

## 설치 파일 SHA-256

- `12c5f3f90455943689153262702765ca.woff2`: `85ade9c84e0fc0bb6d920ea1e3c9231590200ba0a79264968c6b9a0fb527a2fc`
- `2ac864a194a4c2b8049b22eec5d89072.woff2`: `e03745300b3a5fbc59afe513946e38083628edf0954dbd025f37dfb08f54c618`
- `304.a93eeb0835a69d3ec799.js`: `a7413ee7522c78caab77b6bdab6500dd445f0cb27630c7c9330a6049dd294401`
- `304.a93eeb0835a69d3ec799.js.LICENSE.txt`: `d0fe364d118744fae25dfc40064f78ec6ea8bc131f8fbd3d6ba5e3163b2fedb2`
- `304.a93eeb0835a69d3ec799.js.map`: `53f6b7abf87e7a14e1a0ed5c04097d6dc092286927e247bc643b35a90a16e181`
- `43b5c29006f365a91ccd1e8e9e0d04ee.woff2`: `302cb692a03de6e625f7272e5adfe8c75d3069eba320256c9d93572d505a88b9`
- `9a72164420c5bea92570652a34fd378f.woff2`: `cfaf5fe58b1fa5768f7ec867edd5a35bc8fbd8a5988ef9440df8ddbbb554d381`
- `a2b8ed27e25e7116ab30cab19b2fff77.woff2`: `06939e852b59474a2134e644c56e8bd2bd10f2d3997ec4afb2301e8b977b61b2`
- `d3283d226f8f74e7a8d573c221c95608.woff2`: `aacccc8381dde9f0aa6379831fc972b6e7fbebb8529a7adf6fe4e90e9840fe49`
- `index.html`: `07a355c74f21a78cec00c084434a311baa515bf5db02fb4fe4cc133e71761233`
- `main.a0c0b10b85ec64da476b.js`: `28dadc79450b5f82a7cc933c9fb4bde6fae8cfecfa55be47508187c7a86c0587`
- `main.a0c0b10b85ec64da476b.js.map`: `58a7c391a0e738564ec23713aed36f592941cb361e6db84857d0ad4071a801a9`
- `main.css`: `c0378f689e6834a74fc60720a80fba0d8ff90ceea3220a67af880fd1b6c2a8e6`
- `main.css.map`: `6ec164b95531dc26b48c95f3a63cb86ee643a131a021e3b963e220cfc8ba313a`
- `service-worker.js`: `1acbbcfaab71086071c15cee7bbd064befa76d9fdfb6cacbfbb5166fc9e566bf`
- `workbox-39fa566e.js`: `4fc0e53b2aa52344aef1a9cd1935bb67122816a6cf52606ccfd1738d3eec9b1c`

---

## 이전 조사 기록

# 프런트엔드 provenance 분석

분석 기준일: 2026-08-20

## 결론

과거 `ragang/web/` 번들의 정확한 source commit은 증명할 수 없었지만, 현재 설치된
번들은 `RAG-APP-UI`의 전용 modernization branch에서 검증·commit한 source를 직접
build한 것이다. Exact commit과 asset hash는 아래에 기록한다. `ragang/web/`의
minified 파일은 직접 수정하지 않는다.

## 근거

### 백엔드 번들 이력

- 백엔드 `30658ee`는 2025-12-02 19:06:07+09:00에 프런트엔드 빌드 파일을
  교체했다.
- 추적된 `index.html`은 `142.cbe331e0143c713c2b3a.js`와
  `main.24f72c7eb5c45ebc6887.js`만 로드한다.
- 작업 트리에 있던 다른 해시의 JS 파일은 `index.html`이나 추적된 서비스
  워커가 참조하지 않는 orphan 산출물이다. 이 파일들은 기존 사용자 파일이므로
  분석 중 삭제하지 않았다.

### 프런트엔드 이력

- `RAG-APP-UI`의 `61c4f4f`는 2025-12-02 18:55:49+09:00에 생성되었다.
  백엔드 번들 교체보다 약 11분 앞선다.
- 이 커밋은 starter 모듈 제외와 E2E 평가 표시를 추가했다. 추적된 백엔드
  main 번들에도 해당 기능 문자열과 이후 UI 구조가 존재한다.
- `origin/feat/info-out`의 끝은 `4943f86`(2025-11-10)이다. 이후
  `feat/begin` 계보에서 mock 데이터 제거, WebSocket 계약 수정, 라우팅,
  Run Queries, 히스토리 변환, starter/E2E 처리 등 다수 변경이 추가되었다.
  `feat/info-out` 자체에는 제거되기 전 mock 데이터 경로가 남아 있으므로 현재
  번들의 직접 소스가 될 수 없다.

## 분석 당시 재현성 판정

현재 상태의 `npm run build`는 성공하지만 재현 가능한 빌드는 아니다.

- `package-lock.json`이 추적되지 않고 `.gitignore`가 이를 제외한다.
- `webpack.common.js`가 `process.env` 전체를 `DefinePlugin`에 전달한다.
- 같은 소스와 같은 `node_modules`에서 연속 실행한 production build의 vendor와
  main content hash 및 파일 크기가 달라졌다.
- 이 방식은 빌드 환경에 따른 결과 변동뿐 아니라 브라우저 번들에 불필요한 환경
  값이 포함될 위험을 만든다.

정확한 provenance를 복구하려면 먼저 전체 환경 주입을 제거하고, Node/npm
버전과 락파일을 추적하며, clean checkout에서 두 번 빌드한 결과가 동일함을
검증해야 한다.

## 이번 작업의 재현성 복구

- `DefinePlugin`은 이제 공개 설정 `REACT_APP_WS_URL` 하나만 주입한다.
- `package-lock.json`을 추적 대상으로 복구하고 test/typecheck 스크립트를
  추가했다.
- Workbox source map에 임시 디렉터리가 기록되지 않도록 production service
  worker source map을 비활성화했다.
- Node 26.7.0/npm 11.19.0의 동일 작업트리에서 production build를 연속 두 번
  실행했고 전체 `dist/` 파일 SHA-256 목록이 일치했다.
- 검증된 전체 `dist/`를 백엔드에 동기화했으며, `index.html`과 service worker가
  같은 최신 해시 자산만 참조하는 것을 확인했다.

## 설치된 검증 빌드

- source repository: `meta-gang/RAG-APP-UI`
- source branch: `codex/ragang-ui-2026-modernization`
- exact source commit:
  `cd8ace19c0e2a25eecb315d5d556682e9305e1cf`
- build runtime: Node 26.7.0, npm 11.19.0
- verification: `npm ci`, `npm test`, `npm run typecheck`, production build
  연속 2회와 전체 `dist/` SHA-256 일치
- installed entry assets:
  - `672.b1ce182a0d38187a8faa.js`
  - `main.999a67e469b0ae75a858.js`
  - `main.css`
  - `service-worker.js`
  - `workbox-86637ee2.js`

핵심 파일 SHA-256은 다음과 같다.

- `index.html`: `296ae46cb2dc6b4cb978064d04d3b8c9d2d212335c898f26a1696297427137db`
- `672.b1ce182a0d38187a8faa.js`: `10c9e18323ba6a3a8ab81355237b178c815f34e32df217de754aa46cd54facf9`
- `main.999a67e469b0ae75a858.js`: `5710b718eab9bbd8b31e1a5125190991222f8a391f21a52a4c97cb5e09d20426`
- `service-worker.js`: `e9d1ef9246f4efbc6f5780296b11be35164bae5b281615fda1f29d77b0a87f5b`

## 안전한 소스-번들 흐름

1. UI 소스 저장소에서 변경한다.
2. 타입 검사와 테스트를 실행한다.
3. 추적된 락파일로 clean install한다.
4. production build를 두 번 실행해 파일 해시가 동일한지 확인한다.
5. 백엔드 `ragang/web/`에는 검증된 한 빌드의 전체 파일 집합만 설치한다.
6. `index.html`과 서비스 워커가 같은 해시 파일만 참조하는지 검사한다.

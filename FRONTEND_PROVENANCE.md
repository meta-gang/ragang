# 프런트엔드 provenance 분석

분석 기준일: 2026-08-20

## 결론

현재 `ragang/web/`의 추적된 번들은 `RAG-APP-UI`의
`feat/info-out` 끝 커밋에서 직접 생성된 것이 아니다. 기능 내용과 커밋 시각을
함께 보면 `feat/begin`의 `61c4f4f`가 가장 유력한 소스 기준점이다. 다만 당시
의존성 락파일과 빌드 환경이 보존되지 않아 content hash까지 동일한 빌드를
재현하거나 exact source commit을 암호학적으로 증명할 수는 없다.

따라서 UI 수정은 `61c4f4f`를 포함하는 `feat/begin` 소스에서 수행하며,
`ragang/web/`의 minified 파일을 직접 수정하지 않는다.

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
  `2b325d510334f656a9f41a75ee24013d640c217f`
- build runtime: Node 26.7.0, npm 11.19.0
- verification: `npm ci`, `npm test`, `npm run typecheck`, production build
  연속 2회와 전체 `dist/` SHA-256 일치
- installed entry assets:
  - `711.de815a03bc2919966fc9.js`
  - `main.16cb993c67e5dbc716f3.js`
  - `main.css`
  - `service-worker.js`
  - `workbox-86637ee2.js`

핵심 파일 SHA-256은 다음과 같다.

- `index.html`: `84233265becddfd1a513a80046c0af0faaf364c7bff58a44b20dbc380882576c`
- `711.de815a03bc2919966fc9.js`: `796e7f49304810a75f54cd5d16309f6c22337485b942f347921d7422bd14c928`
- `main.16cb993c67e5dbc716f3.js`: `c95b2f3bd161e73a8dd32e4d8587c259a85ec3de8c670385d6c35a14788572c3`
- `service-worker.js`: `21d900a2157e4a59a3262cf60c36f50e439c72daed7b2c3d1855203953aac2dc`

## 안전한 소스-번들 흐름

1. UI 소스 저장소에서 변경한다.
2. 타입 검사와 테스트를 실행한다.
3. 추적된 락파일로 clean install한다.
4. production build를 두 번 실행해 파일 해시가 동일한지 확인한다.
5. 백엔드 `ragang/web/`에는 검증된 한 빌드의 전체 파일 집합만 설치한다.
6. `index.html`과 서비스 워커가 같은 해시 파일만 참조하는지 검사한다.

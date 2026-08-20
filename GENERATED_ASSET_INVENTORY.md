# 생성 자산 및 orphan inventory

기준일: 2026-08-20

## 설치된 검증 자산

`ragang/web/`의 현재 entry build는 frontend commit
`cd8ace19c0e2a25eecb315d5d556682e9305e1cf`에서 생성했다.

- entry: `index.html`
- vendor: `672.b1ce182a0d38187a8faa.js`
- application: `main.999a67e469b0ae75a858.js`
- style: `main.css`
- service worker: `service-worker.js`, `workbox-86637ee2.js`
- font와 source map: 같은 production build의 출력

이 파일들은 Git-tracked, source-generated, 현재 task에서 설치, index/service worker
또는 package manifest에서 참조되며 삭제하면 안 된다.

이 build는 반복 module snapshot, graph/cycle execution trace, raw metric unit와
evaluator coverage를 표시하고 이질 metric의 overall score를 제거한 research-quality
presentation을 포함한다. 동일 source에서 연속 두 production build의 전체 file hash가
일치했다.

## 보존된 pre-existing orphan

아래 파일은 task 시작 전에 이미 존재했고 Git-untracked였다. 현재 `index.html`,
`service-worker.js`, `MANIFEST.in` 어디에서도 참조하지 않으며 검증 wheel에도
포함되지 않는다. 모두 generated output으로 보이지만 사용자 소유 파일이므로
자동 삭제하지 않았다.

| 경로 | Git | 참조 | 종류 | 기원 | 권고 |
| --- | --- | --- | --- | --- | --- |
| `ragang/web/277.10fdf5ebc040ae9492f6.js` | untracked | unreferenced | generated bundle | pre-existing | 사용자 승인 후 삭제 가능 |
| `ragang/web/277.10fdf5ebc040ae9492f6.js.LICENSE.txt` | untracked | unreferenced | generated license | pre-existing | 대응 bundle 삭제 시 함께 삭제 가능 |
| `ragang/web/277.2bbffe6bb7613619ea63.js` | untracked | unreferenced | generated bundle | pre-existing | 사용자 승인 후 삭제 가능 |
| `ragang/web/277.2bbffe6bb7613619ea63.js.LICENSE.txt` | untracked | unreferenced | generated license | pre-existing | 대응 bundle 삭제 시 함께 삭제 가능 |
| `ragang/web/277.f78b837b7c03826aa49e.js` | untracked | unreferenced | generated bundle | pre-existing | 사용자 승인 후 삭제 가능 |
| `ragang/web/277.f78b837b7c03826aa49e.js.LICENSE.txt` | untracked | unreferenced | generated license | pre-existing | 대응 bundle 삭제 시 함께 삭제 가능 |
| `ragang/web/main.2b03dfb8df4cc431d740.js` | untracked | unreferenced | generated bundle | pre-existing | 사용자 승인 후 삭제 가능 |
| `ragang/web/main.af1920b9ab350d8b1e40.js` | untracked | unreferenced | generated bundle | pre-existing | 사용자 승인 후 삭제 가능 |
| `ragang/web/main.e08b28567850a394a382.js` | untracked | unreferenced | generated bundle | pre-existing | 사용자 승인 후 삭제 가능 |
| `ragang/web/workbox-51550195.js.map` | untracked | unreferenced | generated source map | pre-existing | 사용자 승인 후 삭제 가능 |

## Task-generated temporary files

- live acceptance project와 wheel 확인 디렉터리는 운영체제 임시 경로 아래에만
  만들었다. repository 파일로 stage하지 않았으며 별도 삭제하지 않았다.
- live acceptance collection `ragang_live_demo`는 검증 후 삭제했다.
- 기존 Milvus containers는 삭제하지 않고 원래 stopped 상태로 되돌렸다.
- backend의 ignored `build/`와 예제 `__pycache__/`는 검증 중 생길 수 있는 task
  output이며 commit과 wheel에서 제외한다. 기존 파일과 구분하기 어려워 자동
  삭제하지 않는다.
- frontend `dist/`와 `node_modules/`는 ignored build/dependency output이며 commit하지
  않는다.

## 안전 규칙

- orphan이 작업트리에 있어도 `MANIFEST.in`은 검증된 파일만 명시하므로 wheel에
  섞이지 않는다.
- 새 frontend build를 설치할 때 source commit, asset hash, index/service-worker
  참조와 manifest를 함께 갱신한다.
- pre-existing untracked 파일은 명시적 사용자 승인 없이 삭제하지 않는다.

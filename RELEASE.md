# Release and generated frontend policy

## Release 전제

Release, tag, package publish는 별도 명시적 승인 없이 수행하지 않습니다. Branch commit/push
승인은 release 승인과 다릅니다. `main`, `validation`에 직접 push하거나 force push하지
않습니다.

## Backend 검증

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q ragang tests
SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct) .venv/bin/python -m build --wheel
```

Wheel을 만들 때 `MANIFEST.in`과 tracked `ragang/web/` inventory가 일치하는지 확인합니다.
Dirty worktree의 orphan asset은 package에 포함하지 않습니다.

## Frontend bundle 설치

1. `RAG-APP-UI` source branch에서 `npm ci`, test, typecheck, build를 통과합니다.
2. Source 변경을 먼저 commit하여 exact SHA를 확정합니다.
3. 그 commit에서 production build를 다시 만듭니다.
4. Build 전체 asset set을 backend `ragang/web/`에 동기화합니다. Minified 파일을 직접
   수정하지 않습니다.
5. `index.html`, service worker, hashed chunk가 같은 build set인지 확인합니다.
6. `MANIFEST.in`, `GENERATED_ASSET_INVENTORY.md`, `FRONTEND_PROVENANCE.md`에 exact source
   SHA와 검증 명령을 기록합니다.
7. Backend test/compile/wheel 검증을 다시 실행합니다.

연속 build의 hash 동일성은 dependency lock과 build configuration의 deterministic 여부를
확인하는 acceptance입니다. 기존 사용자 untracked file은 자동 삭제하지 않습니다.

## Git safety

```bash
git status --short --branch
git diff --check
git rev-list --left-right --count HEAD...@{upstream}
```

Upstream divergence가 예상과 다르면 fetch 후 재검토합니다. Commit에는 secret, history
result, local settings/path, virtual environment, generated cache를 포함하지 않습니다.

## Release note 필수 항목

- Evaluation 의미론 변경과 migration 영향
- Graph/trace schema와 `max_steps` 정책
- Metric 단위·방향·failure behavior 변경
- Test/typecheck/build 결과
- Backend/frontend commit SHA와 bundle provenance
- Not evaluated/remaining limitation

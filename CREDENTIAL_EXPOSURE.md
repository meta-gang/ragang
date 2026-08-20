# 평문 credential 노출 분류

기준일: 2026-08-20

## 조사 원칙

credential 값은 출력, 복사, 부분 표시, hash, commit하지 않았다. 아래 결과는
파일·Git metadata와 설정 변수명만 사용한다.

## 발견 항목

| 항목 | 판정 |
| --- | --- |
| 디렉터리/프로젝트명 | `my_rag_service` |
| Git repository | 아님 (`.git`과 상위 Git worktree 없음) |
| 상대 파일 경로 | `settings.py` |
| 설정 변수명 | `API_KEY` |
| 현재 Git-tracked | 아니오 |
| Git history 존재 | 확인 가능한 Git repository가 없어 증거 없음 |
| 검증 가능한 remote branch 존재 | 없음 |
| public/private visibility | Git repository가 아니므로 해당 없음 |

## 분류와 사용자 조치

- 노출 분류: **A — Local-only / untracked / no Git history evidence**
- 외부 공개 증거: **없음**
- credential rotation/revocation: **RECOMMENDED**

현재 증거만으로 `REQUIRED NOW` 수준의 public 또는 Git-history 노출을 주장할 수는
없다. 다만 유효할 수 있는 credential이 평문 파일에 있으므로 환경변수 또는 secret
manager로 이전한 뒤 기존 credential을 예방적으로 회전하는 것이 안전하다. 외부
credential의 회전은 자동 수행하지 않았다.

## 최소 migration 제안

관련 프로젝트의 명시적 승인을 받은 뒤 다음 원칙으로 변경한다.

```python
import os

API_KEY = os.environ.get("RAGANG_API_KEY", "")
```

- `.env`와 local settings override를 `.gitignore`에 추가한다.
- startup 시 변수 미설정을 값 노출 없이 명확한 오류로 처리한다.
- log, exception, URL query, history, provenance에 값을 남기지 않는다.
- CI/운영에서는 repository secret 또는 조직 secret manager로 주입한다.

## 작업 저장소 점검

현재 backend와 frontend `HEAD`의 Git-tracked 파일에 대해 Google/OpenAI/GitHub/AWS
형식의 대표 plaintext secret pattern을 파일명만 반환하는 방식으로 점검했다.

- `ragang`: pattern match 없음
- `RAG-APP-UI`: pattern match 없음

이는 알려진 pattern 점검 결과이며 모든 종류의 secret 부재를 수학적으로 증명하는
것은 아니다. commit/push 직전 동일 검사를 다시 실행한다.

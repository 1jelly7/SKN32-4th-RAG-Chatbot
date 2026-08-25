# Django + FastAPI MCP 챗봇

사내 문서 RAG와 구매·판매 Text2SQL을 하나의 채팅 UI/API로 제공하는 Python 프로젝트다.
Django는 사용자 UI와 계정·세션·관리자 기능을 소유하고, FastAPI는 채팅 API·LangGraph·
캐시·MCP 조율을 담당한다. 두 애플리케이션은 독립 프로세스로 실행하며 공개 환경에서는
하나의 주소 뒤에서 경로 기반으로 라우팅한다.

## 구조

```text
project/
├── django_app/                 # 사용자 UI, 계정, 인증 API, Django Admin, DB migration
├── app/                        # FastAPI 채팅·문서 API, LangGraph, 캐시, MCP client
├── shared/                     # Django와 FastAPI가 공유하는 역할 정책
├── mcp_servers/                # 문서·구매·판매 Tool 구현
├── ingestion/                  # 문서 등록·임베딩·인덱싱
├── etl/                        # 구매·판매 오프라인 적재
├── database/                   # DB별 schema/DDL 자료
├── tests/                      # unit, integration, django 계약 테스트
└── docs/                       # 아키텍처·인터페이스·분리 계획
```

책임과 인터페이스의 정본은 [아키텍처](docs/architecture.md),
[인터페이스](docs/interface.md), [소유권](docs/ownership.md),
[구조 분리 계획](docs/django-fastapi-separation-plan.md)이다.

현재 활성 FastAPI 앱은 `app.main:app`, Django 앱은
`django_app.config.asgi:application`이다. 계정·로그인·세션 발급은 Django만 소유하며,
FastAPI는 내부 인증 확인 API를 통해서만 사용자 컨텍스트를 받는다.

## 준비

Windows PowerShell 기준:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에는 팀이 제공한 OpenAI, Redis, 업무 DB, 문서 DB, account DB 값을 입력한다.
추가로 32자 이상의 `DJANGO_SECRET_KEY`와 서로 다른 `AUTH_INTROSPECTION_KEY`를 비밀 관리
수단에서 주입한다. 실제 비밀값이 든 `.env`는 커밋하지 않는다.

`ACCOUNT_DB_USER`는 Django migration을 실행할 때 schema 변경 권한이 필요하다. 운영
런타임에서는 조직의 배포 정책에 따라 migration 전용 자격 증명과 애플리케이션용 최소
권한 자격 증명을 분리한다.

구조 분리에 직접 필요한 설정은 다음과 같다.

| 설정 | 용도 |
|---|---|
| `ACCOUNT_DB_*` | Django가 소유하는 account DB 연결 |
| `DJANGO_SECRET_KEY` | Django 세션·보안 서명 키; 운영에서는 32자 이상 |
| `AUTH_INTROSPECTION_KEY` | FastAPI→Django 내부 인증 확인 전용 키; 운영에서는 32자 이상 |
| `DJANGO_AUTH_INTROSPECTION_URL` | FastAPI가 호출할 Django 내부 endpoint |
| `AUTH_INTROSPECTION_TIMEOUT_SECONDS` | 내부 인증 확인 timeout; 0초 초과, 최대 30초 |
| `AUTH_SESSION_EXPIRE_SECONDS` | 고정 세션 만료 시간; 요청마다 연장하지 않음 |
| `AUTH_COOKIE_SECURE` | HTTPS 환경의 session·CSRF cookie secure 속성 |
| `DJANGO_SERVE_STATIC_FILES` | 로컬에서만 Django가 UI 정적 파일을 직접 제공할지 여부 |
| `LEGACY_ACCOUNT_TIME_ZONE` | 기존 `accounts`의 naive `DATETIME` 해석 시간대 |

### Django 인증 보안 설정

`DJANGO_SECRET_KEY`와 `AUTH_INTROSPECTION_KEY`는 같은 값을 재사용하지 않는다. 다음
PowerShell 명령으로 충분히 긴 난수 두 개를 생성한다.

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48)); print(secrets.token_urlsafe(48))"
```

첫 번째 출력값은 `DJANGO_SECRET_KEY`, 두 번째 출력값은
`AUTH_INTROSPECTION_KEY`에 입력한다. 로컬에서 공개 gateway가 `localhost:8000` 또는
`127.0.0.1:8000`으로 열리는 경우의 예시는 다음과 같다.

```env
DJANGO_SECRET_KEY=<첫 번째 생성값>
AUTH_INTROSPECTION_KEY=<두 번째 생성값>

DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
DJANGO_SERVE_STATIC_FILES=false
DJANGO_AUTH_INTROSPECTION_URL=http://127.0.0.1:8001/internal/auth/introspect
AUTH_COOKIE_SECURE=false
```

`DJANGO_CSRF_TRUSTED_ORIGINS`에는 브라우저가 실제로 접속하는 공개 origin을
`scheme://host[:port]` 형식으로 쉼표로 구분해 입력한다. 경로나 마지막 `/`는 넣지
않는다. 같은 origin으로만 요청하고 reverse proxy가 원래 host와 scheme을 올바르게
전달한다면 별도 trusted origin이 필요하지 않을 수 있지만, 위 로컬 예시는 허용할 두
공개 주소를 명시적으로 등록한다.

공개 주소가 `https://chat.example.com`인 운영 환경의 예시는 다음과 같다.

```env
DJANGO_SECRET_KEY=<운영용 첫 번째 생성값>
AUTH_INTROSPECTION_KEY=<운영용 두 번째 생성값>

DJANGO_ALLOWED_HOSTS=chat.example.com,django-internal
DJANGO_CSRF_TRUSTED_ORIGINS=https://chat.example.com
DJANGO_SERVE_STATIC_FILES=false
AUTH_COOKIE_SECURE=true
```

- 두 비밀 키는 `.env` 또는 배포 환경의 비밀 관리 수단에만 저장하고 Git에 커밋하지 않는다.
- FastAPI와 Django가 환경을 따로 사용한다면 양쪽에 동일한
  `AUTH_INTROSPECTION_KEY`를 주입한다. `DJANGO_SECRET_KEY`는 Django에만 필요하다.
- 운영 중 `DJANGO_SECRET_KEY` 또는 `AUTH_INTROSPECTION_KEY`를 변경하면 기존 세션이나
  내부 인증 호출에 영향을 줄 수 있으므로 계획된 key rotation 절차로 교체한다.
- 값을 변경한 뒤에는 Django와 FastAPI 프로세스를 모두 재시작한다.

## 기존 DB 이관

기존 `account_db`나 `accounts` 테이블을 삭제하지 않는다. 먼저 백업한 뒤 기존 DB를
가리키는 설정으로 다음 명령을 실행한다.

```powershell
.venv\Scripts\python.exe django_app\manage.py migrate
.venv\Scripts\python.exe django_app\manage.py audit_legacy_accounts
```

`LEGACY_ACCOUNT_TIME_ZONE`은 기존 `accounts` 테이블의 `DATETIME`이 기록된 시간대와
일치해야 한다. 기본값은 `Asia/Seoul`이다. 감사 명령은 Django 로그인 트래픽을 열기 전에
실행해야 `last_login`을 이관 시점 기준으로 정확히 대조할 수 있다.

legacy data migration은 지원되는 scrypt 파라미터, 사용자명·역할·활성 상태와 시각 필드를
검증하고 이상이 있으면 중단한다. `0002_import_legacy_accounts`는 부분 rollback 후 재적용
충돌을 막기 위해 irreversible이다. migration을 역적용하지 말고 실패 시 사전 백업/복구
지점으로 되돌린 뒤 원인을 수정한다.

Django 관리자 계정이 필요하면 migration 뒤에 생성한다.

```powershell
.venv\Scripts\python.exe django_app\manage.py createsuperuser
```

이 명령은 이메일, 표시 이름, 애플리케이션 역할을 함께 입력받는다. 애플리케이션의
`admin` 역할만으로 Django Admin 권한이 생기지는 않는다.

## 통합 초기화

`setup_all.py`는 README의 Django migration, 문서 경로 등록·FAISS 인덱싱, 구매·판매 ETL을
정해진 순서로 조립한다. 기본 실행은 변경 없이 계획만 출력한다.

```powershell
.venv\Scripts\python.exe setup_all.py
```

연결 정보가 채워진 `.env`와 선택한 ETL 원본 workbook을 준비한 뒤에만 실제 실행한다.

```powershell
.venv\Scripts\python.exe setup_all.py --apply
```

문서 또는 특정 도메인을 아직 준비하지 않았다면 해당 단계를 명시적으로 생략한다.

```powershell
.venv\Scripts\python.exe setup_all.py --apply --skip-documents --skip-purchase
```

기본 ETL 원본 대신 다른 workbook을 쓰려면 `--purchase-source`, `--sales-source`를 사용한다.
대화형 Django 관리자 생성은 `--create-superuser` 옵션으로 migration 뒤에 별도 실행한다.
이 도구는 `.env`를 만들거나 수정하지 않으며, `--apply` 전에는 DB·FAISS·ETL 데이터를
변경하지 않는다.

## 로컬 origin gateway 실행

전체 UI 흐름은 Nginx가 제공하는 `http://127.0.0.1:8000` 한 주소로 접속한다. 로컬
gateway 설정은 `deploy/nginx/local.conf`이며 Nginx 실행 파일은 프로젝트 Python
의존성이 아니므로 별도로 설치하고 `nginx` 명령을 `PATH`에서 실행할 수 있게 준비한다.

Nginx의 prefix는 반드시 프로젝트 루트로 지정한다. 이 기준으로 설정 파일의
`staticfiles/`, `logs/`, `temp/` 상대 경로가 해석된다.

프로젝트 루트에서 단일 launcher를 실행하면 Django 설정 검사, `collectstatic`, Nginx
설정 검사, Django `:8001`, FastAPI `:8002`, Nginx `:8000` 실행을 순서대로 처리한다.

```powershell
.\scripts\local_gateway.ps1
```

상태 확인, 재시작과 종료도 같은 파일을 사용한다.

```powershell
.\scripts\local_gateway.ps1 status
.\scripts\local_gateway.ps1 restart
.\scripts\local_gateway.ps1 stop
```

launcher는 이 프로젝트에서 시작한 Django와 FastAPI PID 및 시작 시각을
`temp/local-gateway-services.json`에 기록한다. 종료할 때 해당 프로세스만 확인해
종료하며 Nginx에는 graceful quit을 요청한다. 로그는 다음 파일에서 확인한다.

- `logs/django-local.out.log`, `logs/django-local.error.log`
- `logs/fastapi-local.out.log`, `logs/fastapi-local.error.log`
- `logs/nginx-local-access.log`, `logs/nginx-local-error.log`

gateway 사용 시 로컬 `.env`도 `DJANGO_SERVE_STATIC_FILES=false`로 둔다. 정적 파일은
Django 개발 서버가 아니라 Nginx가 `staticfiles/`에서 제공한다.
안전한 프로세스 종료를 위해 Django와 FastAPI의 자동 reload는 사용하지 않는다. 코드나
gateway 설정 변경을 반영할 때는 launcher의 `restart`를 실행한다.

브라우저에서는 `http://127.0.0.1:8000/`만 사용한다. gateway는 같은 공개 origin 아래
다음 경계를 적용한다.

| 경로 | 대상 |
|---|---|
| `/`, 사용자 page route, `/api/auth/*`, `/admin`, `/admin/*` | Django |
| `/django-static/*` | Django UI·Admin `collectstatic` 산출물을 제공하는 정적 파일 서버 |
| `/api/chat`, `/api/documents/*`, `/api/health`, `/docs`, `/openapi.json` | FastAPI |
| 그 밖의 `/api/*` | gateway `404`; Django page fallback 금지 |
| `/internal/auth/*` | gateway `404`; FastAPI에서 Django로만 직접 호출 |

gateway 기준 Django Admin은 `http://127.0.0.1:8000/admin/`, FastAPI OpenAPI는
`http://127.0.0.1:8000/docs`, liveness는 `http://127.0.0.1:8000/api/health`다.
`127.0.0.1:8001`과 `127.0.0.1:8002`는 장애 진단용 upstream 주소일 뿐 정상 사용자
접속 경로가 아니다. `/internal/auth/*`는 공개 gateway에서 항상 `404`이며 FastAPI만
`DJANGO_AUTH_INTROSPECTION_URL`의 Django 직접 주소로 호출한다.

로컬 gateway와 운영 배포에서는 먼저 Django UI·Admin 정적 파일을 수집한다.

```powershell
.venv\Scripts\python.exe django_app\manage.py collectstatic --clear --noinput
```

생성되는 `staticfiles/`는 배포 산출물이며 Git에 커밋하지 않는다. TLS 종료 proxy를 쓰는
경우에는 원래 scheme/host 전달과 `DJANGO_ALLOWED_HOSTS`,
`DJANGO_CSRF_TRUSTED_ORIGINS`, secure cookie 설정을 배포 환경에 맞춰 검증한다. 신뢰할
수 있는 proxy가 들어오는 `X-Forwarded-Proto`를 제거한 뒤 직접 다시 설정하는 경우에만
`DJANGO_TRUST_X_FORWARDED_PROTO=true`를 사용한다. 내부 Django 서비스 hostname도
`DJANGO_ALLOWED_HOSTS`에 포함해야 한다.

`ManifestStaticFilesStorage`가 `collectstatic` 중 파일 내용 hash가 포함된 정적 URL과
manifest를 생성한다. HTML page는 `no-cache`를 유지하고, Nginx/CDN은 hash된
`/django-static/*` 자산에 `Cache-Control: public, max-age=31536000, immutable`을
설정한다. 새 배포에서는 반드시 `collectstatic --clear --noinput`을 먼저 실행해 더 이상
참조되지 않는 이전 번들을 제거한다.

공개 gateway에서는 `/api/auth/login`에 조직 표준 rate limit을 적용하고
`/internal/auth/*`를 외부 라우팅·접근 로그의 header 수집 대상에서 제외한다. Django
Admin은 `is_staff` 계정만 사용하며 운영 환경의 접근 제어 정책을 별도로 적용한다.

## 테스트

```powershell
.venv\Scripts\python.exe -m pytest tests\django
.venv\Scripts\python.exe -m pytest tests\unit
.venv\Scripts\python.exe -m pytest tests\integration
.venv\Scripts\python.exe -m pytest
```

기본 unit/integration 테스트는 fake/mock 중심이다. 실제 MySQL, Redis, 원격 MCP,
운영 FAISS까지 검증했다는 의미는 아니며 외부 서비스 검증은 별도 절차로 수행한다.
UI 이전 뒤 최근 검증은 Django system/migration/static dry-run check와 전체 pytest
`402 passed, 27 skipped`다. 실제 gateway·브라우저와 외부 인프라 검증 결과로 확대
해석하지 않는다.

## 주요 제약

- FastAPI와 Agent는 account DB, 업무 MySQL, FAISS와 원문 파일에 직접 접근하지 않는다.
- Django는 account DB만 소유하며 채팅, MCP, 업무 DB를 호출하지 않는다.
- Data MCP 조회는 허용된 View에 대한 읽기 전용 쿼리만 수행한다.
- ETL과 문서 인덱싱은 채팅 요청 경로에서 실행하지 않는다.
- 질문 원문, 전체 근거, 비밀번호·키, 내부 파일 경로를 로그에 남기지 않는다.

## 현재 남은 전환 작업

- `/`, FastAPI API, `/api/auth/*`, `/admin*`, `/django-static/*` 경로와
  `/internal/auth/*` 비공개 정책을 실제 gateway에서 검증한다.
- 전환 기간에 기존 위치에서 수집하는 Chart.js vendor bundle을 Django `web/static/web/`
  정본으로 옮긴 뒤 호환 설정을 제거한다.
- 동일 origin 실제 브라우저에서 로그인·채팅·표·차트·문서 다운로드를 검증한다.

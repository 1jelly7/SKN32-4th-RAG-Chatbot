# Django·FastAPI 구조 분리 계획 및 진행 현황

> 최종 갱신: 2026-08-20 KST  
> 전체 상태: **Django 인증·MySQL 계정 이관 완료 / Django UI 코드 이전 진행 중·로컬 gateway 구현 대기**  
> 문서 목적: FastAPI 단일 애플리케이션의 인증·계정 책임을 Django로 분리하고, 후속 UI
> 고도화에서 화면 제공 책임까지 Django로 이전하는 범위와 진행 상태를 한 곳에서 관리한다.

## 1. 목표

현재 FastAPI가 함께 담당하는 인증·계정 관리와 AI 채팅 실행 책임을 다음과 같이 분리한다.

- Django는 계정, 비밀번호, 역할, 로그인·로그아웃과 관리자 화면을 소유한다.
- FastAPI는 채팅 API, LangGraph, LLM, 캐시와 MCP 조율을 유지한다.
- 기존 `/api/chat`, `ChatResponse`, MCP Tool 이름과 envelope 계약은 변경하지 않는다.
- 첫 전환에서는 문서 검색, 구매·판매 Text2SQL, ETL, FAISS와 정적 UI의 소유권을 변경하지 않는다.
- 인증 전환이 안정화된 뒤 UI 고도화 단계에서는 Django가 HTML·프론트엔드 정적 자산을
  소유하고 FastAPI는 채팅·문서·상태 API 전용 서비스로 축소한다.
- 두 애플리케이션은 한 프로세스에 mount하지 않고 독립 실행한다.

## 2. 변경 전 기준 구조

변경 전 실제 통합 진입점은 `app/main.py`였으며, 다음 흐름으로 동작했다.

```text
Browser
  -> FastAPI
      -> 직접 구현 인증/RBAC
      -> MemoryCache
      -> LangGraph
          -> Document Tool
          -> Purchase/Sales Tool
          -> Evidence 평가
          -> 답변 합성

Offline
  -> 문서 등록·FAISS 인덱싱
  -> 구매·판매 ETL
```

분리 작업에 직접 영향을 준 변경 전 사항은 다음과 같다.

- `app/api/`가 현재 FastAPI 공개 API 경로다.
- `app/auth/`가 계정 DB 조회, scrypt 비밀번호 검증, 서명 쿠키와 프로세스 내 세션을 담당했다.
- `app/agent/`, `app/mcp/`, `app/cache/`는 인증된 사용자 컨텍스트를 전달받아 채팅 요청을 처리한다.
- `app/routers/`, `app/services/`, `app/config/`, `mcp_server/`에는 초기 구조가 함께 남아 있었다.
- `BOTH` 실행 방식은 코드와 일부 계약 문서의 설명이 일치하지 않았다.

정본·레거시 분류:

| 경로 | 분류 | 처리 |
| --- | --- | --- |
| `app/main.py`, `app/api/` | FastAPI 정본 | 채팅·문서·system API 유지, 인증 라우터 등록 해제 |
| `app/agent/`, `app/mcp/`, `app/cache/` | FastAPI 정본 | 기존 책임과 공개 계약 유지 |
| `app/auth/dependencies.py`, `gateway.py`, `policy.py` | 활성 인증 경계 | Django 세션 확인과 RBAC만 담당 |
| `app/api/auth.py`, `app/auth/{repository,service,sessions,session_store}.py` | 롤백용 legacy | 관찰 기간 뒤 단계 5에서 제거 |
| `app/routers/`, `app/services/`, `app/config/`, `mcp_server/` | 비정본 legacy 후보 | 이번 분리 범위에서 삭제하지 않음 |

`BOTH`의 정본은 `app/agent/graph.py`의 병렬 fan-out이다. Document와 Database가 병렬로
실행되고 evidence에서 합류하며, 구매·판매 두 Data Tool만 database 분기 안에서 순차 실행한다.

관련 정본 문서:

- [아키텍처](architecture.md)
- [HTTP·MCP 인터페이스](interface.md)
- [코드 소유권](ownership.md)
- [테스트 시나리오](test-scenarios.md)

## 3. 목표 구조

### 3.1 인증 분리 1차 구조

```text
Browser
  -> 단일 공개 주소의 경로 라우팅
      -> /api/auth/*, /admin/*
          -> Django
              -> 사용자·비밀번호·역할
              -> account_db

      -> /django-static/*
          -> Django collectstatic 산출물

      -> /api/chat, 문서 다운로드, 정적 UI
          -> FastAPI
              -> Cache
              -> LangGraph
              -> LLM
              -> MCP Client
                  -> Document Tool
                  -> Purchase/Sales Tool
```

첫 구현에서는 기존 FastAPI 디렉터리를 이동하지 않고 `django_app/`을 프로젝트 루트에 추가한다.

```text
project/
├── app/                         # 기존 FastAPI 유지
├── django_app/                  # 신규 Django 인증·계정 경계
│   ├── manage.py
│   ├── config/
│   │   ├── settings.py
│   │   ├── test_settings.py
│   │   ├── urls.py
│   │   └── asgi.py
│   └── accounts/
│       ├── models.py
│       ├── admin.py
│       ├── views.py
│       ├── urls.py
│       ├── internal_urls.py
│       ├── services.py
│       ├── password_hashers.py
│       ├── management/commands/audit_legacy_accounts.py
│       └── migrations/
├── shared/auth_policy.py       # 두 서비스의 역할·업무 DB 정책 정본
├── mcp_servers/
├── ingestion/
├── etl/
├── database/
└── tests/
    ├── unit/
    ├── integration/
    └── django/
```

### 3.2 UI 고도화 후 목표 구조

UI 이전은 `accounts` 앱에 화면 책임을 추가하지 않고 별도 Django `web` 앱을 두는 방식으로
진행한다. Django는 HTML shell, UI 정적 자산과 브라우저 인증 흐름을 소유하고 FastAPI는
기존 API 계약을 유지한다. 운영 정적 파일은 Django 애플리케이션 프로세스가 직접 제공하지
않고 `collectstatic` 산출물을 gateway, 정적 파일 서버 또는 CDN이 제공한다.

```text
Browser
  -> 단일 공개 주소의 gateway
      -> /, UI page route
          -> Django web app
              -> templates/web/
              -> account/session context

      -> /api/auth/*, /admin/*
          -> Django accounts/admin

      -> /django-static/*
          -> collectstatic 산출물 또는 CDN

      -> /api/chat, /api/documents/*, /api/health
          -> FastAPI API
              -> Cache -> LangGraph -> LLM/MCP

FastAPI
  -> /internal/auth/introspect
      -> Django
```

후속 디렉터리 목표:

```text
project/
├── django_app/
│   ├── accounts/               # 계정·인증만 소유
│   ├── web/                    # 사용자 페이지와 UI view
│   │   ├── templates/web/
│   │   ├── static/web/
│   │   ├── views.py
│   │   └── urls.py
│   └── config/
├── app/                        # FastAPI API·Agent·MCP 조율
│   └── web/vendor/             # 전환 기간 Chart.js collectstatic 호환 source
└── staticfiles/                # collectstatic 산출물, Git 제외
```

### 기존 계정 필드 매핑

| legacy `accounts` | Django `accounts_user` | 규칙 |
| --- | --- | --- |
| `id` | `id`, `legacy_account_id` | 공개 `user_id` 보존 |
| `username` | `username` | 기존 문자 범위를 축소하지 않고 128자·unique 유지 |
| `password_hash` | `password` | 기존 고정 scrypt 파라미터를 검증해 보존한 뒤 로그인 성공 시 PBKDF2 재해싱 |
| `display_name` | `display_name` | 그대로 보존 |
| `role` | `role` | `admin`, `hr`, `finance` 외 값이면 migration 중단 |
| `is_active` | `is_active` | 비활성 사용자는 로그인 차단 |
| `last_login_at` | `last_login` | `LEGACY_ACCOUNT_TIME_ZONE` 기준으로 이관 후 Django가 갱신 |
| `created_at` | `date_joined` | 같은 시간대 기준으로 최초 가입 시각 보존 |
| 해당 없음 | `is_staff`, `is_superuser` | 모두 `false`; 애플리케이션 `admin` 역할과 분리 |

## 4. 책임 분리

| 영역 | Django | FastAPI | 기존 도메인 경계 |
| --- | --- | --- | --- |
| 계정 모델·계정 DB | 소유 | 접근 금지 | 해당 없음 |
| 비밀번호 검증 | 소유 | 수행 금지 | 해당 없음 |
| 로그인·로그아웃·현재 사용자 | 소유 | 인증 결과 검증 | 해당 없음 |
| 역할 관리 | 소유 | 역할을 DB 접근 정책으로 변환 | MCP가 최종 권한 재검사 |
| 관리자 화면 | 소유 | 제공하지 않음 | 해당 없음 |
| 채팅 API | 호출하지 않음 | 소유 | Tool 호출 |
| LangGraph·LLM·evidence | 담당하지 않음 | 소유 | Tool 결과 제공 |
| Answer Cache | 담당하지 않음 | 소유 | 해당 없음 |
| 문서 검색·FAISS | 담당하지 않음 | MCP를 통해 호출 | Document Tool 소유 |
| 구매·판매 Text2SQL | 담당하지 않음 | MCP를 통해 호출 | Data Tool 소유 |
| ETL | 요청 경로에서 실행 금지 | 요청 경로에서 실행 금지 | 기존 배치 소유 |
| 사용자 UI | 첫 전환에서는 담당하지 않음; 후속 단계에서 `web` 앱으로 소유 | 후속 전환 전까지 제공, 이후 API 전용 | 해당 없음 |
| UI 정적 자산 | 후속 단계에서 source와 collectstatic 계약 소유 | 전환 관찰 뒤 `/static` mount 제거 | gateway·정적 서버가 산출물 제공 |

## 5. 범위에서 제외하는 항목

다음 항목은 Django 인증 분리의 완료 조건이 아니다. UI 이전은 요구가 확정되어 이 문서의
단계 6으로 편입했고, 나머지는 실제 요구가 확인될 때 별도 계획으로 다룬다.

- 전체 저장소를 `services/` 구조로 재배치
- 문서 메타데이터와 다운로드의 Django 이전
- Django REST Framework 필수 도입
- 사내 OIDC/SSO 신규 도입
- 원격 MCP transport 구현
- Redis answer cache 구현
- 컨테이너·Ingress·분산 tracing 구성
- 오브젝트 스토리지와 서명 URL 도입
- account DB와 document DB 통합

## 6. 단계별 실행 계획

### 단계 0. 현행 계약 기준선 확정

목표: Django 코드 추가 전에 현재 정본과 보존할 계약을 확정한다.

- [x] 현재 FastAPI 진입점과 주요 책임 파악
- [x] Django의 1차 책임을 인증·계정 관리로 제한
- [x] 첫 전환의 비대상 영역 확정
- [ ] `app/api`가 공개 API 정본인지 팀 검토
- [x] `app/routers`, `app/services`, `app/config`, `mcp_server`의 사용 여부 분류
- [x] `BOTH`의 병렬/순차 실행 계약을 코드·문서·테스트에서 통일
- [x] `/api/auth/*`와 `/api/chat` 요청·응답 snapshot 작성
- [ ] 변경 전 전체 테스트 결과 기록

완료 조건:

- 정본 코드 경로와 레거시 후보가 구분돼 있다.
- 변경 중 보존할 HTTP·MCP 계약이 테스트로 고정돼 있다.

### 단계 1. Django 인증 기반 추가

목표: 기존 트래픽에 영향을 주지 않는 Django 인증 애플리케이션을 병행 구성한다.

- [x] Python과 Django 지원 버전 확정
- [x] `django_app/`과 `accounts` app 생성
- [x] `AbstractUser` 기반 사용자 모델 정의
- [x] 사용자 모델을 첫 migration에 포함
- [x] `admin`, `hr`, `finance` 역할 표현 방식 확정
- [x] Django Admin에 사용자 관리 기능 등록
- [x] Django 설정과 환경 변수 경계 정의
- [x] `account_db` migration 소유 방식 확정
- [x] Django 단위 테스트 기본 구조 추가

완료 조건:

- Django가 독립적으로 시작되고 migration을 적용할 수 있다.
- 관리자 화면에서 테스트 계정을 안전하게 관리할 수 있다.
- 이 단계의 병행 도입 시점에는 기존 FastAPI 인증을 건드리지 않는다. 현재 코드는 단계
  4까지 진행돼 FastAPI 인증 라우터 등록이 이미 해제된 상태다.

### 단계 2. 기존 계정과 비밀번호 이관 검증

목표: 기존 사용자가 평문 비밀번호 저장 없이 Django 인증으로 전환될 수 있음을 증명한다.

- [x] 기존 `accounts` 필드와 Django 사용자 필드 매핑표 작성
- [x] 기존 scrypt 문자열 형식의 호환성 테스트 작성
- [x] legacy password hasher 또는 인증 backend 중 한 방식 선택
- [x] 테스트 DB 대상 계정 데이터 migration 작성
- [x] 첫 로그인 후 Django 기본 hasher로 재해싱되는지 검증
- [x] 사용자명·역할·활성 상태·마지막 로그인 시각 비교
- [x] 변환 불가능한 계정의 비밀번호 재설정 절차 정의
- [x] 기존 계정 테이블의 보존·롤백 기간 정의

운영 절차:

- 변환할 수 없는 계정은 migration을 조용히 건너뛰지 않고 중단한다. 기존 계정 저장소의
  승인된 비밀번호 재설정 절차로 지원되는 scrypt 해시를 만든 뒤 migration을 다시
  실행한다. Django 이관과 rollback 관찰 기간이 끝난 뒤의 재설정은
  `python django_app/manage.py changepassword <username>`을 사용하며 평문이나 해시를
  로그·문서에 남기지 않는다.
- legacy `accounts` 테이블과 FastAPI 롤백 코드는 운영 전환 후 최소 14일과 정상 로그인
  피크 주기 1회 중 긴 기간 동안 삭제·schema 변경 없이 보존한다. 정상 Django 경로에서는
  이 테이블을 쓰지 않되, 이전 배포 버전으로 rollback할 때 필요한 조회와
  `last_login_at` 갱신 권한은 rollback 자격 증명에 유지한다. 감사 명령 결과와 인증 지표를
  확인한 뒤 단계 5의 별도 변경으로 제거한다.
- 관찰 기간에는 `LEGACY_AUTH_ROLLBACK_WINDOW=true`로 Django Admin의 계정 추가·삭제와
  이관 계정 변경을 차단한다. 계정 집합·비밀번호·역할·활성 상태를 변경해야 한다면
  legacy rollback을 포기하고 forward fix로 전환할지, 별도 승인된 동기화 절차를 만들지
  먼저 결정한다. 자동
  동기화가 없는 상태에서 설정만 해제해 두 저장소를 분기시키지 않는다.
- migration 전에 기존 DB 백업과 `LEGACY_ACCOUNT_TIME_ZONE` 확인을 먼저 수행한다. data
  migration은 안전하지 않은 부분 롤백을 허용하지 않으므로 실패 시 백업을 기준으로
  원인을 수정한 뒤 새 DB/복구 지점에서 다시 적용한다.
- `python django_app/manage.py audit_legacy_accounts`는 인증 트래픽을 열기 전에 실행하며
  계정 수와 ID·사용자명·표시명·역할·활성 상태·마지막 로그인·가입 시각을 대조하고
  불일치 ID만 출력한다.

완료 조건:

- 기존 계정으로 Django 로그인이 가능하거나 재설정 대상이 명확하다.
- 이관 전후 계정 수와 권한이 검증됐다.
- 실패 시 기존 인증으로 되돌릴 수 있다.

### 단계 3. Django와 FastAPI 사이 인증 계약 확정

목표: FastAPI가 계정 DB를 조회하지 않고 인증된 사용자 컨텍스트를 얻도록 한다.

후보:

| 방식 | 장점 | 단점 | 상태 |
| --- | --- | --- | --- |
| Django 발급 단기 서명 토큰 | FastAPI 요청마다 Django 호출 불필요 | 폐기와 키 관리 정책 필요 | 우선 검토 |
| Django 내부 인증 확인 API | 세션 소유권이 Django에 집중 | 채팅마다 서비스 간 호출과 장애 의존성 추가 | 비교 검토 |

- [ ] 실제 배포 형태와 브라우저 요청 흐름 확인
- [x] 두 방식의 보안·지연시간·운영 복잡도 비교
- [x] 선택 방식을 ADR 또는 본 문서의 결정 기록에 확정
- [x] 사용자 컨텍스트 필드 계약 정의
- [x] 인증 실패, 만료, 변조, 로그아웃 의미 정의
- [x] FastAPI가 Django `SECRET_KEY`나 session 테이블을 직접 사용하지 않음을 확인
- [x] MCP의 역할별 DB 권한 재검사 유지 방안 확인

필수 사용자 컨텍스트:

```json
{
  "user_id": 1,
  "username": "user",
  "display_name": "사용자",
  "role": "admin | hr | finance",
  "allowed_databases": ["document_db"]
}
```

완료 조건:

- 인증 방식과 만료·폐기 정책이 확정돼 있다.
- FastAPI가 신뢰할 수 있는 사용자 컨텍스트만 Graph와 MCP에 전달한다.

선택 방식은 **Django 내부 인증 확인 API**다. 단기 서명 토큰은 요청 지연이 낮지만 별도
폐기 저장소 없이는 로그아웃·비활성화·역할 변경의 즉시 반영 계약을 만족하지 못한다.
FastAPI는 보호 요청마다 `chatbot_session`을 내부 API에 전달하며, Django는 별도
`AUTH_INTROSPECTION_KEY`와 활성 서버 세션을 모두 검증한다. 인증 실패는 `401`, 인증
서비스 장애·잘못된 응답은 `503`이고 account DB로 우회하지 않는다.

### 단계 4. 인증 API와 트래픽 전환

목표: 공개 URL과 응답 형식을 유지하면서 인증 책임을 Django로 전환한다.

- [x] Django에 `/api/auth/login` 구현
- [x] Django에 `/api/auth/logout` 구현
- [x] Django에 `/api/auth/me` 구현
- [x] 기존 `LoginResponse`와 `UserProfile` 호환성 확인
- [x] FastAPI `CurrentUser`를 새 인증 계약으로 교체
- [x] 인증 사용자 정보를 기존 `GraphState.user_context`로 변환
- [x] 역할별 `allowed_databases` 정책 유지
- [ ] 경로 라우팅으로 `/api/auth/*`, `/admin*`, `/django-static/*`를 각각 전환
- [x] 기존 FastAPI 세션 사용자의 재로그인 정책 적용
- [ ] 인증 전환 롤백 절차 검증

기존 FastAPI 서명 쿠키는 Django session 저장소에 존재하지 않으므로 전환 시 한 번의
재로그인을 요구한다. 기존 토큰을 Django 세션으로 변환하거나 두 인증 체계를 동시에
허용하지 않는다.

현재 rollback은 런타임 feature flag가 아니라 배포 버전 되돌리기다. 이전 FastAPI 인증
구성이 포함된 검증된 버전으로 되돌리고 `/api/auth/*` 경로를 FastAPI에 복구한 뒤, 보존한
legacy `accounts` 테이블을 사용한다. 현 배포에서 legacy 라우터만 다시 등록하면 제거된
composition dependency가 없어 동작하지 않으므로 그렇게 복구하지 않는다.

인증 전환 당시 경로 라우팅 계약:

| 경로 | 대상 |
| --- | --- |
| `/api/auth/*`, `/admin`, `/admin/*` | Django |
| `/django-static/*` | `collectstatic` 산출물 정적 서버 |
| 위 경로를 제외한 공개 경로 | FastAPI (`/`, UI asset, chat/document/health, OpenAPI 포함) |
| `/internal/auth/*` | 외부 공개 금지, FastAPI에서 Django로만 호출 |

단계 6의 UI 코드 이전으로 사용자 `/`와 UI 정적 자산의 최종 대상은 Django로 변경됐다.
현재 정본은 단계 6의 `최종 경로 라우팅 계약`을 따른다.

`account_db`는 Django 전용이므로 사용자 컨텍스트의 허용 업무 DB 목록에 포함하지 않는다.

완료 조건:

- Django 로그인 후 FastAPI 채팅을 호출할 수 있다.
- 인증이 없거나 만료·변조된 요청은 `401`이다.
- 권한이 없는 DB 요청은 기존 계약대로 차단된다.
- `/api/chat` 응답 계약에는 변화가 없다.

### 단계 5. 기존 FastAPI 인증 경계 정리

목표: 안정화 기간이 끝난 후 중복 인증 구현과 직접 계정 DB 접근을 제거한다.

- [ ] 운영 또는 스테이징 관찰 기간 완료
- [ ] Django 인증 오류율과 로그인 성공률 확인
- [ ] FastAPI의 legacy 직접 `account_db` adapter 삭제
- [ ] FastAPI의 legacy 로그인·로그아웃·현재 사용자 라우터 소스 삭제
- [ ] 기존 비밀번호·세션 유틸리티 제거
- [ ] 계정 시딩 절차를 Django 관리 명령 또는 migration 경계로 이전
- [ ] 사용되지 않는 인증 설정값 정리
- [ ] 관련 문서·테스트·환경 변수 계약 동기화
- [ ] 레거시 코드 제거 전 import 사용처 재확인

완료 조건:

- 계정·비밀번호·로그인의 쓰기와 검증 책임이 Django에만 있다.
- FastAPI는 계정 DB 또는 Django ORM에 접근하지 않는다.
- 기존 채팅·MCP 테스트와 신규 인증 통합 테스트가 모두 통과한다.

### 단계 6. 사용자 UI를 Django로 이전

목표: UI 고도화에 필요한 템플릿·화면 라우팅·정적 자산 책임을 Django의 별도 `web` 앱으로
이전하고 FastAPI를 채팅·문서·상태 API 전용 서비스로 만든다. 이 단계는 인증 경로 전환과
단계 5의 rollback 관찰이 끝난 뒤 시작한다.

선행 조건:

- 단계 4의 동일 origin gateway와 Django 인증 경로가 운영 또는 스테이징에서 검증됐다.
- 단계 5의 legacy 인증 rollback 관찰이 끝나 UI rollback 범위를 인증 rollback과 분리할 수 있다.
- UI 고도화 요구사항, 지원 브라우저, 접근성·반응형 기준과 배포 주체가 합의됐다.
- `/api/chat`, `/api/documents/*`, `/api/auth/*`의 공개 계약 변경이 필요하면 UI 이전과 분리해
  별도 API 변경으로 검토한다.

구현 계획:

- [x] 현재 `app/web/index.html`, `chat.js`, `style.css`, vendor 자산과 공개 URL inventory 작성
- [x] Django에 인증 앱과 분리된 `web` 앱 및 URL namespace 설계
- [x] HTML을 `django_app/web/templates/web/`로 옮기고 Django template 렌더링 경계 정의
- [x] CSS·JavaScript를 `django_app/web/static/web/` namespace로 이전
- [ ] Chart.js vendor bundle을 `django_app/web/static/web/vendor/`로 이전
- [x] UI가 `/api/auth/*`와 `/api/chat`을 같은 origin 상대 경로로 호출하도록 유지
- [ ] 사용자 문자열·채팅 응답 렌더링의 escaping과 CSP 적용 방안 검토
- [ ] Django page 응답의 cache 정책과 정적 자산의 fingerprint·장기 cache 정책 분리
- [ ] `collectstatic` 산출물을 gateway·정적 서버 또는 CDN이 제공하도록 배포 구성
- [ ] gateway의 `/`와 UI page route를 Django로 전환하고 FastAPI API 경로를 명시적으로 유지
- [x] 기존 `/chat.js`, `/style.css`, `/static/*`는 redirect 없이 제거하고 새 HTML이
  `/django-static/*`만 참조하도록 호환 정책 확정
- [x] Chart.js는 전환 기간에 `app/web/vendor/`에서 Django staticfiles가 수집하도록 보존
- [x] FastAPI의 `/`, UI asset route와 `/static` mount를 제거하고 API 전용 계약으로 변경
- [ ] vendor 이전과 gateway 안정화 뒤 `app/web/` 호환 디렉터리·설정을 제거

최종 경로 라우팅 계약:

| 경로 | 최종 대상 | 비고 |
| --- | --- | --- |
| `/`, 합의된 사용자 page route | Django `web` 앱 | template 응답 |
| `/api/auth/*`, `/admin`, `/admin/*` | Django | 기존 인증·관리 계약 유지 |
| `/django-static/*` | collectstatic 산출물/CDN | `web/`과 `admin/` namespace 분리 |
| `/api/chat`, `/api/documents/*`, `/api/health` | FastAPI | 기존 요청·응답 계약 유지 |
| `/docs`, `/openapi.json` | FastAPI 또는 운영 비공개 | 배포 보안 정책으로 결정 |
| `/internal/auth/*` | 외부 공개 금지 | FastAPI에서 Django로만 호출 |

검증 계획:

- [x] Django page view의 공개 응답과 template/static URL 테스트
- [ ] 로그인, 세션 복원, 로그아웃, CSRF 실패와 만료 세션의 브라우저 흐름 테스트
- [ ] Django UI → FastAPI chat/document API 동일 origin 통합 테스트
- [ ] 표·차트·문서 다운로드·오류·부분 실패 UI 회귀 테스트
- [ ] XSS escaping, CSP, cookie 속성, 내부 URL·비밀정보 비노출 점검
- [ ] 정적 자산 누락, content type, cache header와 collectstatic manifest 검증
- [ ] 데스크톱·모바일 반응형, 키보드 탐색과 핵심 접근성 기준 검증
- [ ] gateway 전환 전후 API latency·오류율과 UI 로딩 지표 비교

전환과 rollback:

1. Django `web` 앱과 template/static source를 추가하고 FastAPI UI route를 제거한다.
2. 외부 기본 경로를 바꾸기 전에 정적 자산을 배포하고 스테이징 gateway에서 Django UI의
   전체 흐름을 검증한다.
3. `/`는 Django, 명시한 `/api/*`는 각 소유 서비스로 보내도록 gateway를 전환한다.
4. 치명적 UI 회귀 시 gateway와 애플리케이션을 UI 이전 직전 검증 버전으로 되돌린다.
   account DB migration과 FastAPI API 계약은 되돌리지 않는다.
5. 관찰 기간과 성공 기준을 충족한 뒤 Chart.js를 Django 정본으로 옮기고
   `app/web/`·`STATICFILES_DIRS` 호환 설정을 제거한다.

완료 조건:

- Django가 사용자 페이지와 UI source의 단일 소유자다.
- FastAPI에는 사용자 HTML·CSS·JavaScript 제공 route가 남아 있지 않다.
- 브라우저 인증, 채팅, 표·차트와 문서 다운로드의 기존 사용자 흐름이 회귀하지 않는다.
- 운영 정적 자산은 `collectstatic` 산출물 또는 CDN에서 제공되고 애플리케이션 프로세스에
  의존하지 않는다.
- UI rollback 절차가 API·계정 migration rollback과 분리되어 검증됐다.

### 단계 7. 로컬 origin gateway 구성

목표: AWS나 운영용 ingress를 도입하기 전에 로컬 reverse proxy를 단일 공개 origin으로
사용하여 Django UI·인증과 FastAPI API의 최종 경로 계약을 실제 브라우저 환경에서
검증한다. 이 단계에서는 애플리케이션을 한 프로세스로 합치거나 공개 API 경로를 변경하지
않는다.

#### 구현 기준

- 로컬 gateway는 현업에서 널리 사용하는 reverse proxy인 **Nginx**를 우선안으로 한다.
  애플리케이션 코드나 Python 의존성에 proxy 책임을 추가하지 않는다.
- 브라우저가 접속하는 유일한 주소는 `http://127.0.0.1:8000`으로 고정한다.
- Django는 `127.0.0.1:8001`, FastAPI는 `127.0.0.1:8002`에서 gateway의 upstream으로만
  실행한다. 두 upstream 포트는 로컬 진단 외에는 사용자 접속 주소로 안내하지 않는다.
- FastAPI의 Django 인증 확인 요청은 공개 gateway를 경유하지 않고
  `http://127.0.0.1:8001/internal/auth/introspect`를 직접 호출한다.
- 로컬 1차 구현은 별도 도메인과 TLS를 도입하지 않는다. HTTPS·도메인·인증서 종료는
  운영 배포 계획에서 별도로 다룬다.
- Nginx 실행 파일과 설정은 Python `requirements.txt`에 포함하지 않는다. 저장소에는
  비밀값이 없는 설정 예시와 실행 안내만 두고, 바이너리 설치 방식은 개발 환경별 절차로
  분리한다.

```text
Browser
  -> http://127.0.0.1:8000 (Nginx)
      -> /, /api/auth/*, /admin/*
          -> Django 127.0.0.1:8001
      -> /api/chat, /api/documents/*, /api/health
          -> FastAPI 127.0.0.1:8002
      -> /django-static/*
          -> staticfiles/ collectstatic 산출물
      -> /internal/auth/*
          -> gateway에서 거부

FastAPI 127.0.0.1:8002
  -> Django 127.0.0.1:8001/internal/auth/introspect
```

#### 경로 및 proxy 계약

| 우선순위 | 공개 경로 | 처리 | 비고 |
| ---: | --- | --- | --- |
| 1 | `/internal/auth`, `/internal/auth/*` | gateway 고정 `404` | Django upstream으로 전달하지 않음 |
| 10 | `/api/chat`, `/api/chat/*` | FastAPI | 원래 path와 query string 유지 |
| 20 | `/api/documents/*` | FastAPI | 다운로드 응답 buffering 정책 검토 |
| 30 | `/api/health` | FastAPI | gateway 포함 로컬 상태 확인에 사용 |
| 40 | `/docs`, `/openapi.json` | FastAPI | 로컬 개발에서만 공개 |
| 50 | `/django-static/*` | Nginx 정적 파일 제공 | `collectstatic` 이후 `staticfiles/` 사용 |
| 기본 | 그 밖의 경로 | Django | `/`, `/api/auth/*`, `/admin/*` 포함 |

proxy는 원래 `Host`를 보존하고 `X-Forwarded-For`, `X-Forwarded-Host`,
`X-Forwarded-Proto`를 gateway가 직접 설정한다. 클라이언트가 보낸 forwarded header는
신뢰하지 않는다. LLM 응답 지연을 고려해 `/api/chat`의 upstream timeout은 일반 페이지보다
길게 두되, 무제한으로 설정하지 않는다. 요청 본문 제한과 timeout의 구체적인 값은 현재
요청 크기 및 성능 측정 결과를 기준으로 구현 시 확정한다.

#### 로컬 환경 변수와 실행 순서

계획상 로컬 설정은 다음 계약을 따른다. 비밀값의 실제 값은 `.env`에만 둔다.

```env
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000
DJANGO_AUTH_INTROSPECTION_URL=http://127.0.0.1:8001/internal/auth/introspect
DJANGO_SERVE_STATIC_FILES=false
AUTH_COOKIE_SECURE=false
```

구현 후 로컬 실행 순서는 다음과 같이 정리한다.

1. Django migration 적용 여부를 확인한다.
2. `collectstatic`으로 `staticfiles/` 산출물을 만든다.
3. Django를 `127.0.0.1:8001`에서 실행한다.
4. FastAPI를 `127.0.0.1:8002`에서 실행한다.
5. Nginx 설정 문법과 upstream 경로를 확인한 뒤 `127.0.0.1:8000`에서 실행한다.
6. 브라우저는 gateway 주소로만 접속한다.

#### 구현 체크리스트

- [x] 로컬 Nginx 설정 파일의 저장 위치와 실행 명령 확정
- [x] Django·FastAPI upstream 포트와 공개 gateway 포트를 문서·설정에서 통일
- [x] 최종 경로 계약에 따른 proxy route 작성
- [x] `/internal/auth/*` 고정 차단과 직접 introspection 경로 분리
- [x] `collectstatic` 산출물의 `/django-static/*` 정적 제공 구성
- [x] forwarded header 덮어쓰기, 요청 크기 제한과 timeout 정책 적용
- [x] Nginx 설정 문법 검사 절차와 시작·종료·재시작 절차 문서화
- [x] README의 로컬 실행 명령을 gateway 기준으로 변경
- [x] direct upstream 주소는 진단용임을 문서에 명시
- [x] 단일 launcher로 Django·FastAPI·Nginx 시작·상태·재시작·종료 자동화
- [ ] 동일 origin 브라우저 회귀 검증 및 rollback 절차 확인

#### 검증 및 rollback 계획

- gateway `/`에서 Django UI와 CSS·JavaScript가 정상 로드되는지 확인한다.
- gateway에서 로그인·`/api/auth/me`·채팅·로그아웃을 연속 수행해 session cookie가
  동일 origin에서 전달되는지 확인한다.
- 문서 다운로드, 표·차트 렌더링과 FastAPI 오류 응답이 proxy 전후 동일한지 확인한다.
- 외부 요청으로 `/internal/auth/introspect`에 접근할 수 없고, FastAPI의 직접 내부 호출은
  성공하는지 각각 확인한다.
- 존재하지 않는 `/api/*`가 Django HTML로 잘못 fallback하지 않는지 확인한다. 필요하면
  구현 시 `/api/` catch-all 정책을 추가하되 기존 공개 계약과 먼저 대조한다.
- gateway 중단 또는 설정 오류 시 Django `:8001`과 FastAPI `:8002`를 직접 호출해 장애
  범위를 진단한다. 이는 임시 진단 절차이며 정상 사용자 흐름의 대체 경로로 사용하지 않는다.
- rollback은 Nginx 설정을 직전 검증본으로 되돌리는 방식으로 수행하며 DB migration이나
  Django/FastAPI 애플리케이션 버전을 함께 되돌리지 않는다.

완료 조건:

- 사용자가 gateway 주소 하나로 UI·인증·채팅·문서 기능을 이용할 수 있다.
- Django와 FastAPI의 공개 경로 및 내부 인증 경계가 최종 라우팅 계약과 일치한다.
- 정적 파일이 Django 개발 서버가 아니라 `collectstatic` 산출물에서 제공된다.
- 내부 introspection 경로가 공개되지 않고 forwarded header 신뢰 경계가 명확하다.
- 로컬 실행·검증·rollback 절차가 README와 본 문서에 일치하게 기록돼 있다.

## 7. 테스트 계획

### Django 단위·통합 테스트

- [x] 사용자 생성과 비밀번호 검증
- [x] 비활성 사용자 로그인 차단
- [x] 역할별 권한 매핑
- [x] Django Admin 접근 제한
- [x] legacy scrypt 로그인
- [x] 로그인 성공 후 비밀번호 자동 재해싱
- [x] login/logout/me 요청·응답 계약
- [x] strict JSON 입력, 인증 응답 no-cache와 고정 세션 만료 설정
- [x] rollback 관찰 중 Admin 계정 추가·삭제·이관 계정 변경 잠금

### FastAPI 회귀 테스트

- [x] 인증 정보 없음 → `401`
- [x] 변조된 인증 정보 → `401`
- [x] 만료된 인증 정보 → `401`
- [x] 로그아웃 후 인증 정보 재사용 → `401`
- [x] HR의 구매·판매 접근 → `403`
- [x] Finance/Admin의 허용 도메인 접근 → 성공
- [x] 동일 사용자 answer cache 재사용
- [x] 서로 다른 사용자의 answer cache 격리
- [x] 기존 LangGraph·MCP·evidence 테스트 유지
- [x] Django 내부 응답의 타입·role·opaque session ID 형식 오류 → `503`

### 서비스 간 계약 테스트

- [x] Django login → FastAPI chat → fake MCP → `ChatResponse`
- [x] Django 역할 변경 또는 비활성화가 정해진 정책에 따라 반영됨
- [x] 기존 HTTP 오류 코드와 공개 메시지 호환
- [x] 내부 비밀번호, 인증 정보와 파일 경로가 응답·로그에 노출되지 않음
- [x] Django ASGI 세션과 FastAPI ASGI 보호 API의 in-process 연결

구조 재검토 전 기준선 실행 결과 (`.venv`, Python 3.11.9):

- `.venv\Scripts\python.exe django_app\manage.py check --settings=django_app.config.test_settings`: 이상 없음
- `.venv\Scripts\python.exe django_app\manage.py makemigrations --check --dry-run --settings=django_app.config.test_settings`: 변경 없음
- `.venv\Scripts\python.exe -m pytest tests\django -q`: 5 passed
- `.venv\Scripts\python.exe -m pytest tests\unit -q`: 351 passed, 26 skipped
- `.venv\Scripts\python.exe -m pytest tests\integration -q`: 15 passed
- `.venv\Scripts\python.exe -m pytest -q`: 393 passed, 27 skipped

2026-08-20 정적 재검토 뒤 실제 account DB migration과 legacy 계정 3건 감사를 완료했다.
Django UI 코드 이전 뒤 system check, migration·collectstatic dry-run과 전체 pytest
`402 passed, 27 skipped`를 확인했다. reverse proxy와 실제 브라우저 흐름은 검증하지
않았다. 로컬 gateway 설정 추가 뒤 Django system check와 실제 collectstatic(130개 파일),
Nginx 설정 검사, launcher 기반 전체 기동·HTTP smoke·전체 종료를 확인했다. 실제 로그인과
채팅을 포함한 브라우저 회귀 검증은 아직 보류했다.

## 8. 진행 현황 요약

| 단계 | 상태 | 완료 항목 | 전체 항목 | 차단 요인 | 다음 작업 |
| --- | --- | ---: | ---: | --- | --- |
| 0. 현행 기준선 | 진행 중 | 6 | 8 | 팀 검토·변경 전 테스트 기록 보류 | 계약 문서 소유자 검토 |
| 1. Django 기반 | 완료 | 9 | 9 | 없음 | 인증 경로 전환 관찰 |
| 2. 계정 이관 | 완료 | 8 | 8 | 없음 | rollback 관찰 기간 동안 legacy 원본 보존 |
| 3. 인증 계약 | 진행 중 | 6 | 7 | 실제 reverse proxy/Ingress 형태 미확인 | 배포 경로 검토 |
| 4. 트래픽 전환 | 진행 중 | 8 | 10 | 외부 경로 라우팅·rollback 검증 필요 | reverse proxy/Ingress 경로 전환 |
| 5. 기존 경계 정리 | 미착수 | 0 | 9 | 관찰 기간 전 | 운영 관찰 후 legacy 제거 |
| 6. Django UI 이전 | 진행 중 | 9 | 22 | 실제 gateway·브라우저·정적 배포 미검증 | gateway 전환과 브라우저 회귀 검증 |
| 7. 로컬 origin gateway | 진행 중 | 10 | 11 | 로그인·채팅 브라우저 회귀 검증 보류 | 동일 origin 브라우저 회귀와 rollback 검증 |

상태 정의:

- `미착수`: 구현이나 검증을 시작하지 않았다.
- `진행 중`: 하나 이상의 체크리스트가 완료됐지만 단계 완료 조건을 충족하지 못했다.
- `차단`: 외부 결정이나 선행 작업 없이는 진행할 수 없다.
- `완료`: 체크리스트와 단계 완료 조건을 모두 충족하고 검증 근거가 기록됐다.

## 9. 결정 기록

| 날짜 | 결정 | 근거 | 영향 |
| --- | --- | --- | --- |
| 2026-08-20 | Django 1차 범위를 인증·계정 관리로 제한 | 문서·MCP·ETL은 이미 별도 경계를 가지며 Django 이전 요구가 확인되지 않음 | 변경 범위와 회귀 위험 감소 |
| 2026-08-20 | 기존 FastAPI 디렉터리를 초기 전환에서 이동하지 않음 | 기능 변경과 대규모 rename을 분리해야 검토·롤백이 쉬움 | `django_app/`만 병행 추가 |
| 2026-08-20 | 정적 UI와 문서 다운로드는 첫 전환에서 FastAPI에 유지 | Django 기능을 필요로 하지 않으며 공개 계약 변경을 줄일 수 있음 | 인증 경로만 우선 전환 |
| 2026-08-20 | 서비스 간 인증 방식은 구현 전에 비교 후 확정 | 배포 형태와 운영 요구가 확인되지 않은 상태에서 JWT·세션 방식을 고정할 근거가 부족함 | 단계 3을 결정 게이트로 설정 |
| 2026-08-20 | Django 5.2 LTS 사용 | Python 3.13 지원과 장기 보안 지원, custom user 첫 migration 공식 지침 | `Django>=5.2.17,<5.3` 계약 추가 |
| 2026-08-20 | Django 내부 인증 확인 API 선택 | 로그아웃·비활성화·역할 변경을 즉시 반영하고 세션 DB·SECRET_KEY 공유를 피함 | FastAPI 보호 요청에 내부 호출 1회 추가 |
| 2026-08-20 | 애플리케이션 `admin` 역할과 Django 관리자 권한 분리 | 기존 역할 이관만으로 관리자 화면 권한을 부여하면 권한 상승 위험 | 이관 사용자의 `is_staff`, `is_superuser`는 `false` |
| 2026-08-20 | 기존 계정 PK와 scrypt 해시를 보존 이관 | 공개 `user_id` 호환과 평문 없는 점진 전환 필요 | 첫 성공 로그인에서 PBKDF2로 자동 재해싱 |
| 2026-08-20 | `BOTH`는 실제 코드의 병렬 fan-out을 정본으로 확정 | Document와 Database가 독립 state 필드에 쓰며 현재 코드가 병렬 실행 | architecture/interface/test 문서 동기화 |
| 2026-08-20 | `account_db`를 FastAPI/MCP 허용 DB 목록에서 제외 | 계정 저장소는 Django가 단독 소유하며 채팅 도메인 권한이 아님 | admin/hr profile과 RBAC 계약 수정 |
| 2026-08-20 | Django Admin 정적 파일은 `/django-static/*`로 분리 | FastAPI UI `/static/*`와 충돌 없이 `collectstatic` 산출물을 배포해야 함 | gateway/정적 서버 경로 계약 추가 |
| 2026-08-20 | legacy 시각은 명시한 DB 시간대로 해석하고 data migration은 irreversible로 표시 | naive `DATETIME`의 시간 왜곡과 부분 rollback 후 재적용 충돌 방지 | 사전 백업·시간대 확인·이관 직후 감사 필수 |
| 2026-08-20 | rollback 관찰 중 Django Admin 계정 mutation 잠금 | 신규/변경 계정이 legacy snapshot과 달라지면 이전 FastAPI 인증으로 안전하게 복귀할 수 없음 | `LEGACY_AUTH_ROLLBACK_WINDOW`를 종료 승인 전까지 유지 |
| 2026-08-20 | UI 고도화 시 사용자 UI를 Django의 별도 `web` 앱으로 이전 | 템플릿·세션 기반 화면과 정적 자산 운영 책임을 한 경계에 모으고 FastAPI를 API 전용으로 유지 | 인증 안정화 뒤 단계 6에서 병행 배포·gateway 전환·독립 rollback 수행 |
| 2026-08-20 | 로컬 origin gateway는 Nginx로 구성하고 공개 `:8000`, Django `:8001`, FastAPI `:8002`로 분리 | 동일 origin 브라우저 흐름을 운영과 유사한 reverse proxy 경계에서 검증하면서 애플리케이션 코드와 Python 의존성에 gateway 책임을 넣지 않기 위함 | `/internal/auth/*` 공개 차단, collectstatic 제공, forwarded header·timeout 정책을 단계 7에서 구현 |

## 10. 진행 기록 작성 규칙

체크리스트를 변경할 때 다음 내용을 함께 갱신한다.

1. `진행 현황 요약`의 완료 수, 상태, 차단 요인과 다음 작업
2. 관련 단계의 체크박스
3. 새로운 구조·보안 결정이 있다면 `결정 기록`
4. 실제 작업 이력은 [진행 이력 운영 가이드](progress/README.md)에 따라 `docs/progress/backend/` 또는 `docs/progress/integration/`의 날짜별 파일에 기록
5. 테스트를 실행했다면 명령, 통과·실패·skip 수와 실제 외부 서비스 사용 여부 기록

문서의 체크박스는 코드 존재 여부가 아니라 해당 단계의 완료 조건과 검증 근거가 충족됐을 때만 완료 처리한다.

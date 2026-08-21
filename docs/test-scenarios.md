# 테스트 시나리오 및 완료 기준

## 목적

현재 자동화된 검증, 로컬 인프라를 선택적으로 사용하는 검증, 아직 구현되지 않은 목표
수용 검증을 구분한다. fake 기반 API→Graph 흐름 통과는 원격 MCP나 실제 MySQL·FAISS
통합 완료를 뜻하지 않는다.

## 표준 실행 명령

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest tests\unit
.venv\Scripts\python.exe -m pytest tests\integration
.venv\Scripts\python.exe -m pytest tests\django
.venv\Scripts\python.exe -m pytest tests\unit\test_etl.py
```

2026-08-20 Django UI 이전 뒤 `.venv` 전체 테스트는 `402 passed, 27 skipped`다. Django
system check, migration dry-run과 collectstatic dry-run도 통과했다. fake/mock 중심의 이
결과를 실제 gateway·브라우저·외부 MySQL·Redis·FAISS 통합 성공으로 해석하지 않는다.

먼저 `requirements.txt`를 설치해야 한다. `pytest.ini`는 `tests/`, `test_*.py`, async auto
mode와 `unit`/`integration` marker를 정의한다. 현재 대부분의 unit 파일은 marker가 아니라
경로로 구분하므로 `tests/unit`, `tests/integration` 경로 명령을 기준으로 사용한다.

실제 로컬 MySQL을 사용하는 선택 테스트는 명시적으로 다음 환경 변수를 설정한 경우에만
실행한다.

```powershell
$env:RUN_LOCAL_MYSQL_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests\unit\test_sales_text2sql.py tests\unit\test_purchase_text2sql.py tests\unit\test_agent.py
```

이 테스트는 로컬 설정과 데이터에 의존하므로 기본 CI 성격의 결과와 분리해 보고한다.

## 현재 자동 검증 범위

### API·인증·UI

| 테스트 | 검증 내용 |
|---|---|
| `tests/unit/test_api.py` | liveness health, FastAPI UI route 미제공, 문서 ID 다운로드, cache hit/miss, 요청·timing 헤더, 입력 검증, 공개 오류 매핑 |
| `tests/unit/test_auth.py` | Django 인증 gateway의 401/503, 역할별 DB 정책, HR 데이터 질의 차단, 사용자별 cache 격리 |
| `tests/unit/test_auth_gateway.py` | 내부 키·세션 쿠키 전달, 인증 실패와 잘못된 Django 응답 매핑 |
| `tests/django/test_auth_api.py` | CSRF, login/me/logout, 내부 인증 확인, 비활성 계정, legacy scrypt 자동 재해싱·파라미터 검증, 관리자 필수 필드·권한 분리·롤백 관찰 잠금 |
| `tests/django/test_web_ui.py` | Django 루트 template, HTML no-cache, UI·Chart.js staticfiles 발견과 로컬 정적 route 응답 |
| `tests/unit/test_web_auth.py` | 로그인 상태 복원, CSRF 전달, logout 정리, 로컬 Chart.js, 차트 크기, 다운로드 파일명 처리 |
| `tests/unit/test_performance.py` | `Server-Timing` 파싱과 nearest-rank p95 계산 |

### Agent·캐시

| 테스트 | 검증 내용 |
|---|---|
| `tests/unit/test_agent.py` | route/data domain, 병렬 BOTH 병합, 부분 실패, evidence 상태·정책·충돌, 1회 재조회, LLM evidence sanitization, 출처·표 직렬화 |
| `tests/unit/test_query_expansion.py` | 문서 동의어 확장, 낮은 직접 점수에서만 추가 조회, semantic document query 사용 |
| `tests/unit/test_cache.py` | 질문·대화 문맥·인증 사용자·version 재료별 키 변화, Graph 밖 cache service |

`query_classification.py`의 일반 지식·실시간성 fallback은 직접 상태를 구성한 단위 테스트가
있다. 기본 router가 `query_labels`를 자동 주입하는 통합 테스트는 없으며 실제 코드에도
연결되지 않았다.

### Document RAG

| 테스트 | 검증 내용 |
|---|---|
| `tests/unit/test_document_mcp.py` | 활성 문서 전체 허용 목록, ID별 활성 다운로드 매핑, DB→RAG 순서, 문서 DB 오류 분류, 파일 파싱 캐시 |
| `tests/unit/test_document_mcp_eval.py` | fixture FAISS 검색 품질, 정확한 정책 용어의 어휘 검색 보완 |
| `tests/unit/test_ingestion.py` | PDF/TXT/Markdown 로딩, 안정적 문서 ID, 청킹·페이지, 임베딩, 인덱스·metadata·version 생성 |

문서 MCP 단위 테스트는 실제 사내 DB나 원천 문서를 사용하지 않는다. 작은 공개 fixture와
임시 인덱스를 사용한다.

### Data MCP·Text2SQL·ETL

| 테스트 | 검증 내용 |
|---|---|
| `tests/unit/test_data_mcp.py` | Tool dispatch, envelope/domain 검증, metadata 보존, 빈 결과·오류 분류, SQL 사전 차단, Tool 등록 |
| `tests/unit/test_purchase_text2sql.py` | 구매 허용 View·지표, API key 없음, SQL guard/LIMIT, EXPLAIN 실패 1회 재작성, chart hint, opt-in golden case |
| `tests/unit/test_sales_text2sql.py` | 판매 허용 View·지표, API key 없음, SQL guard/LIMIT, EXPLAIN 실패 1회 재작성, chart hint, opt-in golden case |
| `tests/unit/test_etl.py` | 공통 transform 중복 제거 계약 |

구매·판매 Text2SQL 기본 테스트는 LLM과 MySQL을 monkeypatch해 결정적으로 실행한다.
`RUN_LOCAL_MYSQL_TESTS=1` golden case만 실제 로컬 OpenAI/MySQL 의존성을 사용할 수 있다.

### fake 통합 테스트

| 테스트 | 검증 내용 |
|---|---|
| `tests/integration/test_chat_document_flow.py` | 인증→Chat API→Graph→fake Document Tool→문서 카드 직렬화 |
| `tests/integration/test_chat_data_flow.py` | 구매·판매 단일 선택과 모호한 질의의 두 Tool 순차 호출 |
| `tests/integration/test_cache_flow.py` | BOTH 성공 cache short-circuit, 한쪽 부분 실패, 전체 Tool 실패 |
| `tests/integration/test_chat_error_flow.py` | 빈 결과의 1회 재조회·HTTP 200, query/malformed/timeout 오류 매핑 |
| `tests/integration/test_django_fastapi_auth_flow.py` | Django login/session → FastAPI chat → fake MCP, 역할·활성 상태·세션 삭제의 즉시 반영 |
| `tests/integration/test_etl_mysql_flow.py` | placeholder 한 건만 존재 |

앞의 네 chat/cache 통합 파일은 `FakeMCPPort`, fake LLM, 인증 gateway·메모리 캐시 대역을
사용한다. Django/FastAPI 인증 흐름 테스트는 두 ASGI 앱을 in-process로 연결하지만
Django test DB와 fake MCP를 사용한다. 어느 테스트도 외부 MCP 프로세스, 실제 OpenAI,
운영 MySQL·Redis·FAISS를 호출하지 않는다.

## 현재 자동 테스트가 보장하는 계약

### TS-A01: 인증과 RBAC

- 보호 API는 Django가 유효하다고 확인한 서버 세션 없이는 `401`이다.
- Django 인증 확인 서비스 장애나 잘못된 응답은 `503`이며 FastAPI가 account DB로 우회하지 않는다.
- 로그인·로그아웃은 CSRF 검증을 통과해야 하고 로그아웃한 세션 쿠키는 재사용할 수 없다.
- 세션은 고정 만료이며 내부 인증 확인 요청으로 만료가 연장되지 않는다.
- `hr`는 문서 DB만 사용하며 구매·판매 질의는 Tool 실행 전에 `403 FORBIDDEN`이다.
- `admin`, `finance`의 허용 DB는 서버 정책이 계산한다.
- `account_db`는 Django 전용이며 FastAPI/MCP의 허용 DB 목록에 포함되지 않는다.
- 사용자·세션·역할·허용 DB가 다르면 answer-cache 키가 다르다.
- rollback 관찰 설정이 켜진 동안 Django Admin은 계정 추가·삭제와 이관 계정 변경을 막는다.

### TS-A01-UI: 사용자 화면 소유권

- `GET /`의 사용자 HTML은 Django `web` 앱이 제공하며 HTML 응답은 no-cache다.
- CSS·JavaScript와 Chart.js는 `/django-static/web/*` 경로로 해석된다. production
  `collectstatic` manifest는 파일 내용 hash가 포함된 URL을 반환한다.
- FastAPI의 `/`, `/chat.js`, `/style.css`는 `404`이며 FastAPI가 UI를 다시 소유하지 않는다.
- UI의 인증·채팅·문서 호출은 같은 origin 상대 `/api/*` 경로를 유지한다.
- Django가 발급한 유효 세션은 `/api/chat`과 `/api/documents/download`에서 FastAPI의
  내부 인증 확인을 통과하며, gateway는 `/api/auth/*`를 Django, 두 API를 FastAPI로 전달한다.
- UI는 API table을 escape한 HTML 표와 Chart.js 차트로 렌더링하고, 문서 다운로드는
  same-origin `/api/documents/download` URL만 사용한다. `401`은 로그인 화면으로 전환하며,
  `PARTIALLY_SUPPORTED`·`INSUFFICIENT` 등 근거 상태와 오류는 사용자 안내로 표시한다.
- 사용자 UI HTML은 same-origin CSP, `X-Frame-Options: DENY`, `nosniff`를 적용한다.
  세션 쿠키는 `HttpOnly`, `SameSite=Lax`를 사용하며 HTTPS 환경에서 `Secure` 설정을 따른다.
  `/internal/auth/*`는 public gateway에서 `404`이고 응답에 내부 인증 key·원본 `file_path`를
  포함하지 않는다.

### TS-A02: 라우팅과 조회 선택

- 질문은 `GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH` 중 하나로 분류된다.
- 명확한 구매/판매 질문은 해당 Tool만 호출한다.
- 구매·판매가 모두 있거나 모호한 DB 질문은 구매 후 판매 순서로 두 Tool을 호출한다.
- `BOTH`는 Document와 Database를 병렬 실행하고 evidence 유형을 분리한다.

### TS-A03: 문서 검색과 출처

- 문서 DB 제목과 질문의 단순 문자열 일치로 허용 문서를 줄이지 않는다.
- DB의 활성 `document_id` 허용 목록 밖 청크는 검색 결과에 포함하지 않는다.
- 문서 DB 연결 장애는 일반 내부 오류가 아니라 조회 불가로 분류한다.
- 문서 카드는 같은 ID의 페이지·발췌문을 병합하고 `file_path`를 노출하지 않는다.
- 다운로드는 활성 문서 ID 매핑만 사용한다.

### TS-A04: Data Tool 안전성

- 비어 있거나 너무 긴 질문, `NO_SQL`, 실제 빈 행은 원인 안내와 `NO_RESULT`가 된다.
- SQL은 단일 `SELECT`/`WITH`, 도메인 허용 View, `LIMIT <= 200`만 허용한다.
- 주석, 다중 문장, 쓰기·DDL, 미허용 테이블은 DB 연결 전에 거부한다.
- 첫 SQL 또는 EXPLAIN 실패 시 한 번만 재작성하고 두 번째 실패는 `QUERY_ERROR`다.

### TS-A05: evidence 평가

- 문서 점수·관련성·신뢰도·metadata·freshness 정책을 통과한 근거만 채택한다.
- 한 Tool 실패와 다른 유효 근거가 함께 있으면 `PARTIALLY_SUPPORTED`다.
- 명시적 상충만 `CONTRADICTED`이며 LLM을 호출하지 않는다.
- `INSUFFICIENT`는 원래 route를 한 번만 재조회한다.
- 두 번째도 부족하면 HTTP 200, `evidence_status=INSUFFICIENT`, 빈 sources/tables와 안전한 안내다.

### TS-A06: 캐시

- hit는 Graph, LLM, MCP를 모두 건너뛴다.
- 문서 인덱스 버전이 응답되면 앱의 cache-key context를 갱신한다.
- `SUPPORTED`와 `GENERAL`만 저장하며 부분·부족·상충 결과는 저장하지 않는다.
- 인증 사용자가 다르면 같은 질문도 cache를 공유하지 않는다.

### TS-A07: 공개 오류와 관측성

- `INVALID_INPUT`, `FORBIDDEN`, `QUERY_ERROR`, `INTERNAL_ERROR`, `TIMEOUT`을 HTTP 계약에 맞게 구분한다.
- malformed provider payload와 provider 내부 메시지는 공개하지 않는다.
- 응답에 안전한 `X-Request-ID`, `Server-Timing`을 제공한다.
- 로그 formatter가 공통 필드를 채우고 handler를 중복 등록하지 않는다.

## 선택 실행 검증

### TS-L01: 로컬 Text2SQL golden case

준비 조건:

- `RUN_LOCAL_MYSQL_TESTS=1`
- 유효한 OpenAI 설정
- 구매·판매 DB와 read-only 계정
- schema가 광고하는 허용 View와 fixture 질문에 대응하는 데이터

완료 조건:

- LLM SQL이 허용 View와 기대 지표를 사용한다.
- EXPLAIN과 read-only 조회가 성공한다.
- 원천 테이블, 쓰기 SQL, 범위 밖 View를 사용하지 않는다.

`tests/unit/test_agent.py`의 opt-in sales 경로는 same-process Data Tool 뒤의 판매 조회를
검증한다. 구매, Document MCP, ETL 전체 통합까지 증명하지 않는다.

### TS-L02: 문서 fixture 검색 품질

`tests/unit/test_document_mcp_eval.py`는 임시 FAISS 인덱스에서 정의된 RAG case가 기대 문서를
찾는지 확인한다. 이는 회귀 기준이지 실제 사내 문서 전체의 정답률 보장이 아니다.

## 아직 자동화되지 않은 목표 수용 테스트

### TS-T01: 실제 문서 전체 흐름

```text
실제 document_paths
  -> 등록된 원문 파일
  -> 배치 FAISS 인덱스
  -> FastAPI in-process Document Tool
  -> evidence 평가
  -> 문서 카드와 다운로드
```

완료 조건:

- `admin`/`hr`가 실제 사내 문서 질문에서 기대 문서를 찾는다.
- DB의 활성 ID, 인덱스 metadata, 다운로드 파일이 서로 일치한다.
- 비활성 ID·임의 ID·삭제 파일은 다운로드되지 않는다.
- 질문·응답·로그에 내부 경로나 비밀정보가 없다.

### TS-T02: 실제 구매·판매 흐름

- `finance`가 실제 read-only 계정으로 구매와 판매 질문을 각각 조회한다.
- 반환 수치를 기준 SQL 결과와 대조한다.
- `hr`는 두 DB 모두 거부된다.
- 허용 View 외의 객체와 원천 개인정보 컬럼은 접근할 수 없다.

### TS-T03: ETL 멱등성·이력

- 동일 원천 workbook으로 구매·판매 ETL을 두 번 실행해 업무 행이 중복 증가하지 않는다.
- 필수 컬럼, 타입, PK/참조, 금액 계산, 중복 검증 실패 시 적재를 중단한다.
- 처리 행 수와 검증 결과가 도메인 ETL 로그에 남는다.
- LLM 증강 데이터는 원천과 구분되고 실제 실적으로 오인될 필드가 없다.

`tests/integration/test_etl_mysql_flow.py`가 실제 테스트로 교체되기 전에는 이 항목을 완료로
표시하지 않는다.

### TS-T04: 재인덱싱과 cache freshness

- 문서 추가·교체 후 재인덱싱하면 `index_version`이 바뀐다.
- 다음 문서 응답과 cache key가 새 version을 사용한다.
- 오래된 문서 답변이 다시 사용되지 않는다.

현재 프로세스 내 인덱스 store cache를 실행 중 재인덱싱과 자동 동기화하는 end-to-end
테스트는 없다.

### TS-T05: DB freshness와 무효화

- ETL 완료 후 `database_freshness_bucket` 또는 source version이 갱신된다.
- 이전 DB 답변 cache가 재사용되지 않는다.
- 다중 앱 인스턴스에서도 무효화가 일관된다.

현재 DB freshness는 `unknown`, 저장소는 `MemoryCache`이므로 미구현이다.

### TS-T06: 원격 MCP transport

- FastAPI가 `DOCUMENT_MCP_URL`, `DATA_MCP_URL`로 실제 MCP 서버를 호출한다.
- 사용자 컨텍스트와 RBAC가 신뢰 가능한 방식으로 전달된다.
- timeout, malformed envelope, 서버 중단이 현재 HTTP 계약으로 정규화된다.
- 다운로드 해석을 원격 경계로 옮길 경우 내부 경로가 네트워크 공개 payload가 되지 않는다.

현재 Host는 URL을 사용하지 않으므로 미구현이다.

### TS-T07: 통합 초기화 runbook

깨끗한 Windows/MySQL 환경에서 프로젝트 루트 명령으로 다음을 검증해야 한다.

- `.env`가 올바른 프로젝트 위치에 생성되고 `Settings` 필수 필드를 충족한다.
- account/document/purchase/sales SQL 파일 경로가 모두 해석된다.
- 문서 등록·인덱싱과 구매·판매 ETL 명령이 실제로 실행된다.
- Django migration·감사와 관리자 생성 순서가 명확하다.
- 재실행이 기존 데이터와 설정을 손상하지 않는다.

현재 저장소에는 `scripts/setup_all.py`가 없으며 README와 도메인별 스크립트를 따라
수동으로 실행한다. `scripts/seed_accounts.py`는 legacy rollback 전용이므로 Django 계정
초기화 단계에 포함하지 않는다. 통합 runbook이나 자동화가 실제 환경에서 검증되기 전에는
이 수용 테스트를 통과한 것으로 간주하지 않는다.

### TS-T08: readiness와 Redis

- MySQL, FAISS, LLM/MCP, Redis 상태를 비밀값 없이 확인하는 readiness 정책이 있다.
- Redis adapter가 MemoryCache와 같은 TTL·복사·멱등 삭제 의미를 제공한다.
- Redis 장애 시 운영 정책이 명확하다.

현재 `/api/health`는 liveness만 제공하고 `RedisCache`는 placeholder다.

## 공통 수용 데이터

| 구분 | 최소 준비물 |
|---|---|
| 계정 | `admin`, `hr`, `finance`, 비활성 계정 각 1개 |
| 문서 DB | 활성 문서 3건 이상, 비활성 문서 1건, 존재하지 않는 경로 1건 |
| 문서 파일 | PDF/TXT/Markdown 각 1건 이상, 페이지 metadata 포함 |
| 구매 | 공급업체·월·발주 상태·미지급금을 검증할 소형 fixture |
| 판매 | 고객·월·주문 상태·미수금을 검증할 소형 fixture |
| 질문 | GENERAL, DOCUMENT, 구매, 판매, 모호한 DATABASE, BOTH, 권한 거부, 빈 결과, 상충 질문 |

실제 Kaggle 원천과 사내 문서는 자동 테스트 fixture에 직접 복사하지 않는다. 재배포 가능한
비식별 소형 fixture만 `tests/fixtures/`에 둔다.

## 발표 필수 시나리오

| 번호 | 사용자 | 질문 | 검증 포인트 |
|---|---|---|---|
| D01 | `hr` | 사내 규정 질문 | 문서 route, 출처 카드, 원문 다운로드 |
| D02 | `finance` | 공급업체별 구매 질문 | 구매 Tool, SQL·표, 수치 대조 |
| D03 | `finance` | 고객별 판매 질문 | 판매 Tool, SQL·표·차트 |
| D04 | `finance` | 규정+매출 복합 질문 | 병렬 BOTH, 도메인별 근거, 부분 실패 |
| D05 | 동일 사용자 | D04 반복 | cache hit와 MCP/LLM 미호출 |
| D06 | `hr` | 구매·판매 질문 | `403 FORBIDDEN`, DB 호출 차단 |

## 완료 판정

- 관련 unit 테스트와 fake integration 테스트가 통과한다.
- 외부 인프라를 사용한 항목은 실행 조건과 결과를 별도로 기록한다.
- placeholder와 skip을 실제 통합 성공으로 보고하지 않는다.
- `interface.md`의 route, payload, envelope, HTTP 오류, 출처·표 계약을 지킨다.
- 내부 경로·질문 원문·전체 근거·API key·DB 비밀번호가 응답과 로그에 없다.
- `git diff --check`와 `git status --short`로 원천 데이터, 인덱스, 로그, 비밀 파일이
  변경되지 않았음을 확인한다.

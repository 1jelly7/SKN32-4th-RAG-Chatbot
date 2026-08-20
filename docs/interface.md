# HTTP·MCP 인터페이스 계약

## 목적

Django 인증 서비스, FastAPI/LangGraph Host, MCP Client, 문서·데이터 Tool service
사이의 현재 호출 형식과 공개·내부 HTTP 응답을 정의한다. 구현 정본은
`django_app/accounts/views.py`, `app/auth/gateway.py`, `shared/auth_policy.py`,
`app/schemas/`, `app/mcp/client.py`, `mcp_servers/*/server.py`다.

- Host와 Agent는 문서 파일·FAISS·업무 DB에 직접 접근하지 않는다.
- 캐시는 Graph 밖의 `app/cache/`에서만 처리한다.
- Tool payload는 서버가 복원한 사용자 컨텍스트를 사용하며 클라이언트 역할 값을 신뢰하지 않는다.
- Tool 결과는 Pydantic envelope 검증과 evidence 평가를 통과한 뒤에만 답변에 사용한다.

## 현재 transport 범위

운영 앱의 기본값은 `MCPClient(InProcessMCPPort())`다. Tool과 같은 async 계약을 사용하지만
별도 프로세스나 `.env`의 MCP URL로 HTTP 연결하지 않는다.

| 경계 | 현재 상태 |
|---|---|
| `search_documents` | in-process Host dispatch와 독립 Document MCP 서버 등록 모두 존재 |
| `query_purchase`, `query_sales` | 공통 Data MCP service와 독립 Data MCP 서버 등록 모두 존재 |
| `resolve_document_download` | Host의 in-process 전용 dispatch; 독립 Document MCP 서버에는 미등록 |
| 원격 MCP URL transport | 미구현 |

따라서 독립 MCP 서버를 실행할 수 있다는 사실만으로 FastAPI가 그 서버 URL을 사용한다고
해석하면 안 된다.

## 인증된 사용자 컨텍스트

보호 HTTP API는 Django가 발급한 불투명한 `chatbot_session` 세션 키를 내부 인증
인트로스펙션으로 검증한 뒤 다음 컨텍스트를 서버에서 복원한다.

```json
{
  "user_id": 1,
  "username": "user",
  "display_name": "사용자",
  "session_id": "server-session-id",
  "role": "admin | hr | finance",
  "allowed_databases": ["document_db"]
}
```

이 값은 캐시 격리와 Tool RBAC에 사용된다. `query_purchase`, `query_sales`의 독립 MCP Tool
서명은 `user_context`를 필수 입력으로 받는다. `search_documents` 독립 MCP Tool은 현재
`query`, `top_k`만 받으며, 운영 Host의 in-process dispatch가 호출 전에 문서 DB 권한을
검사한다. 원격 transport를 구현할 때는 Document MCP에도 검증 가능한 사용자 컨텍스트
전달 계약을 먼저 추가해야 한다.

## 공통 Tool envelope

### 성공

```json
{
  "status": "success",
  "domain": "document | purchase | sales | both",
  "message": null,
  "data": [],
  "sources": [],
  "metadata": {}
}
```

### 실패

```json
{
  "status": "error",
  "domain": "document | purchase | sales | both",
  "message": "사용자에게 표시 가능한 오류 설명",
  "error_code": "FORBIDDEN | INVALID_INPUT | NO_RESULT | QUERY_ERROR | EVIDENCE_INSUFFICIENT | INTERNAL_ERROR",
  "data": [],
  "sources": [],
  "metadata": {}
}
```

`TIMEOUT`은 Tool envelope 코드가 아니다. Host가 transport timeout을
`MCPTimeoutError`로 분류한 뒤 공개 HTTP 오류 코드 `TIMEOUT`으로 변환한다. envelope의
상태·필수 필드·domain이 잘못된 응답은 `MCPMalformedPayloadError`로 처리하며 provider의
원문 오류를 공개하지 않는다.

## Tool 1: 문서 검색

- Tool 이름: `search_documents`
- 구현: `mcp_servers/document_tools/`, `app/mcp/client.py`
- 용도: 규정·정책·가이드 등 등록된 사내 문서 근거 검색
- 금지: 업무 수치 조회, 임의 파일 경로 접근, 원문 파일 수정

### 입력

```json
{
  "query": "휴가 신청 절차를 알려줘",
  "top_k": 5
}
```

`query`는 공백이 아니어야 하고 `top_k`는 양수 정수여야 한다. 독립 서버와 service의
기본값은 5지만 현재 Agent의 직접 검색 호출은 recall 확보를 위해 10을 전달한다.

### 처리

1. 문서 DB에서 모든 활성 문서 경로 레코드를 조회해 `document_id` 허용 목록을 만든다.
2. 사전 생성된 영구 FAISS 인덱스를 로드하거나 프로세스 캐시에서 재사용한다.
3. 벡터 검색과 어휘 검색 결과를 합치고 활성 문서 ID만 남긴다.
4. Agent는 직접 검색 최고 점수가 기준보다 낮을 때 동의어 확장 질의를 병렬 추가 호출한다.

질의 시 원문 파일을 다시 로드하지 않는다. `file_path`는 DB 허용 목록과 다운로드 해석에만
사용하며 Tool 응답에 포함하지 않는다.

### 성공 응답

```json
{
  "status": "success",
  "domain": "document",
  "message": null,
  "data": [
    {"content": "휴가 신청은 ...", "score": 0.87}
  ],
  "sources": [
    {
      "document_id": "hr_policy_001",
      "title": "인사 규정",
      "file_name": "인사규정.pdf",
      "page": 12
    }
  ],
  "metadata": {
    "index_version": "index-version",
    "result_count": 1
  }
}
```

`data`와 `sources`는 같은 순서와 길이를 가져야 한다. Host는 각 쌍을 하나의 문서 evidence로
정규화한다. 문서 DB 접속 실패는 in-process 경계에서 `QUERY_ERROR`, 일반 검색 장애는
`INTERNAL_ERROR`, 결과 없음은 `NO_RESULT`다.

## Tool 2: 문서 다운로드 해석

- Tool 이름: `resolve_document_download`
- 현재 범위: `InProcessMCPPort` 전용
- 입력: `document_id`, 서버 생성 `user_context`
- 출력: Host 내부에서만 쓰는 `file_path`, `file_name`

```json
{
  "document_id": "hr_policy_001",
  "user_context": {"role": "hr"}
}
```

활성 문서 ID와 `document_db` 권한을 검사한 뒤 등록된 파일만 해석한다. 이 성공 envelope의
내부 `file_path`는 일반 MCP evidence나 Chat API에 전달하지 않고 `FileResponse` 생성에만
사용한다. 등록되지 않은 ID나 실제 파일이 없는 경우 Host는 `MCPNoResultError`로 바꾼다.

## Tool 3: 구매 데이터 조회

- Tool 이름: `query_purchase`
- 구현: `mcp_servers/data_tools/purchase/`
- 용도: 구매액, 공급업체, 발주, 미지급금 질의
- 접근: `purchase_db` 권한과 구매 read-only 계정 필요

```json
{
  "question": "공급업체별 구매 금액을 알려줘",
  "user_context": {"role": "finance"}
}
```

## Tool 4: 판매 데이터 조회

- Tool 이름: `query_sales`
- 구현: `mcp_servers/data_tools/sales/`
- 용도: 매출, 고객, 주문, 미수금 질의
- 접근: `sales_db` 권한과 판매 read-only 계정 필요

```json
{
  "question": "2025년 1분기 상품별 매출을 알려줘",
  "user_context": {"role": "finance"}
}
```

## Data Tool 공통 처리 계약

```text
질문 검증
  -> 역할별 DB 권한 검사
  -> 도메인 schema·용어집으로 LLM SQL 생성
  -> SELECT/WITH + 허용 View + 금지 키워드 + LIMIT 검사
  -> EXPLAIN
  -> 실패 시 SQL 1회 재작성 후 재검증
  -> read-only 계정으로 실행
  -> 공통 envelope
```

- 질문 최대 길이는 도메인 service에서 500자다.
- 허용 SQL은 단일 `SELECT` 또는 `WITH`이며 주석과 쓰기·DDL 키워드는 거부한다.
- 구매·판매는 각각 다섯 개의 공개 View만 참조할 수 있다.
- `LIMIT`이 없으면 200을 붙이고 200보다 크면 200으로 낮춘다.
- LLM이 `NO_SQL`을 반환하거나 결과가 없으면 원인·재질문 안내를 포함한 `NO_RESULT`다.
- SQL/EXPLAIN/조회 장애는 `QUERY_ERROR`, 내부 evidence 형식 위반은 `INTERNAL_ERROR`다.

### 성공 metadata

```json
{
  "generated_sql": "SELECT ... LIMIT 200",
  "row_count": 1,
  "elapsed_ms": 12.3,
  "views_used": ["v_sales_order"],
  "data_coverage": {"min_order_date": "...", "max_order_date": "..."},
  "retry_count": 0,
  "currency": "JOD",
  "truncated": false,
  "chart_hint": "bar | line | null"
}
```

`generated_sql`, `row_count`, `elapsed_ms`는 공통 Data server가 보강한다. 나머지는 도메인
service metadata다. 현재 운영 구현은 `table_name`, `query_id`, `freshness_seconds`,
`source_version`을 공급하지 않는다. 스키마 모델과 fake 테스트는 이 필드를 수용하지만
실제 provider가 값을 만들기 전에는 완료된 provenance/freshness 계약으로 간주하지 않는다.

`chart_hint`도 Host evidence에는 보존되지만 현재 `TableData.chart_type`으로 복사되지 않는다.

## LangGraph 라우팅·병합

| route / data domain | 호출 |
|---|---|
| `GENERAL` | Tool 없음 |
| `DOCUMENT` | `search_documents` |
| `DATABASE + purchase` | `query_purchase` |
| `DATABASE + sales` | `query_sales` |
| `DATABASE + both` | 구매 후 판매 순차 호출 |
| `BOTH` | 문서와 선택된 구매·판매 분기를 병렬 호출 |

각 결과는 `document_evidence`, `database_evidence`에 분리 보존한 뒤 평가 시 합친다.
구매·판매를 모두 조회하는 database 분기 안에서는 두 Data Tool을 순차 호출한다.

- `NO_RESULT`는 retrieval 노드에서 정상적인 빈 결과로 처리한다.
- 단일 도메인의 `FORBIDDEN`, `QUERY_ERROR`, `INTERNAL_ERROR`, timeout은 즉시 API 오류로 전파된다.
- `data_domain=both` 또는 route `BOTH`에서는 한 Tool 오류가 있어도 다른 근거가 있으면
  부분 응답으로 진행한다.
- 모든 근거가 없으면 evidence가 `INSUFFICIENT`가 되고 같은 route를 한 번 재조회한다.
- 재조회 뒤에도 근거가 없으면 HTTP 200과 안전한 근거 부족 답변을 반환한다.

## evidence 평가 계약

Graph state에는 다음 필드가 기록된다.

```json
{
  "evidence_status": "SUPPORTED | PARTIALLY_SUPPORTED | INSUFFICIENT | CONTRADICTED",
  "evidence_reason": "판정 이유",
  "evidence": [],
  "retrieval_diagnostics": {}
}
```

`evidence`에는 정책을 통과한 항목만 남는다. `CONTRADICTED`는 `contradicted=true` 또는 같은
`fact_id`의 서로 다른 명시적 `fact_value`가 있을 때만 사용한다. 단순 저신뢰는
`INSUFFICIENT`다.

## 공개 HTTP API

### 인증

| Method | Endpoint | 인증 | 성공 |
|---|---|---|---|
| `GET` | `/api/auth/csrf` | 불필요 | CSRF token과 cookie |
| `POST` | `/api/auth/login` | CSRF | `{"user": profile}`, 세션 쿠키 |
| `POST` | `/api/auth/logout` | session + CSRF | `204`와 쿠키 삭제 |
| `GET` | `/api/auth/me` | 필요 | 현재 사용자 profile |

인증 API는 Django가 소유한다. `login`과 `logout`에는 `/api/auth/csrf`에서 받은 토큰을
`X-CSRFToken` 헤더로 전달한다. 세션 쿠키는 JavaScript에서 읽지 않으며 인증 응답에는
재사용 방지를 위한 `no-store/no-cache` 헤더를 적용한다.

- `GET /api/auth/csrf`: `{"csrf_token": "..."}`와 CSRF cookie
- login JSON 형식 오류: `400`; 자격증명·활성 상태·역할 오류: `401`; CSRF 실패: `403`
- logout/me의 세션 없음: `401`; logout CSRF 실패: `403`

공개 profile은 다음 필드만 포함한다. `allowed_databases`는 client 입력이 아니라
`shared/auth_policy.py`가 role에서 계산한 결과다.

```json
{
  "user_id": 1,
  "username": "user",
  "display_name": "사용자",
  "role": "admin",
  "allowed_databases": ["document_db", "purchase_db", "sales_db"]
}
```

세션 cookie 이름은 `chatbot_session`이고 `HttpOnly`, `SameSite=Lax`, path `/`를 사용한다.
`AUTH_COOKIE_SECURE=true`이면 session과 CSRF cookie 모두 Secure다. 만료는
`AUTH_SESSION_EXPIRE_SECONDS` 기준의 고정 수명이며 보호 요청마다 연장하지 않는다.

FastAPI는 보호 요청마다 `POST /internal/auth/introspect`를 Django 내부 주소로 호출한다.
브라우저에 이 경로를 공개 라우팅하지 않으며, `Authorization: Bearer`의 별도 내부 키와
유효한 Django 세션이 모두 있어야 사용자 profile과 원문이 아닌 `session_id`를 반환한다.
인증 실패는 FastAPI에서 `401`, Django 인증 서비스 장애나 계약 오류는 `503`이다.
내부 호출은 환경 proxy를 사용하지 않으며 `/internal/auth/*`는 private network 또는
loopback에서만 접근할 수 있어야 한다. 원격 구간이라면 TLS 또는 service mesh 보호가
필요하다. 공개 gateway는 `/api/auth/login`에 조직 표준 rate limit을 적용하고 인증
header·cookie를 access log에 기록하지 않는다.

내부 성공 응답은 공개 profile 필드에 64자리 hex `session_id`를 추가한다. FastAPI는
응답의 `user_id`, 문자열 길이, role과 session ID 형식을 다시 검증한 뒤
`allowed_databases`를 로컬 정책으로 재계산한다.

| Django 내부 응답 | 의미 | FastAPI 공개 응답 |
|---|---|---|
| `200` | 내부 키·활성 세션·활성 계정 유효 | 보호 API 계속 처리 |
| `401` | 세션 없음·만료·삭제, 비활성/잘못된 역할 | `401` |
| `403` | 내부 키 불일치 | `503` |
| `503` 또는 기타 오류/잘못된 JSON | 인증 서비스 설정·가용성·계약 오류 | `503` |

FastAPI의 내부 client timeout은 `AUTH_INTROSPECTION_TIMEOUT_SECONDS`이며 환경 HTTP proxy를
사용하지 않는다. `app/api/auth.py`의 legacy 라우터는 현재 FastAPI 앱에 등록되지 않는다.

### 사용자 UI

`GET /`은 Django `web` 앱이 `web/index.html` template으로 제공한다. HTML은 no-cache이고
CSS·JavaScript는 `/django-static/web/*`, 전환 기간의 Chart.js bundle은
`/django-static/vendor/*`에서 제공한다. UI는 같은 origin의 `/api/auth/*`, `/api/chat`과
`/api/documents/*`만 호출한다.

로컬에서 `DJANGO_SERVE_STATIC_FILES=true`이면 Django가 finder 기반 개발용 정적 route를
등록한다. 운영에서는 이 값을 `false`로 두며 `/django-static/*`를 collectstatic 산출물이나
CDN으로 라우팅한다.

FastAPI는 더 이상 `/`, `/chat.js`, `/style.css`, `/static/*`를 제공하지 않는다. 공개
gateway는 `/`와 사용자 page route를 Django로, 명시한 채팅·문서·상태 API를 FastAPI로
보낸다. `/django-static/*`는 Django `collectstatic` 산출물을 제공하는 정적 파일 서버나
CDN으로 보낸다.

### 채팅

`POST /api/chat`는 인증이 필요하다.

```json
{
  "question": "2025년 고객별 매출을 알려줘",
  "session_id": "optional-conversation-id"
}
```

`question`은 1자 이상이어야 한다. `session_id`는 선택 값이며 원문 대신 SHA-256 해시가
캐시 대화 문맥 재료로 사용된다.

```json
{
  "answer": "...",
  "sources": [],
  "tables": [],
  "cached": false,
  "route": "DATABASE",
  "evidence_status": "SUPPORTED",
  "request_id": "uuid"
}
```

문서 `sources`는 `document_id`별로 합쳐 `pages`, `chunks`, `download_url`, 최고 `score`,
`source_version`을 제공한다. DB `sources`와 `tables`는 가능한 경우 `table_name`,
`query_id`, `freshness_seconds`, `source_version`을 전달한다. 내부 `file_path`, 자격증명,
token 계열 필드는 공개하지 않는다.

### 문서 다운로드

`GET /api/documents/download?doc_id=<document_id>`는 인증과 문서 DB 권한이 필요하다.

- 성공: `application/octet-stream`, UTF-8 `Content-Disposition`
- 등록되지 않은 ID 또는 파일 없음: `404`
- 문서 DB 권한 없음: `403`
- Tool 처리 장애: `502`

### 상태 확인

`GET /api/health`는 인증 없이 `{"status":"ok"}`를 반환한다. 프로세스 liveness만
의미하며 MySQL, FAISS, OpenAI, Redis, 원격 MCP readiness를 보장하지 않는다.

### 공통 관측 헤더

FastAPI middleware는 응답에 `X-Request-ID`와 `Server-Timing`을 추가한다. 채팅 응답의
`request_id`는 헤더 ID와 같다. UI 정적 진입 파일은 `Cache-Control: no-store`를 사용한다.

## 공개 오류 매핑

| 내부 분류 | HTTP | 공개 `error_code` |
|---|---:|---|
| 입력 오류 | 400 | `INVALID_INPUT` |
| DB 권한 거부 | 403 | `FORBIDDEN` |
| 직접 전파된 결과 없음 | 404 | `NO_RESULT` |
| 직접 전파된 근거 부족 | 422 | `EVIDENCE_INSUFFICIENT` |
| Tool 질의 오류 | 502 | `QUERY_ERROR` |
| Tool 내부·malformed 응답 | 502 | `INTERNAL_ERROR` |
| transport timeout | 504 | `TIMEOUT` |
| 분류되지 않은 앱 오류 | 500 | `INTERNAL_ERROR` |

일반적인 문서·Data `NO_RESULT`는 retrieval 노드에서 빈 근거로 흡수되므로 실제 Chat API는
대개 404 대신 재조회 후 HTTP 200 근거 부족 답변을 반환한다.

## 캐시 계약

- Graph 진입 전에 조회하고 Graph 완료 후에만 저장한다.
- cache hit는 LLM과 모든 MCP 호출을 차단한다.
- 질문, 대화 문맥, 인증 사용자·세션·역할·허용 DB, 인덱스/DB freshness, 프롬프트,
  모델이 키 재료다.
- cache hit도 저장된 `route`, `evidence_status`, 출처, 표를 보존하고 새 `request_id`를 반환한다.
- 현재 저장소는 `MemoryCache`다. Redis와 ETL 기반 분산 무효화는 미구현이다.

## 변경 규칙

- Tool 이름, payload, envelope, 공개 HTTP 필드, 오류 매핑 변경은 Backend/통합 담당과
  관련 도메인 담당이 함께 검토한다.
- 문서 ID·인덱스 metadata·다운로드 해석 변경은 RAG PDF 담당과 Backend 담당이 검토한다.
- 구매·판매 허용 View, 지표, SQL guard 변경은 해당 도메인 담당과 Backend 담당이 검토한다.
- 인증 역할이나 DB 권한 변경은 `app/auth/policy.py`, API/MCP 테스트, 이 문서를 함께 갱신한다.
- 원격 MCP transport를 추가할 때는 인증 컨텍스트 전달, timeout, envelope 검증을 계약
  테스트로 먼저 고정한다.

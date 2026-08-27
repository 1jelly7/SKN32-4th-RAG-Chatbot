# 요구사항 정의서

## 1. 문서 개요

| 항목            | 내용                                                                                                               |
|-----------------|--------------------------------------------------------------------------------------------------------------------|
| 문서명          | 사내 문서 RAG·업무 데이터 Text2SQL 챗봇 요구사항 정의서                                                            |
| 기준일          | 2026-08-27                                                                                                         |
| 기준 시스템     | Django + FastAPI + LangGraph + MCP 기반 챗봇                                                                       |
| 문서 목적       | 현재 구현과 계약을 기준으로 시스템의 범위, 기능, 품질, 보안 및 수용 기준을 식별 가능한 요구사항으로 정의한다.      |
| 인터페이스 정본 | 현재 코드와 Pydantic model. 대표 경계는 `app/api/`, `app/schemas/`, `app/mcp/client.py`, `app/schemas/mcp.py`이다. |

## 2. 배경 및 목표

조직 구성원은 사내 규정·업무 문서와 구매·판매 데이터가 서로 다른 저장소에 있어 필요한 정보를 찾고 해석하는 데 시간이 든다. 본 시스템은 하나의 채팅 UI와 API에서 자연어 질문을 받아 다음 목표를 달성한다.

1. 사내 문서를 검색하고 근거 문서, 페이지 및 발췌문과 함께 답변한다.
2. 구매·판매 질문을 읽기 전용 SQL로 변환하고 조회 결과를 표와 차트로 제공한다.
3. 문서와 업무 데이터가 함께 필요한 질문은 두 근거를 결합하되 출처를 분리한다.
4. 인증된 사용자의 역할에 따라 접근 가능한 데이터베이스를 제한한다.
5. 근거의 품질과 충돌 여부를 평가해 확인되지 않은 사실의 생성을 억제한다.
6. 계정·UI, 채팅 오케스트레이션, Tool, 배치 작업의 책임을 분리해 안전하게 운영한다.
7. 권한이 있는 사용자에게 구매·판매 추이와 고정 규칙 기반 이상 신호를 대시보드로 제공한다.
8. 등록된 업무 리포트 템플릿과 조회 기간으로 DOCX 보고서를 생성한다.

## 3. 이해관계자와 사용자 역할

| 구분             | 주요 관심사 및 권한                                                                       |
|------------------|-------------------------------------------------------------------------------------------|
| 일반 업무 사용자 | 로그인, 자연어 질문, 답변·출처·표·차트 확인, 허용 문서 다운로드                           |
| `hr` 역할        | `document_db`만 접근 가능하며 구매·판매 DB에는 접근 불가                                  |
| `finance` 역할   | 세 업무 DB와 대시보드·리포트 화면 접근 가능                                               |
| `admin` 역할     | 세 업무 DB와 대시보드·리포트 화면 접근 가능. Django Admin은 별도 `is_staff` 정책으로 관리 |
| 운영자           | 환경 설정, 프로세스·gateway 운영, 로그 확인, 계정 migration 및 비밀 관리                  |
| 데이터 담당자    | 구매·판매 ETL, 읽기 전용 View와 계정, 데이터 품질 및 freshness 관리                       |
| 문서/RAG 담당자  | 문서 등록, 청킹·임베딩, FAISS 재생성, 검색 품질 관리                                      |
| 개발·검증 담당자 | API·MCP 계약, fake 기반 회귀 테스트, 실제 인프라 수용 테스트 관리                         |

## 4. 시스템 범위

- Django 기반 사용자 화면, 계정, 로그인·로그아웃, 서버 세션 및 Django Admin
- FastAPI 기반 채팅, 문서 다운로드, 대시보드, DOCX 리포트 및 liveness API
- 질문을 `GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH`로 분류하는 LangGraph 흐름
    - Document Tool을 통한 하이브리드 문서 검색과 원문 다운로드 경로 해석
- Purchase/Sales Data Tool을 통한 자연어 Text2SQL 및 읽기 전용 조회
- 근거 평가, 답변 합성, 출처·표·차트용 응답 생성
- 사용자·대화 문맥·권한·근거 freshness가 격리된 응답 캐시
- 문서 등록·인덱싱과 구매·판매 ETL을 수행하는 오프라인 배치
- RAG 후보 관련성 라벨링과 검색 품질 지표 산출을 위한 오프라인 평가 도구
- 동일 origin을 제공하는 로컬 Nginx gateway 구성과 실행 스크립트

## 5. 시스템 구성 및 책임 경계

```text
Browser
  -> Same-origin Gateway
      -> Django: chat/dashboard/report UI, /api/auth/*, /admin/*, account DB, server session
      -> Static server: /django-static/*
      -> FastAPI: chat, document, dashboard, anomaly, report, health API
          -> Django internal session introspection
          -> Cache -> LangGraph -> MCP client
              -> Document Tool -> document DB + persistent FAISS + registered files
              -> Purchase/Sales Tool -> read-only MySQL views

Offline
  -> Infrastructure setup -> databases + write accounts + read-only views/accounts
  -> Document registration/ingestion -> document DB + FAISS artifacts
  -> Purchase/Sales ETL -> domain tables + read-only views
  -> RAG evaluation -> relevance labels + retrieval metrics
```

- Django는 계정 DB, 인증, 세션, UI와 Admin의 유일한 소유자여야 한다.
- FastAPI는 보호 API마다 Django 내부 인증 확인 API로 사용자 컨텍스트를 획득해야 한다.
- FastAPI와 Agent는 MCP 경계를 통해서만 문서 및 업무 데이터를 조회해야 한다.
- ETL과 문서 인덱싱은 온라인 요청 흐름과 분리해야 한다.

## 6. 기능 요구사항

기능 요구사항은 개발 우선순위가 아니라 현재 구현과 검증 수준을 추적한다.

- `구현`: 기본 실행 경로가 코드에 반영되어 있다.
- `조건부 구현`: 코드가 반영되어 있으나 기능 플래그나 선택적 외부 의존성을 활성화해야 한다.
- `자동 검증`: 결정적인 단위 또는 fake 기반 계약 테스트가 해당 동작을 직접 검증한다.
- `부분 검증`: 코드·정적 계약 또는 일부 자동 테스트는 있으나 실제 브라우저, DB, 외부 서비스 등의 수용 검증이 남아 있다.
- `수동 검증`: 해당 동작을 직접 실행하는 자동 테스트가 없어 명시된 환경과 절차로 사람이 확인해야 한다.
- `구현·검증 근거 및 수용 기준`: 해당 ID를 직접 뒷받침하는 구현·테스트 경로와 남은 수용 조건이다.

### 6.1 인증·계정·권한

| ID          | 요구사항                                                                                                                                | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                                                                                                                                 |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-AUTH-001 | 시스템은 사용자에게 CSRF 토큰 발급, 로그인, 로그아웃, 현재 사용자 조회 API를 제공해야 한다.                                             | 구현      | 자동 검증 | `app/auth/`, `shared/auth_policy.py`, `django_app/accounts/`, `app/tests/test_auth.py`, `app/tests/test_auth_gateway.py`, `django_app/tests/test_auth_api.py`; `GET /api/auth/csrf`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`의 계약 테스트 통과 |
| FR-AUTH-002 | 로그인 성공 시 Django 서버 세션을 발급하고 세션 쿠키를 `HttpOnly`, `SameSite=Lax`, path `/`로 설정해야 한다.                            | 구현      | 자동 검증 | `app/auth/`, `shared/auth_policy.py`, `django_app/accounts/`, `app/tests/test_auth.py`, `app/tests/test_auth_gateway.py`, `django_app/tests/test_auth_api.py`; 브라우저/응답 쿠키 속성 확인                                                                                 |
| FR-AUTH-003 | 로그인과 로그아웃 요청은 CSRF 검증을 통과해야 하며, 로그아웃된 세션은 재사용할 수 없어야 한다.                                          | 구현      | 자동 검증 | `app/auth/`, `shared/auth_policy.py`, `django_app/accounts/`, `app/tests/test_auth.py`, `app/tests/test_auth_gateway.py`, `django_app/tests/test_auth_api.py`; CSRF 실패 `403`, 폐기 세션 재요청 `401` 확인                                                                 |
| FR-AUTH-004 | 세션은 설정된 고정 수명으로 만료되며 보호 요청이나 내부 인증 확인으로 만료가 연장되지 않아야 한다.                                      | 구현      | 자동 검증 | `app/auth/`, `shared/auth_policy.py`, `django_app/accounts/`, `app/tests/test_auth.py`, `app/tests/test_auth_gateway.py`, `django_app/tests/test_auth_api.py`; 시간 제어 세션 테스트 통과                                                                                   |
| FR-AUTH-005 | FastAPI는 보호 요청마다 비공개 Django introspection endpoint를 호출하고 검증된 사용자 컨텍스트만 Graph와 MCP에 전달해야 한다.           | 구현      | 자동 검증 | `app/auth/`, `shared/auth_policy.py`, `django_app/accounts/`, `app/tests/test_auth.py`, `app/tests/test_auth_gateway.py`, `django_app/tests/test_auth_api.py`; 유효 세션은 처리, 무효 세션은 `401`, 인증 서비스 장애는 `503`                                                |
| FR-AUTH-006 | 역할별 허용 DB는 서버의 공통 정책으로 계산해야 한다. `hr`는 문서 DB만, `finance`와 `admin`은 문서·구매·판매 DB를 사용할 수 있어야 한다. | 구현      | 자동 검증 | `app/auth/`, `shared/auth_policy.py`, `django_app/accounts/`, `app/tests/test_auth.py`, `app/tests/test_auth_gateway.py`, `django_app/tests/test_auth_api.py`; 역할별 허용·거부 테스트 통과                                                                                 |
| FR-AUTH-007 | Tool은 실행 시점에 서버가 만든 사용자 컨텍스트와 DB 권한을 다시 검증해야 한다.                                                          | 구현      | 자동 검증 | `app/auth/`, `shared/auth_policy.py`, `django_app/accounts/`, `app/tests/test_auth.py`, `app/tests/test_auth_gateway.py`, `django_app/tests/test_auth_api.py`; 권한 없는 Data/Document Tool 호출이 실행 전 거부됨                                                           |
| FR-AUTH-008 | Django Admin 접근은 애플리케이션의 `admin` 역할과 별도로 Django의 staff 권한을 요구해야 한다.                                           | 구현      | 자동 검증 | `app/auth/`, `shared/auth_policy.py`, `django_app/accounts/`, `app/tests/test_auth.py`, `app/tests/test_auth_gateway.py`, `django_app/tests/test_auth_api.py`; 비-staff 계정의 Admin 접근 거부                                                                              |

### 6.2 채팅 및 질문 라우팅

| ID          | 요구사항                                                                                                                                          | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                                                                                                     |
|-------------|---------------------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-CHAT-001 | 인증된 사용자는 1자 이상의 질문과 선택적 `session_id`로 `POST /api/chat`을 호출할 수 있어야 한다.                                                 | 구현      | 자동 검증 | `app/api/chat.py`, `app/agent/`, `app/tests/test_agent.py`, `tests/integration/test_chat_document_flow.py`, `tests/integration/test_chat_data_flow.py`, `tests/integration/test_chat_error_flow.py`; Pydantic 입력 검증 및 보호 API 테스트 통과 |
| FR-CHAT-002 | 시스템은 질문을 `GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH` 중 하나로 분류해야 한다.                                                                | 구현      | 자동 검증 | `app/api/chat.py`, `app/agent/`, `app/tests/test_agent.py`, `tests/integration/test_chat_document_flow.py`, `tests/integration/test_chat_data_flow.py`, `tests/integration/test_chat_error_flow.py`; routing fixture와 단위 테스트 통과         |
| FR-CHAT-003 | `GENERAL` 질문은 문서·구매·판매 Tool을 호출하지 않고 일반 답변 생성 경로로 처리해야 한다.                                                         | 구현      | 자동 검증 | `app/api/chat.py`, `app/agent/nodes.py`, `app/tests/test_agent.py`; `GENERAL` 경로의 내부 Tool 호출 0회 확인                                                                                                                                    |
| FR-CHAT-004 | `DOCUMENT`는 Document Tool만 호출하고, `DATABASE`는 분류된 `data_domain`이 `purchase`, `sales`, `both`인지에 따라 해당 Data Tool만 호출해야 한다. | 구현      | 자동 검증 | `app/agent/nodes.py`, `app/tests/test_agent.py`, `tests/integration/test_chat_document_flow.py`, `tests/integration/test_chat_data_flow.py`; route·domain별 호출 확인                                                                           |
| FR-CHAT-005 | `BOTH`는 문서와 DB 검색을 병렬 실행하고 두 근거를 평가 전까지 별도 상태로 보존해야 한다.                                                          | 구현      | 자동 검증 | `app/api/chat.py`, `app/agent/`, `app/tests/test_agent.py`, `tests/integration/test_chat_document_flow.py`, `tests/integration/test_chat_data_flow.py`, `tests/integration/test_chat_error_flow.py`; 병렬 분기 및 병합 테스트 통과              |
| FR-CHAT-006 | 구매와 판매가 모두 필요한 질문은 동일 database 분기에서 각 도메인 Tool을 호출하고 결과를 합쳐야 한다.                                             | 구현      | 자동 검증 | `app/api/chat.py`, `app/agent/`, `app/tests/test_agent.py`, `tests/integration/test_chat_document_flow.py`, `tests/integration/test_chat_data_flow.py`, `tests/integration/test_chat_error_flow.py`; 양 도메인 fake 결과 병합 확인              |
| FR-CHAT-007 | 응답은 `answer`, `sources`, `tables`, `cached`, `route`, `evidence_status`, `request_id`를 공개 계약에 맞게 반환해야 한다.                        | 구현      | 자동 검증 | `app/api/chat.py`, `app/agent/`, `app/tests/test_agent.py`, `tests/integration/test_chat_document_flow.py`, `tests/integration/test_chat_data_flow.py`, `tests/integration/test_chat_error_flow.py`; 응답 schema 검증 통과                      |
| FR-CHAT-008 | 내부 오류는 계약된 HTTP status와 공개 `error_code`로 변환하고 내부 예외 상세를 노출하지 않아야 한다.                                              | 구현      | 자동 검증 | `app/api/chat.py`, `app/agent/`, `app/tests/test_agent.py`, `tests/integration/test_chat_document_flow.py`, `tests/integration/test_chat_data_flow.py`, `tests/integration/test_chat_error_flow.py`; 오류 flow 통합 테스트 통과                 |
| FR-CHAT-009 | 최신성이 필요한 질문은 명시적 query label 또는 LLM 분류 보정으로 식별하고, 웹 검색 결과가 있을 때만 해당 결과를 근거로 답변해야 한다.             | 구현      | 자동 검증 | `app/agent/nodes.py`, `app/tests/test_agent.py`, `app/tests/test_web_search.py`; 최신성 분류와 검색 결과 기반 답변 확인                                                                                                                         |
| FR-CHAT-010 | 최신성 질문의 웹 검색이 실패하거나 결과가 없으면 추측성 답변 대신 최신 정보 확인이 필요하다는 고정 안내를 반환해야 한다.                          | 구현      | 자동 검증 | `app/agent/nodes.py`, `app/tests/test_agent.py`, `app/tests/test_web_search.py`; 검색 실패·무결과 fallback 확인                                                                                                                                 |

### 6.3 문서 RAG

| ID         | 요구사항                                                                                                                                 | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                                                                                                |
|------------|------------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-RAG-001 | 문서는 온라인 질의 전에 등록, 로드, 청킹, 임베딩 및 영구 FAISS 인덱싱되어야 한다.                                                        | 구현      | 자동 검증 | `ingestion/`, `mcp_servers/document_tools/`, `app/tests/test_document_mcp.py`, `app/tests/test_document_mcp_eval.py`, `app/tests/test_query_expansion.py`, `app/tests/test_web_search.py`; fixture 인덱싱 및 재로딩 테스트 통과            |
| FR-RAG-002 | 문서 검색은 활성 문서 목록을 허용 목록으로 사용하고 벡터 검색과 어휘 검색 결과를 결합해야 한다.                                          | 구현      | 자동 검증 | `ingestion/`, `mcp_servers/document_tools/`, `app/tests/test_document_mcp.py`, `app/tests/test_document_mcp_eval.py`, `app/tests/test_query_expansion.py`, `app/tests/test_web_search.py`; 비활성 문서 제외 및 하이브리드 검색 테스트 통과 |
| FR-RAG-003 | 직접 검색 점수가 기준보다 낮으면 동의어 확장 검색을 추가 수행하되 중복 근거를 제거해야 한다.                                             | 구현      | 자동 검증 | `ingestion/`, `mcp_servers/document_tools/`, `app/tests/test_document_mcp.py`, `app/tests/test_document_mcp_eval.py`, `app/tests/test_query_expansion.py`, `app/tests/test_web_search.py`; 낮은 점수/중복 fixture 테스트 통과              |
| FR-RAG-004 | 검색 결과는 문서 ID, 제목, 파일명, 페이지, 발췌문, 관련도 및 버전 정보를 제공하고 내부 파일 경로를 제거해야 한다.                        | 구현      | 자동 검증 | `ingestion/`, `mcp_servers/document_tools/`, `app/tests/test_document_mcp.py`, `app/tests/test_document_mcp_eval.py`, `app/tests/test_query_expansion.py`, `app/tests/test_web_search.py`; Source schema와 민감 필드 부재 확인             |
| FR-RAG-005 | 문서 질문에 사내 근거가 부족하면 웹 검색을 마지막 수단으로 사용할 수 있으며, 검색도 실패하면 근거 부족 안내를 반환해야 한다.             | 구현      | 자동 검증 | `ingestion/`, `mcp_servers/document_tools/`, `app/tests/test_document_mcp.py`, `app/tests/test_document_mcp_eval.py`, `app/tests/test_query_expansion.py`, `app/tests/test_web_search.py`; 웹 검색 성공/실패 fake 테스트 통과              |
| FR-RAG-006 | 사용자는 출처 카드의 등록된 `document_id`로 권한이 허용된 원문을 다운로드할 수 있어야 한다. 클라이언트 파일 경로 입력은 허용하지 않는다. | 구현      | 자동 검증 | `ingestion/`, `mcp_servers/document_tools/`, `app/tests/test_document_mcp.py`, `app/tests/test_document_mcp_eval.py`, `app/tests/test_query_expansion.py`, `app/tests/test_web_search.py`; 성공 다운로드와 `403`/`404`/`502` 매핑 확인     |

### 6.4 구매·판매 Text2SQL

| ID         | 요구사항                                                                                                                                                                            | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                                                                                                                   |
|------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-SQL-001 | 시스템은 자연어 질문과 도메인 schema·용어집을 이용해 구매 또는 판매 조회 SQL을 생성해야 하며, 복합 질문은 도메인별로 라벨이 있는 독립 쿼리 최대 3개로 분해할 수 있어야 한다.        | 구현      | 자동 검증 | `mcp_servers/data_tools/`, `scripts/ensure_views_and_readers.py`, `app/tests/test_purchase_text2sql.py`, `app/tests/test_sales_text2sql.py`, `app/tests/test_data_mcp.py`, `django_app/web/static/web/chat.js`; 도메인 golden case와 최대 쿼리 수 테스트 통과 |
| FR-SQL-002 | 생성된 각 SQL은 단일 `SELECT` 또는 `WITH` 문, 도메인별 허용 View 및 최대 `LIMIT 200` 조건을 만족해야 한다.                                                                          | 구현      | 자동 검증 | `mcp_servers/data_tools/`, `scripts/ensure_views_and_readers.py`, `app/tests/test_purchase_text2sql.py`, `app/tests/test_sales_text2sql.py`, `app/tests/test_data_mcp.py`, `django_app/web/static/web/chat.js`; 쿼리 블록별 SQL guard 테스트 통과             |
| FR-SQL-003 | DML, DDL, 다중 statement, 주석 기반 우회 및 허용되지 않은 table/view 접근을 실행 전에 차단해야 한다.                                                                                | 구현      | 자동 검증 | `mcp_servers/data_tools/`, `scripts/ensure_views_and_readers.py`, `app/tests/test_purchase_text2sql.py`, `app/tests/test_sales_text2sql.py`, `app/tests/test_data_mcp.py`, `django_app/web/static/web/chat.js`; adversarial SQL 테스트 통과                   |
| FR-SQL-004 | 실행 전 권한 있는 계정으로 `EXPLAIN`을 수행하고, 실패 시 오류 문맥을 이용한 SQL 재작성은 최대 1회만 허용해야 한다.                                                                  | 구현      | 자동 검증 | `mcp_servers/data_tools/`, `scripts/ensure_views_and_readers.py`, `app/tests/test_purchase_text2sql.py`, `app/tests/test_sales_text2sql.py`, `app/tests/test_data_mcp.py`, `django_app/web/static/web/chat.js`; EXPLAIN 실패·재작성 호출 횟수 확인            |
| FR-SQL-005 | 실제 조회는 도메인별 read-only 계정으로만 수행해야 한다.                                                                                                                            | 구현      | 부분 검증 | `mcp_servers/data_tools/`, `scripts/ensure_views_and_readers.py`, `app/tests/test_purchase_text2sql.py`, `app/tests/test_sales_text2sql.py`, `app/tests/test_data_mcp.py`, `django_app/web/static/web/chat.js`; DB grant와 client 설정 검증                   |
| FR-SQL-006 | 결과 또는 답변 가능한 schema가 없으면 `NO_RESULT`로 처리하고 Graph가 빈 근거로 평가할 수 있어야 한다.                                                                               | 구현      | 자동 검증 | `mcp_servers/data_tools/`, `scripts/ensure_views_and_readers.py`, `app/tests/test_purchase_text2sql.py`, `app/tests/test_sales_text2sql.py`, `app/tests/test_data_mcp.py`, `django_app/web/static/web/chat.js`; 무결과 flow 테스트 통과                       |
| FR-SQL-007 | 성공한 DB 쿼리 블록은 `label`, `domain`, `generated_sql`, `rows`, `row_count`를 독립된 database evidence에 보존해야 한다.                                                           | 구현      | 자동 검증 | `app/schemas/mcp.py`, `app/mcp/client.py`, `app/tests/test_data_mcp.py`; 다중 Tool envelope의 블록별 evidence 변환 확인                                                                                                                                       |
| FR-SQL-008 | 판매 금액은 UI에서 KRW 단위를 표시해야 한다.                                                                                                                                        | 구현      | 부분 검증 | `mcp_servers/data_tools/`, `scripts/ensure_views_and_readers.py`, `app/tests/test_purchase_text2sql.py`, `app/tests/test_sales_text2sql.py`, `app/tests/test_data_mcp.py`, `django_app/web/static/web/chat.js`; 판매 금액 표·차트 렌더링 확인                 |
| FR-SQL-009 | DB Tool 응답에 `table_name` 또는 `view_name`, `query_id`, `freshness_seconds`, `source_version`이 있으면 공개 Source·TableData에 동일 값을 전달하고, 없으면 `null`로 반환해야 한다. | 구현      | 자동 검증 | `app/schemas/mcp.py`, `app/schemas/chat.py`, `app/agent/nodes.py`, `app/tests/test_data_mcp.py`; 선택 metadata의 존재·부재 변환 확인                                                                                                                          |

### 6.5 근거 평가 및 답변 생성

| ID         | 요구사항                                                                                                                          | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                           |
|------------|-----------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-EVD-001 | 검색 경로의 답변은 채택된 근거 범위 안에서만 생성해야 한다.                                                                       | 구현      | 자동 검증 | `app/agent/evidence_eval.py`, `app/agent/nodes.py`, `app/tests/test_agent.py`, `tests/integration/test_chat_error_flow.py`; 근거 밖 사실을 요구하는 평가 case 확인    |
| FR-EVD-002 | 시스템은 근거를 `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT`, `CONTRADICTED`로 평가해야 한다.                               | 구현      | 자동 검증 | `app/agent/evidence_eval.py`, `app/agent/nodes.py`, `app/tests/test_agent.py`, `tests/integration/test_chat_error_flow.py`; 상태별 단위 테스트 통과                   |
| FR-EVD-003 | `INSUFFICIENT`이면 같은 retrieval 경로로 최대 1회 보강 조회하고, 여전히 부족하면 HTTP 200의 안전한 안내를 반환해야 한다.          | 구현      | 자동 검증 | `app/agent/evidence_eval.py`, `app/agent/nodes.py`, `app/tests/test_agent.py`, `tests/integration/test_chat_error_flow.py`; 재조회 1회와 최종 안내 확인               |
| FR-EVD-004 | `PARTIALLY_SUPPORTED`이면 확인된 근거만 사용하고 부분 실패 사유를 사용자에게 알려야 한다.                                         | 구현      | 자동 검증 | `app/agent/evidence_eval.py`, `app/agent/nodes.py`, `app/tests/test_agent.py`, `tests/integration/test_chat_error_flow.py`; 일부 Tool 실패 통합 테스트 통과           |
| FR-EVD-005 | `CONTRADICTED`이면 단일 사실로 확정하지 않고 담당자 확인이 필요함을 안내해야 한다.                                                | 구현      | 자동 검증 | `app/agent/evidence_eval.py`, `app/agent/nodes.py`, `app/tests/test_agent.py`, `tests/integration/test_chat_error_flow.py`; 충돌 fixture 테스트 통과                  |
| FR-EVD-006 | 문서 출처는 문서별로 합치고 페이지·발췌문의 중복을 제거하며, DB 쿼리 블록은 서로 다른 컬럼 구조를 보존한 독립 표로 변환해야 한다. | 구현      | 자동 검증 | `app/agent/evidence_eval.py`, `app/agent/nodes.py`, `app/tests/test_agent.py`, `tests/integration/test_chat_error_flow.py`; 출처 병합과 다중 table schema 테스트 통과 |

### 6.6 캐시

| ID           | 요구사항                                                                                                                                                                                 | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                                |
|--------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-CACHE-001 | 캐시는 Graph 실행 전에 조회하고 Graph가 완료된 뒤에만 저장해야 한다.                                                                                                                     | 구현      | 자동 검증 | `app/cache/`, `app/tests/test_cache.py`, `app/tests/test_api.py`, `tests/integration/test_cache_flow.py`; cache flow 테스트 통과                                           |
| FR-CACHE-002 | cache hit는 LLM 및 모든 MCP 호출을 생략하고 저장된 답변·route·근거 상태·출처·표를 반환해야 한다.                                                                                         | 구현      | 자동 검증 | `app/cache/`, `app/tests/test_cache.py`, `app/tests/test_api.py`, `tests/integration/test_cache_flow.py`; hit 시 외부 fake 호출 0회 확인                                   |
| FR-CACHE-003 | 키는 정규화 질문, 선택적 대화 문맥 해시, 사용자·역할·허용 DB, 문서/DB freshness, prompt 및 model 정보를 포함해야 한다. 요청의 `session_id` 원문과 Django 인증 세션 값은 포함하지 않는다. | 구현      | 자동 검증 | `app/cache/`, `app/tests/test_cache.py`, `app/tests/test_api.py`, `tests/integration/test_cache_flow.py`; 각 입력 차이와 동일 사용자 재로그인에 따른 키 동등성 테스트 통과 |
| FR-CACHE-004 | `GENERAL` 또는 `SUPPORTED` 결과만 저장하고 오류나 부분·부족·충돌 결과는 저장하지 않아야 한다.                                                                                            | 구현      | 자동 검증 | `app/cache/`, `app/tests/test_cache.py`, `app/tests/test_api.py`, `tests/integration/test_cache_flow.py`; 상태별 저장 여부 테스트 통과                                     |
| FR-CACHE-005 | 기본 TTL은 `GENERAL`·`DATABASE`·`BOTH` 300초, `DOCUMENT` 3600초여야 한다.                                                                                                                | 구현      | 자동 검증 | `app/cache/`, `app/tests/test_cache.py`, `app/tests/test_api.py`, `tests/integration/test_cache_flow.py`; TTL 정책 단위 테스트 통과                                        |

### 6.7 사용자 화면

| ID        | 요구사항                                                                                                                                                                                                 | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                                                                                   |
|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-UI-001 | Django는 로그인 화면과 인증 후 채팅 화면을 같은 origin에서 제공해야 한다.                                                                                                                                | 구현      | 자동 검증 | `django_app/web/`, `app/tests/test_web_auth.py`, `django_app/tests/test_web_ui.py`; Django UI 및 gateway route 테스트 통과                                                                                                    |
| FR-UI-002 | UI는 질문과 답변, route badge, cache 여부 및 근거 상태 안내를 표시해야 한다.                                                                                                                             | 구현      | 부분 검증 | `django_app/web/`, `app/tests/test_web_auth.py`, `django_app/tests/test_web_ui.py`; DOM 렌더링 테스트 또는 브라우저 확인                                                                                                      |
| FR-UI-003 | UI는 DB 결과를 표로 표시하고 생성 SQL을 펼쳐 볼 수 있게 해야 한다.                                                                                                                                       | 구현      | 부분 검증 | `django_app/web/`, `app/tests/test_web_auth.py`, `django_app/tests/test_web_ui.py`; 표·SQL 상세 렌더링 확인                                                                                                                   |
| FR-UI-004 | 숫자값과 라벨값이 있는 30행 이하 결과는 Chart.js 차트로 표시할 수 있어야 하며, 명시적 `chart_type`이 없으면 막대 차트를 사용해야 한다.                                                                   | 구현      | 부분 검증 | `django_app/web/`, `app/tests/test_web_auth.py`, `django_app/tests/test_web_ui.py`; chartable 응답과 기본 막대 차트 렌더링 확인                                                                                               |
| FR-UI-005 | UI는 문서 출처의 페이지·발췌문과 웹 출처 링크를 표시하고, 허용된 문서 다운로드를 제공해야 한다.                                                                                                          | 구현      | 부분 검증 | `django_app/web/`, `app/tests/test_web_auth.py`, `django_app/tests/test_web_ui.py`; 문서/웹 출처별 UI 확인                                                                                                                    |
| FR-UI-006 | UI는 보호 API의 `401` 응답 시 로그인 화면으로 전환하고, API 오류는 공개 `detail` 또는 정해진 상태 메시지로 표시하며, 네트워크·다운로드 실패에는 재시도 안내를 표시하되 내부 예외를 노출하지 않아야 한다. | 구현      | 부분 검증 | `django_app/web/static/web/chat.js`, `django_app/web/static/web/dashboard.js`, `django_app/web/static/web/report.js`, `app/tests/test_web_auth.py`, `django_app/tests/test_web_ui.py`; 오류 유형별 정적 계약 및 브라우저 확인 |
| FR-UI-007 | 로그아웃이나 인증 상태 변경 시 진행 중 요청과 이전 사용자의 화면 상태를 정리해야 한다.                                                                                                                   | 구현      | 자동 검증 | `django_app/web/`, `app/tests/test_web_auth.py`, `django_app/tests/test_web_ui.py`; 인증 상태 경쟁 조건 테스트 통과                                                                                                           |

### 6.8 대시보드·이상탐지

| ID          | 요구사항                                                                                                                                        | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                                                                                                                                                    |
|-------------|-------------------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-DASH-001 | Django는 `/dashboard/` 화면을 제공하고, UI는 `finance`와 `admin`에게만 대시보드 탭을 표시해야 한다.                                             | 구현      | 부분 검증 | `app/api/dashboard.py`, `app/api/anomalies.py`, `app/services/monthly_trends_service.py`, `app/services/anomaly_service.py`, `django_app/web/static/web/dashboard.js`, `app/tests/test_anomalies_api.py`, `app/tests/test_anomaly_service.py`; 역할별 탭 표시와 직접 URL 접근 안내 확인        |
| FR-DASH-002 | `GET /api/dashboard/monthly-trends`는 2000~2100년의 연도를 받아 판매·구매 월별 합계를 읽기 전용 고정 SQL로 병렬 조회해야 한다.                  | 구현      | 수동 검증 | `app/api/dashboard.py`, `app/services/monthly_trends_service.py`; 전용 자동 테스트 부재로 실제 또는 fake client를 이용한 응답 schema·SQL guard·병렬 호출 확인 필요                                                                                                                             |
| FR-DASH-003 | `GET /api/anomalies`는 판매·구매 각각의 금액 이상치, 연체, 거래 급증 규칙을 고정 SQL로 병렬 실행하고 공통 행 형식으로 반환해야 한다.            | 구현      | 자동 검증 | `app/api/dashboard.py`, `app/api/anomalies.py`, `app/services/monthly_trends_service.py`, `app/services/anomaly_service.py`, `django_app/web/static/web/dashboard.js`, `app/tests/test_anomalies_api.py`, `app/tests/test_anomaly_service.py`; 6개 규칙의 schema·도메인·SQL guard 단위 테스트  |
| FR-DASH-004 | 대시보드 API는 두 업무 DB 모두에 접근 가능한 인증 사용자만 허용하고 `hr` 요청은 조회 전에 `403`으로 거부해야 한다.                              | 구현      | 부분 검증 | `app/api/dashboard.py`, `app/api/anomalies.py`, `app/services/monthly_trends_service.py`, `app/services/anomaly_service.py`, `django_app/web/static/web/dashboard.js`, `app/tests/test_anomalies_api.py`, `app/tests/test_anomaly_service.py`; 미인증 `401`, 권한 없음 `403`, 허용 역할 테스트 |
| FR-DASH-005 | 이상탐지 서비스는 정의된 6개 규칙을 독립 실행하고, 한 규칙이 실패하면 그 규칙 결과만 제외한 채 성공한 규칙의 결과를 반환해야 한다.              | 구현      | 자동 검증 | `app/services/anomaly_service.py`, `app/tests/test_anomaly_service.py`; 6개 규칙과 규칙별 부분 실패 격리 확인                                                                                                                                                                                  |
| FR-DASH-006 | UI는 최근 월 매출·구매, 전월 대비, 연체 총액, 이상 신호 수, 월별 선 차트와 도메인별 이상 신호 중 금액 상위 최대 4개를 KRW 단위로 표시해야 한다. | 구현      | 부분 검증 | `app/api/dashboard.py`, `app/api/anomalies.py`, `app/services/monthly_trends_service.py`, `app/services/anomaly_service.py`, `django_app/web/static/web/dashboard.js`, `app/tests/test_anomalies_api.py`, `app/tests/test_anomaly_service.py`; 정적 UI 계약 테스트 및 브라우저 확인            |
| FR-DASH-007 | 월별 추이 조회에서 판매·구매 중 한 도메인이 실패하면 실패한 도메인은 빈 결과로 반환하고 성공한 도메인의 결과는 유지해야 한다.                   | 구현      | 수동 검증 | `app/services/monthly_trends_service.py`, `app/api/dashboard.py`; 전용 자동 테스트 부재로 실제 또는 fake client를 이용한 부분 실패 확인 필요                                                                                                                                                   |

### 6.9 DOCX 리포트

| ID         | 요구사항                                                                                                                                      | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                                                                                                                                                                                      |
|------------|-----------------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-RPT-001 | Django는 `/report/` 화면을 제공하고, UI는 `finance`와 `admin`에게만 리포트 탭을 표시해야 한다.                                                | 구현      | 부분 검증 | `app/api/reports.py`, `app/services/report_templates.py`, `app/services/report_service.py`, `django_app/web/static/web/report.js`, `app/tests/test_report_dependencies.py`, `app/tests/test_report_service.py`, `app/tests/test_reports_api.py`, `app/tests/test_docx_builder.py`; 역할별 탭 표시와 직접 URL 접근 안내 확인      |
| FR-RPT-002 | `GET /api/reports/templates`는 등록된 리포트 템플릿의 ID, 이름, 설명을 반환해야 한다.                                                         | 구현      | 자동 검증 | `app/api/reports.py`, `app/services/report_templates.py`, `app/services/report_service.py`, `django_app/web/static/web/report.js`, `app/tests/test_report_dependencies.py`, `app/tests/test_report_service.py`, `app/tests/test_reports_api.py`, `app/tests/test_docx_builder.py`; 템플릿 목록 API 테스트 통과                   |
| FR-RPT-003 | `POST /api/reports/generate`는 템플릿 ID와 시작·종료일을 검증하고 템플릿이 요구하는 모든 DB 권한을 조회 전에 확인해야 한다.                   | 구현      | 자동 검증 | `app/api/reports.py`, `app/services/report_templates.py`, `app/services/report_service.py`, `django_app/web/static/web/report.js`, `app/tests/test_report_dependencies.py`, `app/tests/test_report_service.py`, `app/tests/test_reports_api.py`, `app/tests/test_docx_builder.py`; 인증·권한·미등록 템플릿·역전 기간 테스트 통과 |
| FR-RPT-004 | 현재 `sales_monthly` 템플릿은 매출 추이, 고객별 순위, 미수금 현황을 판매 Data Tool로 조회해 표와 선택적 차트를 포함한 DOCX로 조립해야 한다.   | 구현      | 자동 검증 | `app/api/reports.py`, `app/services/report_templates.py`, `app/services/report_service.py`, `django_app/web/static/web/report.js`, `app/tests/test_report_dependencies.py`, `app/tests/test_report_service.py`, `app/tests/test_reports_api.py`, `app/tests/test_docx_builder.py`; 서비스와 DOCX 재개봉·구성 단위 테스트 통과    |
| FR-RPT-005 | 생성 문서는 서버 디스크에 남기지 않고 DOCX media type과 UTF-8 파일명이 있는 attachment 응답으로 스트리밍해야 한다.                            | 구현      | 자동 검증 | `app/api/reports.py`, `app/services/report_templates.py`, `app/services/report_service.py`, `django_app/web/static/web/report.js`, `app/tests/test_report_dependencies.py`, `app/tests/test_report_service.py`, `app/tests/test_reports_api.py`, `app/tests/test_docx_builder.py`; 다운로드 header와 본문 형식 API 테스트 통과   |
| FR-RPT-006 | UI는 템플릿·기간 선택, 생성 진행·실패 상태 및 성공한 DOCX 자동 다운로드를 제공해야 한다.                                                      | 구현      | 부분 검증 | `app/api/reports.py`, `app/services/report_templates.py`, `app/services/report_service.py`, `django_app/web/static/web/report.js`, `app/tests/test_report_dependencies.py`, `app/tests/test_report_service.py`, `app/tests/test_reports_api.py`, `app/tests/test_docx_builder.py`; 정적 UI 계약 테스트 및 브라우저 확인          |
| FR-RPT-007 | 템플릿의 섹션 조회는 병렬 실행하고, 정상 무결과 섹션은 빈 섹션으로 남기되 권한·timeout·query·payload 오류는 리포트 생성 실패로 처리해야 한다. | 구현      | 자동 검증 | `app/api/reports.py`, `app/services/report_templates.py`, `app/services/report_service.py`, `django_app/web/static/web/report.js`, `app/tests/test_report_dependencies.py`, `app/tests/test_report_service.py`, `app/tests/test_reports_api.py`, `app/tests/test_docx_builder.py`; 무결과 섹션과 비정상 Tool 오류 테스트 통과    |

### 6.10 문서 처리·RAG 품질 평가

| ID          | 요구사항                                                                                                                          | 구현 상태   | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                              |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------|-------------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-RAGQ-001 | PDF 로더는 기본 pypdf 경로를 제공하고, `ENABLE_DOCLING_CAPTIONING=true`일 때 Docling 이미지 캡션을 페이지 텍스트에 포함해야 한다. | 조건부 구현 | 자동 검증 | `ingestion/loaders.py`, `scripts/rag_ground_truth_label.py`, `scripts/rag_eval_metrics.py`, `app/tests/test_docling_loader.py`; 캡션 포함·미검출·비활성 단위 테스트 통과 |
| FR-RAGQ-002 | Docling 처리 실패 시 전체 인덱싱을 중단하지 않고 pypdf 로더로 폴백해야 한다.                                                      | 구현        | 자동 검증 | `ingestion/loaders.py`, `scripts/rag_ground_truth_label.py`, `scripts/rag_eval_metrics.py`, `app/tests/test_docling_loader.py`; 예외 폴백 단위 테스트 통과               |
| FR-RAGQ-003 | 오프라인 평가 도구는 질문별 검색 후보의 관련성 라벨을 생성하고 Recall@k, Precision@k, MRR, nDCG를 계산할 수 있어야 한다.          | 구현        | 수동 검증 | `scripts/rag_ground_truth_label.py`, `scripts/rag_eval_metrics.py`; 대표 fixture 실행 결과와 도메인 담당자의 qrels 승인 확인 필요                                        |

### 6.11 배치·초기화·상태 확인

| ID         | 요구사항                                                                                                                                  | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                                                                                                            |
|------------|-------------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-OPS-001 | 문서 등록·인덱싱과 구매·판매 ETL은 명시적 CLI 배치로만 실행해야 한다.                                                                     | 구현      | 부분 검증 | `setup_all.py`, `scripts/ensure_databases_and_accounts.py`, `scripts/ensure_views_and_readers.py`, `app/api/system.py`, `deploy/nginx/local.conf`, `app/tests/test_setup_all.py`, `app/tests/test_api.py`; 채팅 경로에서 배치 호출 부재 확인           |
| FR-OPS-002 | 통합 초기화 도구는 기본 실행에서 계획만 출력하고 `--apply`가 있을 때만 DB·인덱스·ETL을 변경해야 한다.                                     | 구현      | 자동 검증 | `setup_all.py`, `scripts/ensure_databases_and_accounts.py`, `scripts/ensure_views_and_readers.py`, `app/api/system.py`, `deploy/nginx/local.conf`, `app/tests/test_setup_all.py`, `app/tests/test_api.py`; dry-run과 apply 분리 테스트                 |
| FR-OPS-003 | 초기화 도구는 인프라·Django·문서·구매·판매 단계 생략, 관리자 생성, 원본 workbook 경로 지정을 지원해야 한다.                               | 구현      | 자동 검증 | `setup_all.py`, `scripts/ensure_databases_and_accounts.py`, `scripts/ensure_views_and_readers.py`, `app/api/system.py`, `deploy/nginx/local.conf`, `app/tests/test_setup_all.py`, `app/tests/test_api.py`; CLI option과 단계 조립 테스트               |
| FR-OPS-004 | `setup_all.py --apply`에서 `--skip-infra`를 지정하지 않으면 선택한 mutation 단계보다 먼저 MySQL 데이터베이스와 쓰기 계정을 준비해야 한다. | 구현      | 자동 검증 | `setup_all.py`, `app/tests/test_setup_all.py`; 인프라 준비 선행·생략 순서 확인                                                                                                                                                                         |
| FR-OPS-005 | `GET /api/health`는 인증 없이 프로세스 liveness만 `{"status":"ok"}`로 반환해야 한다.                                                      | 구현      | 자동 검증 | `setup_all.py`, `scripts/ensure_databases_and_accounts.py`, `scripts/ensure_views_and_readers.py`, `app/api/system.py`, `deploy/nginx/local.conf`, `app/tests/test_setup_all.py`, `app/tests/test_api.py`; health API 테스트 통과                      |
| FR-OPS-006 | 로컬 gateway는 Django, FastAPI, 정적 파일 및 비공개 내부 인증 경로를 계약된 prefix에 따라 분리해야 한다.                                  | 구현      | 부분 검증 | `setup_all.py`, `scripts/ensure_databases_and_accounts.py`, `scripts/ensure_views_and_readers.py`, `app/api/system.py`, `deploy/nginx/local.conf`, `app/tests/test_setup_all.py`, `app/tests/test_api.py`; Nginx 설정 검사와 동일 origin 브라우저 검증 |
| FR-OPS-007 | `setup_all.py --apply`는 `build_steps` 순서에 따라 migration, 문서 등록·인덱싱, 선택된 구매·판매 ETL을 실행해야 한다.                     | 구현      | 자동 검증 | `setup_all.py`, `app/tests/test_setup_all.py`; 선택 단계와 실행 순서 확인                                                                                                                                                                              |
| FR-OPS-008 | `--skip-infra`를 지정하지 않고 구매 또는 판매 ETL을 선택하면, 선택된 모든 ETL 완료 후 허용 View와 도메인별 reader 계정을 준비해야 한다.   | 구현      | 부분 검증 | `setup_all.py`, `scripts/ensure_views_and_readers.py`, `app/tests/test_setup_all.py`; 호출 순서 자동 검증 및 실제 MySQL 권한 수동 확인                                                                                                                 |

## 7. 비기능 요구사항

비기능 요구사항도 현재 기준선의 구현과 검증 수준을 함께 추적한다.

- 구현 상태는 `구현`, `부분 구현`, `배포 범위 외`, `결정 필요`로 구분한다.
- 검증 상태는 `자동 검증`, `부분 검증`, `수동 검증`으로 구분한다.
- 정량 기준이나 운영 환경이 확정되지 않은 항목은 임의 수치를 부여하지 않고 연결된 `TBD-*`, `GAP-*`, `VAL-*`로 완료 조건을 관리한다.

### 7.1 보안 및 개인정보

| ID          | 요구사항                                                                                                                                                       | 구현 상태    | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                 |
|-------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| NFR-SEC-001 | API key, 비밀번호, 인증 header, cookie, 질문 원문, 전체 근거 및 내부 `file_path`를 로그에 기록하거나 공개 응답에 포함해서는 안 된다.                           | 부분 구현    | 부분 검증 | `app/core/security.py`, `app/logging/`, `app/tests/test_logging.py`; 자동 마스킹 검증 외에 운영 access/error log 표본 점검 필요                             |
| NFR-SEC-002 | `DJANGO_SECRET_KEY`와 `AUTH_INTROSPECTION_KEY`는 서로 다른 32자 이상의 비밀값이어야 하며 저장소에 커밋하지 않아야 한다.                                        | 구현         | 자동 검증 | `django_app/config/settings.py`, `app/core/config.py`, `app/tests/test_auth.py`; 누락·길이·동일 값 거부 확인                                                |
| NFR-SEC-003 | 내부 introspection endpoint는 공개 gateway에 노출하지 않아야 한다. loopback이 아닌 원격 구간을 사용할 경우 TLS 또는 service mesh 보호를 적용해야 한다.         | 부분 구현    | 부분 검증 | `deploy/nginx/local.conf`, `django_app/accounts/`, `django_app/tests/test_auth_api.py`; 로컬 비공개 경로 확인, 원격 보호는 `GAP-006`·`TBD-005` 적용 후 검증 |
| NFR-SEC-004 | FastAPI는 Django secret, account DB 및 세션 테이블에 직접 접근해서는 안 된다.                                                                                  | 구현         | 자동 검증 | `app/auth/`, `app/core/config.py`, `app/tests/test_auth.py`; 내부 introspection client 경계와 설정 계약 확인                                                |
| NFR-SEC-005 | 운영 gateway는 합의된 요청 수·시간창으로 로그인 endpoint rate limit을 설정하고, 인증 header·cookie·request body를 인증 access log에서 제외해야 한다.           | 배포 범위 외 | 수동 검증 | `GAP-006`, `TBD-005`; 운영 값 확정 후 제한 초과 응답과 access log 표본 검증                                                                                 |
| NFR-SEC-006 | UI가 표시하는 동적 문자열은 HTML로 해석하지 않도록 처리하고, 외부 URL은 `http`·`https`만 허용하며, 문서 다운로드는 서버가 발급한 문서 ID 경로만 사용해야 한다. | 구현         | 부분 검증 | `django_app/web/static/web/chat.js`, `app/api/documents.py`, `app/tests/test_web_auth.py`; 정적 계약과 악성 문자열·URL·문서 ID 브라우저 검증                |

### 7.2 성능 및 확장성

| ID           | 요구사항                                                                                                          | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                                                 |
|--------------|-------------------------------------------------------------------------------------------------------------------|-----------|-----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| NFR-PERF-001 | `BOTH`의 독립적인 문서·DB 검색은 병렬 실행해야 한다.                                                              | 구현      | 자동 검증 | `app/agent/graph.py`, `app/tests/test_agent.py`; 병렬 fan-out·join 확인                                                                                                                     |
| NFR-PERF-002 | 영구 FAISS 인덱스는 프로세스에서 재사용하며 질문마다 원문 재로딩이나 임시 인덱스 생성을 하지 않아야 한다.         | 구현      | 자동 검증 | `ingestion/index.py`, `app/tests/test_ingestion.py`; 저장 인덱스 재로딩·재사용 확인                                                                                                         |
| NFR-PERF-003 | cache hit는 Graph, LLM 및 Tool 호출을 완전히 단락해야 한다.                                                       | 구현      | 자동 검증 | `app/cache/service.py`, `app/api/chat.py`, `app/tests/test_cache.py`; hit 시 하위 호출 0회 확인                                                                                             |
| NFR-PERF-004 | Text2SQL은 도메인별 최대 3개 쿼리 블록을 만들고 각 결과를 최대 200행으로 제한해야 한다.                           | 구현      | 자동 검증 | `mcp_servers/data_tools/purchase/sql_guard.py`, `mcp_servers/data_tools/sales/sql_guard.py`, `app/tests/test_purchase_text2sql.py`, `app/tests/test_sales_text2sql.py`; 초과 입력 거부 확인 |
| NFR-PERF-005 | 정량 응답시간·처리량 SLO는 운영 인프라 실측 후 별도로 확정해야 하며, 현재 문서에서는 임의 목표를 설정하지 않는다. | 결정 필요 | 수동 검증 | `TBD-001`; 대상 인프라·부하 모델·측정 결과 승인 시 완료                                                                                                                                     |

### 7.3 신뢰성 및 오류 처리

| ID          | 요구사항                                                                                                                                                       | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                                                                                                                                              |
|-------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| NFR-REL-001 | 외부 Tool 경계의 timeout, 권한, 입력, 무결과, query 및 payload 오류를 구분해야 한다.                                                                           | 구현      | 자동 검증 | `app/mcp/client.py`, `app/tests/test_data_mcp.py`, `tests/integration/test_chat_error_flow.py`; 오류별 공개 코드 확인                                                                                                                                    |
| NFR-REL-002 | `BOTH` 또는 양 DB 조회 중 일부가 실패해도 유효한 다른 근거가 있으면 부분 응답을 제공해야 한다. 모든 근거가 실패하면 오류를 정상 무결과로 위장하지 않아야 한다. | 구현      | 자동 검증 | `app/agent/nodes.py`, `app/tests/test_agent.py`, `tests/integration/test_chat_error_flow.py`; 부분·전체 실패 분기 확인                                                                                                                                   |
| NFR-REL-003 | ETL은 재실행 가능한 UPSERT와 검증 절차를 유지해야 하며 온라인 요청과 격리되어야 한다.                                                                          | 구현      | 부분 검증 | `etl/purchase/`, `etl/sales/`, `app/tests/test_etl.py`; 변환·재실행 단위 검증, 실제 MySQL 검증은 `VAL-002`                                                                                                                                               |
| NFR-REL-004 | 기존 계정 이관 전 복구 가능한 백업을 만들고 dry-run 감사 결과를 보존해야 하며, 이관 과정에서 원본 계정 DB를 삭제해서는 안 된다.                                | 부분 구현 | 수동 검증 | `django_app/accounts/migrations/0002_import_legacy_accounts.py`, `django_app/accounts/management/commands/audit_legacy_accounts.py`; 백업 복구 시험과 감사 산출물 확인 필요                                                                              |
| NFR-REL-005 | 대시보드의 독립 규칙·도메인 조회는 부분 실패를 격리해야 하며, 리포트 생성의 필수 조회 실패는 정상 빈 결과로 위장하지 않아야 한다.                              | 구현      | 부분 검증 | `app/services/anomaly_service.py`, `app/services/monthly_trends_service.py`, `app/services/report_service.py`, `app/tests/test_anomaly_service.py`, `app/tests/test_report_service.py`, `app/tests/test_reports_api.py`; 월별 추이는 `VAL-003` 추가 검증 |

### 7.4 관측성 및 운영성

| ID          | 요구사항                                                                                                                                                                              | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                |
|-------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|----------------------------------------------------------------------------------------------------------------------------|
| NFR-OBS-001 | 모든 FastAPI 응답은 `X-Request-ID`와 `Server-Timing`을 제공해야 한다.                                                                                                                 | 구현      | 자동 검증 | `app/main.py`, `app/tests/test_api.py`, `app/tests/test_performance.py`; 모든 응답 header 확인                             |
| NFR-OBS-002 | 채팅 응답의 `request_id`는 응답 header의 ID와 일치해야 한다.                                                                                                                          | 구현      | 자동 검증 | `app/api/chat.py`, `app/tests/test_api.py`; body·header ID 일치 확인                                                       |
| NFR-OBS-003 | 요청 완료 로그는 `request_id`, method, path, status와 적용 가능한 route, evidence status, cache hit/miss, 단계별 timing을 기록하되 질문 원문·전체 근거·비밀값은 기록하지 않아야 한다. | 부분 구현 | 부분 검증 | `app/logging/`, `app/tests/test_logging.py`, `app/tests/test_performance.py`; 필드·마스킹 자동 검증 및 운영 로그 표본 확인 |
| NFR-OBS-004 | `/api/health`는 liveness 의미만 가지며 외부 의존성 readiness 성공으로 해석해서는 안 된다.                                                                                             | 구현      | 자동 검증 | `app/api/system.py`, `app/tests/test_api.py`; 응답 body와 외부 의존성 미호출 확인                                          |

### 7.5 유지보수성 및 호환성

| ID          | 요구사항                                                                                                                                                      | 구현 상태 | 검증 상태 | 구현·검증 근거 및 수용 기준                                                                                                               |
|-------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------|-------------------------------------------------------------------------------------------------------------------------------------------|
| NFR-MNT-001 | 공개 요청·응답은 Pydantic model, Graph 상태는 `GraphState`, MCP 응답은 공통 envelope로 검증해야 한다.                                                         | 구현      | 자동 검증 | `app/schemas/`, `app/agent/state.py`, `app/schemas/mcp.py`, `app/tests/test_api.py`, `app/tests/test_data_mcp.py`; 경계 validation 확인   |
| NFR-MNT-002 | I/O 경계는 비동기 계약을 유지하고 새 함수에는 Python 타입을 명시해야 한다.                                                                                    | 부분 구현 | 부분 검증 | 관련 코드의 async·type annotation 검토; 저장소에 정적 타입 검사 도구가 없어 변경 리뷰로 확인                                              |
| NFR-MNT-003 | UI는 현재 구조에 맞춰 vanilla HTML/CSS/JavaScript와 Chart.js를 사용하며 별도 프론트엔드 런타임을 도입하지 않아야 한다.                                        | 구현      | 자동 검증 | `django_app/web/`, `django_app/tests/test_web_ui.py`; template·static 계약 확인                                                           |
| NFR-MNT-004 | 환경 변수 계약 변경 시 `app/core/config.py`와 비밀값 없는 `.env.example`을 함께 갱신해야 한다.                                                                | 부분 구현 | 부분 검증 | `app/core/config.py`, `.env.example`; 변경 시 diff review가 필요하며 자동 동기화 검사는 없음                                              |
| NFR-MNT-005 | Tool/API 이름, envelope, 권한, route, cache key 또는 DB schema 변경 시 코드·Pydantic model, fixture, 테스트와 관련 계약 문서를 같은 변경에서 동기화해야 한다. | 부분 구현 | 부분 검증 | 현재 정본은 코드·Pydantic model이며 문서 차이는 `DOC-001`·`DOC-002`로 추적; 변경 시 계약 테스트와 문서 review 필요                        |
| NFR-MNT-006 | 대시보드의 반복 조회는 LLM/Text2SQL 없이 SQL guard를 통과하는 고정 SQL과 도메인별 read-only client를 사용해야 한다.                                           | 구현      | 자동 검증 | `app/services/anomaly_service.py`, `app/services/monthly_trends_service.py`, `app/tests/test_anomaly_service.py`; 고정 query와 guard 확인 |
| NFR-MNT-007 | 애플리케이션 Python runtime은 루트 `pyproject.toml`의 `>=3.11,<3.12` 계약을 따라야 한다.                                                                      | 구현      | 부분 검증 | `pyproject.toml`, `app/tests/test_import_smoke.py`; 지원 버전 정적 확인과 실제 Python 3.11 환경의 전체 테스트 필요                        |

## 8. 공개 인터페이스 요약

| Method | Endpoint                                 | 소유 서비스 | 인증                     | 목적                         |
|--------|------------------------------------------|-------------|--------------------------|------------------------------|
| `GET`  | `/`                                      | Django      | 선택                     | 로그인 또는 채팅 UI 제공     |
| `GET`  | `/dashboard/`                            | Django      | UI에서 session 확인      | 이상탐지 대시보드 shell 제공 |
| `GET`  | `/report/`                               | Django      | UI에서 session 확인      | DOCX 리포트 생성 shell 제공  |
| `GET`  | `/api/auth/csrf`                         | Django      | 불필요                   | CSRF token 발급              |
| `POST` | `/api/auth/login`                        | Django      | CSRF                     | 로그인 및 세션 발급          |
| `POST` | `/api/auth/logout`                       | Django      | session + CSRF           | 세션 폐기                    |
| `GET`  | `/api/auth/me`                           | Django      | session                  | 현재 사용자 profile 조회     |
| `POST` | `/api/chat`                              | FastAPI     | session                  | 질문 처리 및 답변 반환       |
| `GET`  | `/api/documents/download?doc_id=...`     | FastAPI     | session + 문서 권한      | 등록 문서 다운로드           |
| `GET`  | `/api/dashboard/monthly-trends?year=...` | FastAPI     | session + 판매·구매 권한 | 연도별 월간 매출·구매 합계   |
| `GET`  | `/api/anomalies`                         | FastAPI     | session + 판매·구매 권한 | 고정 규칙 이상 신호 목록     |
| `GET`  | `/api/reports/templates`                 | FastAPI     | 불필요                   | 등록 리포트 템플릿 목록      |
| `POST` | `/api/reports/generate`                  | FastAPI     | session + 템플릿 DB 권한 | 기간별 DOCX 리포트 생성      |
| `GET`  | `/api/health`                            | FastAPI     | 불필요                   | 프로세스 liveness 확인       |
| `POST` | `/internal/auth/introspect`              | Django 내부 | 내부 key + session       | FastAPI 전용 세션 검증       |

공개 오류 코드와 Tool envelope의 상세 필드는 현재 코드와 Pydantic model을 정본으로 하며, [HTTP·MCP 인터페이스](interface.md)는 이를 설명하는 보조 문서로 사용한다.

## 9. 데이터 요구사항

- account DB는 Django만 읽고 쓰며 Django migration으로 schema를 관리한다.
- document DB는 활성 문서 ID와 등록 경로 metadata를 관리하고 Document Tool만 접근한다.
- 원문은 `data/raw/**`, 생성 인덱스는 `data/faiss/**`에 위치하며 Git 추적 대상이 아니다.
- 구매·판매 원천 workbook은 오프라인 ETL 입력이며 런타임 채팅 경로에서 읽지 않는다.
- 구매·판매 런타임 조회는 도메인별 허용 View와 read-only 계정을 사용한다.
- 문서 Source는 인덱스 metadata에 값이 있을 때 `source_version`을 제공한다. DB Source·TableData의 선택 metadata는 FR-SQL-009에 따라 값이 있으면 전달하고
  없으면 `null`로 반환한다.
- 대시보드 조회는 판매 `v_sales_order`·`v_invoice`, 구매 `v_purchase_order`·`v_vendor_invoice` 등 허용 View만 사용한다.
- 생성 리포트는 메모리에서 조립해 응답하며 서버의 영구 파일 또는 사용자별 리포트 이력을 만들지 않는다.
- 자동 생성한 RAG qrels는 초안이며 관련성 2~3점과 애매한 사례를 사람이 검토한 뒤 golden set으로 확정한다.
- 테스트 데이터는 비식별 소형 fixture와 결정적인 fake/mock을 사용한다.

## 10. 수용 기준 및 추적성

6절과 7절의 각 요구사항 행에 있는 구현·검증 근거 및 수용 기준이 ID 단위 추적성의 정본이다. `자동 검증`은 명시한 테스트가 해당 요구를 직접 실행하는 경우에만 사용하며, `부분 검증`과 `수동 검증`은 행에
남은 수용 조건을 기록한다. 아래 표는 영역별 보조 요약이며 ID별 근거를 대체하지 않는다.

| 요구사항 영역  | 자동 검증 요약                                                 | 추가 수용 검증                                         |
|----------------|----------------------------------------------------------------|--------------------------------------------------------|
| 인증·RBAC      | Django/FastAPI 인증, CSRF, 세션, 역할별 Tool 거부 테스트       | 실제 gateway에서 로그인·로그아웃·만료·Admin 접근 확인  |
| 라우팅·Graph   | routing fixture, route별 호출, `BOTH` 병렬 병합, 재조회 테스트 | 대표 일반·문서·DB·복합 질문 시연                       |
| 문서 RAG       | fixture 인덱싱, 검색, 출처, 다운로드 계약 테스트               | 실제 문서 DB·FAISS·원문을 연결한 전체 흐름             |
| Text2SQL       | SQL guard, 구매·판매 golden case, fake DB 계약 테스트          | 실제 read-only 계정·View·EXPLAIN·결과 정확성 검증      |
| 근거 평가      | 지원·부분·부족·충돌 상태 테스트                                | 도메인 담당자의 답변·출처 정확성 검토                  |
| 캐시           | hit 단락, 키 격리, TTL, 저장 정책 테스트                       | 인덱스 재생성·ETL 후 freshness 및 무효화 확인          |
| UI             | Django template/static/auth 상태 테스트                        | 동일 origin 브라우저에서 표·차트·출처·다운로드 확인    |
| 대시보드       | 이상탐지 API·서비스·SQL guard·부분 실패 테스트                 | 실제 read-only DB에서 KPI·월별 추이·이상 신호 확인     |
| 리포트         | 템플릿·권한·서비스·DOCX 조립·스트리밍 API 테스트               | 실제 Data Tool 결과로 생성한 DOCX의 내용·레이아웃 확인 |
| 문서 처리·평가 | Docling 폴백·캡션 단위 테스트, 평가 스크립트 실행              | 실제 PDF 캡션 품질과 사람이 검토한 qrels 확정          |
| 운영           | 설정·import smoke, health, Nginx config test                   | 실제 외부 서비스 readiness 및 장애 복구 확인           |

변경 완료 시 다음 명령을 기준으로 검증한다. 외부 서비스 없이 통과한 fake/mock 테스트를 실제 MySQL, Redis, 원격 MCP 또는 운영 FAISS 통합 성공으로 해석하지 않는다.

```powershell
python -m pytest django_app/tests
python -m pytest app/tests
python -m pytest tests/integration
python -m pytest
git diff --check
git status --short
```

`pytest.ini`의 실제 자동 수집 경로는 `django_app/tests`, `app/tests`, `tests/integration`이다. 별도 `tests/unit` 디렉터리는 현재 존재하지 않는다.

## 11. 제약사항 및 현행 기술 기준선

### 11.1 제약사항

제약사항은 현재 시스템이 동작할 때 반드시 유지해야 하는 기술·보안·운영 조건이다. 구현되지 않은 향후 기능이나 테스트 공백은 이 절에 포함하지 않는다.

| ID      | 제약사항                                                                                                                                             | 근거                                                                                            |
|---------|------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| CON-001 | FastAPI와 Agent는 문서·구매·판매 저장소에 직접 접근하지 않고 MCP client 경계를 사용해야 한다.                                                        | `app/mcp/client.py`, `app/agent/nodes.py`                                                       |
| CON-005 | 문서 다운로드 경로는 같은 프로세스의 MCP 경계에서 해석하고 HTTP 응답에는 내부 경로를 노출하지 않는다.                                                | `app/api/documents.py`, `app/mcp/client.py`                                                     |
| CON-006 | Django의 `/dashboard/`, `/report/`는 HTML shell을 제공하며, 실제 업무 데이터 접근 권한은 FastAPI 데이터 API에서 서버 측으로 강제해야 한다.           | `django_app/web/views.py`, `app/api/dashboard.py`, `app/api/anomalies.py`, `app/api/reports.py` |
| CON-007 | `GET /api/reports/templates`는 비민감 템플릿 metadata만 공개하고, 데이터 조회와 DOCX 생성은 인증된 `POST /api/reports/generate`에서만 수행해야 한다. | `app/api/reports.py`, `app/services/report_templates.py`                                        |

### 11.2 현행 기술 기준선

다음 항목은 변경 불가능한 제약이 아니라 현재 구현 방식이다. 연결된 교체 조건이 승인·구현되면 요구사항과 테스트를 갱신한 뒤 기준선을 변경할 수 있다.

| ID       | 현재 기준선                                                                | 교체 조건                                              | 근거                                                  |
|----------|----------------------------------------------------------------------------|--------------------------------------------------------|-------------------------------------------------------|
| BASE-001 | MCP 호출은 같은 프로세스의 `InProcessMCPPort`를 사용한다.                  | `GAP-001` 구현 및 `TBD-003`의 transport 계약 확정      | `app/core/dependencies.py`, `app/mcp/client.py`       |
| BASE-002 | 응답 캐시는 프로세스별 `MemoryCache`이며 인스턴스 간 값을 공유하지 않는다. | `GAP-002` 구현 및 `TBD-002`의 캐시·무효화 계약 확정    | `app/cache/repository.py`, `app/core/dependencies.py` |
| BASE-003 | `/api/health`는 프로세스 liveness만 나타낸다.                              | `GAP-004` 구현 및 `TBD-004`의 readiness 판정 기준 확정 | `app/api/system.py`                                   |

# 요구사항 정의서

## 1. 문서 개요

| 항목 | 내용 |
|---|---|
| 문서명 | 사내 문서 RAG·업무 데이터 Text2SQL 챗봇 요구사항 정의서 |
| 기준일 | 2026-08-25 |
| 기준 시스템 | Django + FastAPI + LangGraph + MCP 기반 챗봇 |
| 문서 목적 | 현재 구현과 계약 문서를 기준으로 시스템의 범위, 기능, 품질, 보안 및 수용 기준을 식별 가능한 요구사항으로 정의한다. |
| 관련 문서 | [아키텍처](architecture.md), [HTTP·MCP 인터페이스](interface.md), [소유권](ownership.md), [테스트 시나리오](test-scenarios.md), [Django·FastAPI 분리 계획](django-fastapi-separation-plan.md) |

이 문서는 신규 목표를 임의로 추가하는 기획안이 아니라 현재 저장소의 구현과 계약을 정리한
기준선이다. 아직 구현되지 않았거나 외부 환경에서 확인해야 하는 항목은 별도의 제한사항과
추후 결정 항목으로 구분한다. HTTP 및 MCP payload의 상세 형식은
`docs/interface.md`를 정본으로 한다.

## 2. 배경 및 목표

조직 구성원은 사내 규정·업무 문서와 구매·판매 데이터가 서로 다른 저장소에 있어 필요한
정보를 찾고 해석하는 데 시간이 든다. 본 시스템은 하나의 채팅 UI와 API에서 자연어 질문을
받아 다음 목표를 달성한다.

1. 사내 문서를 검색하고 근거 문서, 페이지 및 발췌문과 함께 답변한다.
2. 구매·판매 질문을 읽기 전용 SQL로 변환하고 조회 결과를 표와 차트로 제공한다.
3. 문서와 업무 데이터가 함께 필요한 질문은 두 근거를 결합하되 출처를 분리한다.
4. 인증된 사용자의 역할에 따라 접근 가능한 데이터베이스를 제한한다.
5. 근거의 품질과 충돌 여부를 평가해 확인되지 않은 사실의 생성을 억제한다.
6. 계정·UI, 채팅 오케스트레이션, Tool, 배치 작업의 책임을 분리해 안전하게 운영한다.

## 3. 이해관계자와 사용자 역할

| 구분 | 주요 관심사 및 권한 |
|---|---|
| 일반 업무 사용자 | 로그인, 자연어 질문, 답변·출처·표·차트 확인, 허용 문서 다운로드 |
| `hr` 역할 | `document_db`만 접근 가능하며 구매·판매 DB에는 접근 불가 |
| `finance` 역할 | `document_db`, `purchase_db`, `sales_db` 접근 가능 |
| `admin` 역할 | 세 업무 DB 접근 가능. Django Admin 권한은 별도의 `is_staff` 정책으로 관리 |
| 운영자 | 환경 설정, 프로세스·gateway 운영, 로그 확인, 계정 migration 및 비밀 관리 |
| 데이터 담당자 | 구매·판매 ETL, 읽기 전용 View와 계정, 데이터 품질 및 freshness 관리 |
| 문서/RAG 담당자 | 문서 등록, 청킹·임베딩, FAISS 재생성, 검색 품질 관리 |
| 개발·검증 담당자 | API·MCP 계약, fake 기반 회귀 테스트, 실제 인프라 수용 테스트 관리 |

## 4. 시스템 범위

### 4.1 포함 범위

- Django 기반 사용자 화면, 계정, 로그인·로그아웃, 서버 세션 및 Django Admin
- FastAPI 기반 채팅, 문서 다운로드 및 liveness API
- 질문을 `GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH`로 분류하는 LangGraph 흐름
- Document Tool을 통한 하이브리드 문서 검색과 원문 다운로드 경로 해석
- Purchase/Sales Data Tool을 통한 자연어 Text2SQL 및 읽기 전용 조회
- 근거 평가, 답변 합성, 출처·표·차트용 응답 생성
- 사용자·세션·근거 freshness가 격리된 응답 캐시
- 문서 등록·인덱싱과 구매·판매 ETL을 수행하는 오프라인 배치
- 동일 origin을 제공하는 로컬 Nginx gateway 구성과 실행 스크립트

### 4.2 제외 범위

- 채팅 요청 중 문서 인덱스 생성, 구매·판매 ETL 또는 DB 쓰기
- FastAPI나 Agent의 업무 DB·FAISS·원문 파일 직접 접근
- Django의 채팅 Graph, MCP, 업무 DB 접근
- 클라이언트가 전달한 역할 또는 허용 DB를 신뢰하는 권한 판정
- account DB를 FastAPI·Graph·MCP에 공개하는 기능
- 범용 SQL 실행, DML/DDL 실행 및 허용 View 밖의 조회
- 실제 원격 MCP URL transport, 완성된 Redis adapter 및 readiness API
- 운영 reverse proxy/Ingress, TLS, network policy와 조직 표준 rate limit 자체의 구축
- 다중 대화 이력 저장소와 장기 대화 기억 기능

## 5. 시스템 구성 및 책임 경계

```text
Browser
  -> Same-origin Gateway
      -> Django: UI, /api/auth/*, /admin/*, account DB, server session
      -> Static server: /django-static/*
      -> FastAPI: /api/chat, /api/documents/*, /api/health
          -> Django internal session introspection
          -> Cache -> LangGraph -> MCP client
              -> Document Tool -> document DB + persistent FAISS + registered files
              -> Purchase/Sales Tool -> read-only MySQL views

Offline
  -> Document registration/ingestion -> document DB + FAISS artifacts
  -> Purchase/Sales ETL -> domain tables + read-only views
```

- Django는 계정 DB, 인증, 세션, UI와 Admin의 유일한 소유자여야 한다.
- FastAPI는 보호 API마다 Django 내부 인증 확인 API로 사용자 컨텍스트를 획득해야 한다.
- FastAPI와 Agent는 MCP 경계를 통해서만 문서 및 업무 데이터를 조회해야 한다.
- ETL과 문서 인덱싱은 온라인 요청 흐름과 분리해야 한다.

## 6. 기능 요구사항

### 6.1 인증·계정·권한

| ID | 요구사항 | 우선순위 | 검증 기준 |
|---|---|---|---|
| FR-AUTH-001 | 시스템은 사용자에게 CSRF 토큰 발급, 로그인, 로그아웃, 현재 사용자 조회 API를 제공해야 한다. | 필수 | `GET /api/auth/csrf`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`의 계약 테스트 통과 |
| FR-AUTH-002 | 로그인 성공 시 Django 서버 세션을 발급하고 세션 쿠키를 `HttpOnly`, `SameSite=Lax`, path `/`로 설정해야 한다. | 필수 | 브라우저/응답 쿠키 속성 확인 |
| FR-AUTH-003 | 로그인과 로그아웃 요청은 CSRF 검증을 통과해야 하며, 로그아웃된 세션은 재사용할 수 없어야 한다. | 필수 | CSRF 실패 `403`, 폐기 세션 재요청 `401` 확인 |
| FR-AUTH-004 | 세션은 설정된 고정 수명으로 만료되며 보호 요청이나 내부 인증 확인으로 만료가 연장되지 않아야 한다. | 필수 | 시간 제어 세션 테스트 통과 |
| FR-AUTH-005 | FastAPI는 보호 요청마다 비공개 Django introspection endpoint를 호출하고 검증된 사용자 컨텍스트만 Graph와 MCP에 전달해야 한다. | 필수 | 유효 세션은 처리, 무효 세션은 `401`, 인증 서비스 장애는 `503` |
| FR-AUTH-006 | 역할별 허용 DB는 서버의 공통 정책으로 계산해야 한다. `hr`는 문서 DB만, `finance`와 `admin`은 문서·구매·판매 DB를 사용할 수 있어야 한다. | 필수 | 역할별 허용·거부 테스트 통과 |
| FR-AUTH-007 | Tool은 실행 시점에 서버가 만든 사용자 컨텍스트와 DB 권한을 다시 검증해야 한다. | 필수 | 권한 없는 Data/Document Tool 호출이 실행 전 거부됨 |
| FR-AUTH-008 | Django Admin 접근은 애플리케이션의 `admin` 역할과 별도로 Django의 staff 권한을 요구해야 한다. | 필수 | 비-staff 계정의 Admin 접근 거부 |

### 6.2 채팅 및 질문 라우팅

| ID | 요구사항 | 우선순위 | 검증 기준 |
|---|---|---|---|
| FR-CHAT-001 | 인증된 사용자는 1자 이상의 질문과 선택적 `session_id`로 `POST /api/chat`을 호출할 수 있어야 한다. | 필수 | Pydantic 입력 검증 및 보호 API 테스트 통과 |
| FR-CHAT-002 | 시스템은 질문을 `GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH` 중 하나로 분류해야 한다. | 필수 | routing fixture와 단위 테스트 통과 |
| FR-CHAT-003 | `GENERAL`은 내부 검색 없이 답변하고, 실시간성이 필요한 일반 질문은 웹 검색 근거를 사용하거나 안전한 최신 정보 확인 안내를 반환해야 한다. | 필수 | 일반/신선도 질문 fake 테스트 통과 |
| FR-CHAT-004 | `DOCUMENT`는 Document Tool만, `DATABASE`는 필요한 구매·판매 Data Tool만 호출해야 한다. | 필수 | 호출 횟수와 route 계약 테스트 통과 |
| FR-CHAT-005 | `BOTH`는 문서와 DB 검색을 병렬 실행하고 두 근거를 평가 전까지 별도 상태로 보존해야 한다. | 필수 | 병렬 분기 및 병합 테스트 통과 |
| FR-CHAT-006 | 구매와 판매가 모두 필요한 질문은 동일 database 분기에서 각 도메인 Tool을 호출하고 결과를 합쳐야 한다. | 필수 | 양 도메인 fake 결과 병합 확인 |
| FR-CHAT-007 | 응답은 `answer`, `sources`, `tables`, `cached`, `route`, `evidence_status`, `request_id`를 공개 계약에 맞게 반환해야 한다. | 필수 | 응답 schema 검증 통과 |
| FR-CHAT-008 | 내부 오류는 계약된 HTTP status와 공개 `error_code`로 변환하고 내부 예외 상세를 노출하지 않아야 한다. | 필수 | 오류 flow 통합 테스트 통과 |

### 6.3 문서 RAG

| ID | 요구사항 | 우선순위 | 검증 기준 |
|---|---|---|---|
| FR-RAG-001 | 문서는 온라인 질의 전에 등록, 로드, 청킹, 임베딩 및 영구 FAISS 인덱싱되어야 한다. | 필수 | fixture 인덱싱 및 재로딩 테스트 통과 |
| FR-RAG-002 | 문서 검색은 활성 문서 목록을 허용 목록으로 사용하고 벡터 검색과 어휘 검색 결과를 결합해야 한다. | 필수 | 비활성 문서 제외 및 하이브리드 검색 테스트 통과 |
| FR-RAG-003 | 직접 검색 점수가 기준보다 낮으면 동의어 확장 검색을 추가 수행하되 중복 근거를 제거해야 한다. | 필수 | 낮은 점수/중복 fixture 테스트 통과 |
| FR-RAG-004 | 검색 결과는 문서 ID, 제목, 파일명, 페이지, 발췌문, 관련도 및 버전 정보를 제공하고 내부 파일 경로를 제거해야 한다. | 필수 | Source schema와 민감 필드 부재 확인 |
| FR-RAG-005 | 문서 질문에 사내 근거가 부족하면 웹 검색을 마지막 수단으로 사용할 수 있으며, 검색도 실패하면 근거 부족 안내를 반환해야 한다. | 필수 | 웹 검색 성공/실패 fake 테스트 통과 |
| FR-RAG-006 | 사용자는 출처 카드의 등록된 `document_id`로 권한이 허용된 원문을 다운로드할 수 있어야 한다. 클라이언트 파일 경로 입력은 허용하지 않는다. | 필수 | 성공 다운로드와 `403`/`404`/`502` 매핑 확인 |

### 6.4 구매·판매 Text2SQL

| ID | 요구사항 | 우선순위 | 검증 기준 |
|---|---|---|---|
| FR-SQL-001 | 시스템은 자연어 질문과 도메인 schema·용어집을 이용해 구매 또는 판매 조회 SQL을 생성해야 한다. | 필수 | 도메인 golden case 테스트 통과 |
| FR-SQL-002 | 생성 SQL은 단일 `SELECT` 또는 `WITH` 문, 도메인별 허용 View 및 최대 `LIMIT 200` 조건을 만족해야 한다. | 필수 | SQL guard 테스트 통과 |
| FR-SQL-003 | DML, DDL, 다중 statement, 주석 기반 우회 및 허용되지 않은 table/view 접근을 실행 전에 차단해야 한다. | 필수 | adversarial SQL 테스트 통과 |
| FR-SQL-004 | 실행 전 권한 있는 계정으로 `EXPLAIN`을 수행하고, 실패 시 오류 문맥을 이용한 SQL 재작성은 최대 1회만 허용해야 한다. | 필수 | EXPLAIN 실패·재작성 호출 횟수 확인 |
| FR-SQL-005 | 실제 조회는 도메인별 read-only 계정으로만 수행해야 한다. | 필수 | DB grant와 client 설정 검증 |
| FR-SQL-006 | 결과 또는 답변 가능한 schema가 없으면 `NO_RESULT`로 처리하고 Graph가 빈 근거로 평가할 수 있어야 한다. | 필수 | 무결과 flow 테스트 통과 |
| FR-SQL-007 | DB 근거는 도메인, 공개 SQL, 행, 행 수, table/view, query ID, freshness 및 source version을 가능한 범위에서 제공해야 한다. | 필수 | 공통 Tool envelope와 ChatResponse 변환 확인 |
| FR-SQL-008 | 판매 금액은 UI에서 JOD 단위를 표시해야 한다. | 필수 | 판매 금액 표·차트 렌더링 확인 |

### 6.5 근거 평가 및 답변 생성

| ID | 요구사항 | 우선순위 | 검증 기준 |
|---|---|---|---|
| FR-EVD-001 | 검색 경로의 답변은 채택된 근거 범위 안에서만 생성해야 한다. | 필수 | 근거 밖 사실을 요구하는 평가 case 확인 |
| FR-EVD-002 | 시스템은 근거를 `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT`, `CONTRADICTED`로 평가해야 한다. | 필수 | 상태별 단위 테스트 통과 |
| FR-EVD-003 | `INSUFFICIENT`이면 같은 retrieval 경로로 최대 1회 보강 조회하고, 여전히 부족하면 HTTP 200의 안전한 안내를 반환해야 한다. | 필수 | 재조회 1회와 최종 안내 확인 |
| FR-EVD-004 | `PARTIALLY_SUPPORTED`이면 확인된 근거만 사용하고 부분 실패 사유를 사용자에게 알려야 한다. | 필수 | 일부 Tool 실패 통합 테스트 통과 |
| FR-EVD-005 | `CONTRADICTED`이면 단일 사실로 확정하지 않고 담당자 확인이 필요함을 안내해야 한다. | 필수 | 충돌 fixture 테스트 통과 |
| FR-EVD-006 | 문서 출처는 문서별로 합치고 페이지·발췌문의 중복을 제거하며, DB 결과는 표와 차트 힌트로 변환해야 한다. | 필수 | 출처 병합과 table schema 테스트 통과 |

### 6.6 캐시

| ID | 요구사항 | 우선순위 | 검증 기준 |
|---|---|---|---|
| FR-CACHE-001 | 캐시는 Graph 실행 전에 조회하고 Graph가 완료된 뒤에만 저장해야 한다. | 필수 | cache flow 테스트 통과 |
| FR-CACHE-002 | cache hit는 LLM 및 모든 MCP 호출을 생략하고 저장된 답변·route·근거 상태·출처·표를 반환해야 한다. | 필수 | hit 시 외부 fake 호출 0회 확인 |
| FR-CACHE-003 | 키는 정규화 질문, 대화 문맥 해시, 사용자·세션·역할·허용 DB, 문서/DB freshness, prompt 및 model 정보를 포함해야 한다. | 필수 | 각 입력 차이에 따른 키 격리 테스트 통과 |
| FR-CACHE-004 | `GENERAL` 또는 `SUPPORTED` 결과만 저장하고 오류나 부분·부족·충돌 결과는 저장하지 않아야 한다. | 필수 | 상태별 저장 여부 테스트 통과 |
| FR-CACHE-005 | 기본 TTL은 `GENERAL`·`DATABASE`·`BOTH` 300초, `DOCUMENT` 3600초여야 한다. | 필수 | TTL 정책 단위 테스트 통과 |

### 6.7 사용자 화면

| ID | 요구사항 | 우선순위 | 검증 기준 |
|---|---|---|---|
| FR-UI-001 | Django는 로그인 화면과 인증 후 채팅 화면을 같은 origin에서 제공해야 한다. | 필수 | Django UI 및 gateway route 테스트 통과 |
| FR-UI-002 | UI는 질문과 답변, route badge, cache 여부 및 근거 상태 안내를 표시해야 한다. | 필수 | DOM 렌더링 테스트 또는 브라우저 확인 |
| FR-UI-003 | UI는 DB 결과를 표로 표시하고 생성 SQL을 펼쳐 볼 수 있게 해야 한다. | 필수 | 표·SQL 상세 렌더링 확인 |
| FR-UI-004 | 숫자값과 라벨값이 있는 30행 이하 결과는 Chart.js 차트로 표시할 수 있어야 한다. | 필수 | chartable 응답의 canvas 렌더링 확인 |
| FR-UI-005 | UI는 문서 출처의 페이지·발췌문과 웹 출처 링크를 표시하고, 허용된 문서 다운로드를 제공해야 한다. | 필수 | 문서/웹 출처별 UI 확인 |
| FR-UI-006 | 세션 만료, 네트워크 실패, API 오류 및 다운로드 실패를 사용자 친화적인 메시지로 표시해야 한다. | 필수 | 오류별 UI 동작 확인 |
| FR-UI-007 | 로그아웃이나 인증 상태 변경 시 진행 중 요청과 이전 사용자의 화면 상태를 정리해야 한다. | 필수 | 인증 상태 경쟁 조건 테스트 통과 |

### 6.8 배치·초기화·상태 확인

| ID | 요구사항 | 우선순위 | 검증 기준 |
|---|---|---|---|
| FR-OPS-001 | 문서 등록·인덱싱과 구매·판매 ETL은 명시적 CLI 배치로만 실행해야 한다. | 필수 | 채팅 경로에서 배치 호출 부재 확인 |
| FR-OPS-002 | 통합 초기화 도구는 기본 실행에서 계획만 출력하고 `--apply`가 있을 때만 DB·인덱스·ETL을 변경해야 한다. | 필수 | dry-run과 apply 분리 테스트 |
| FR-OPS-003 | 초기화 도구는 문서·구매·판매 단계 생략과 원본 workbook 경로 지정을 지원해야 한다. | 필수 | CLI option 테스트 |
| FR-OPS-004 | `GET /api/health`는 인증 없이 프로세스 liveness만 `{"status":"ok"}`로 반환해야 한다. | 필수 | health API 테스트 통과 |
| FR-OPS-005 | 로컬 gateway는 Django, FastAPI, 정적 파일 및 비공개 내부 인증 경로를 계약된 prefix에 따라 분리해야 한다. | 필수 | Nginx 설정 검사와 동일 origin 브라우저 검증 |

## 7. 비기능 요구사항

### 7.1 보안 및 개인정보

| ID | 요구사항 |
|---|---|
| NFR-SEC-001 | API key, 비밀번호, 인증 header, cookie, 질문 원문, 전체 근거 및 내부 `file_path`를 로그에 기록하거나 공개 응답에 포함해서는 안 된다. |
| NFR-SEC-002 | `DJANGO_SECRET_KEY`와 `AUTH_INTROSPECTION_KEY`는 서로 다른 32자 이상의 비밀값이어야 하며 저장소에 커밋하지 않아야 한다. |
| NFR-SEC-003 | 내부 introspection endpoint는 공개 gateway에 노출하지 않고 private network/loopback에서만 접근하게 해야 한다. 원격 구간은 TLS 또는 service mesh로 보호해야 한다. |
| NFR-SEC-004 | FastAPI는 Django secret, account DB 및 세션 테이블에 직접 접근해서는 안 된다. |
| NFR-SEC-005 | 공개 gateway는 로그인 endpoint에 조직 표준 rate limit을 적용하고 인증 정보를 access log에서 제외해야 한다. |
| NFR-SEC-006 | 클라이언트에 표시하는 HTML, URL, 다운로드 경로와 파일명은 신뢰하지 않고 escape·allowlist 검증해야 한다. |

### 7.2 성능 및 확장성

| ID | 요구사항 |
|---|---|
| NFR-PERF-001 | `BOTH`의 독립적인 문서·DB 검색은 병렬 실행해야 한다. |
| NFR-PERF-002 | 영구 FAISS 인덱스는 프로세스에서 재사용하며 질문마다 원문 재로딩이나 임시 인덱스 생성을 하지 않아야 한다. |
| NFR-PERF-003 | cache hit는 Graph, LLM 및 Tool 호출을 완전히 단락해야 한다. |
| NFR-PERF-004 | Text2SQL 결과는 최대 200행으로 제한해야 한다. |
| NFR-PERF-005 | 정량 응답시간·처리량 SLO는 운영 인프라 실측 후 별도로 확정해야 하며, 현재 문서에서는 임의 목표를 설정하지 않는다. |

### 7.3 신뢰성 및 오류 처리

| ID | 요구사항 |
|---|---|
| NFR-REL-001 | 외부 Tool 경계의 timeout, 권한, 입력, 무결과, query 및 payload 오류를 구분해야 한다. |
| NFR-REL-002 | `BOTH` 또는 양 DB 조회 중 일부가 실패해도 유효한 다른 근거가 있으면 부분 응답을 제공해야 한다. 모든 근거가 실패하면 오류를 정상 무결과로 위장하지 않아야 한다. |
| NFR-REL-003 | ETL은 재실행 가능한 UPSERT와 검증 절차를 유지해야 하며 온라인 요청과 격리되어야 한다. |
| NFR-REL-004 | 기존 계정 이관은 원본 계정 DB를 삭제하지 않고 사전 백업과 감사 절차를 전제로 해야 한다. |

### 7.4 관측성 및 운영성

| ID | 요구사항 |
|---|---|
| NFR-OBS-001 | 모든 FastAPI 응답은 `X-Request-ID`와 `Server-Timing`을 제공해야 한다. |
| NFR-OBS-002 | 채팅 응답의 `request_id`는 응답 header의 ID와 일치해야 한다. |
| NFR-OBS-003 | 요청 완료 로그는 request ID, route, 근거 상태, cache hit/miss 및 비밀값 없는 단계별 timing을 추적할 수 있어야 한다. |
| NFR-OBS-004 | `/api/health`는 liveness 의미만 가지며 외부 의존성 readiness 성공으로 해석해서는 안 된다. |

### 7.5 유지보수성 및 호환성

| ID | 요구사항 |
|---|---|
| NFR-MNT-001 | 공개 요청·응답은 Pydantic model, Graph 상태는 `GraphState`, MCP 응답은 공통 envelope로 검증해야 한다. |
| NFR-MNT-002 | I/O 경계는 비동기 계약을 유지하고 새 함수에는 Python 타입을 명시해야 한다. |
| NFR-MNT-003 | UI는 현재 구조에 맞춰 vanilla HTML/CSS/JavaScript와 Chart.js를 사용하며 별도 프론트엔드 런타임을 도입하지 않아야 한다. |
| NFR-MNT-004 | 환경 변수 계약 변경 시 `app/core/config.py`와 비밀값 없는 `.env.example`을 함께 갱신해야 한다. |
| NFR-MNT-005 | Tool/API 이름, envelope, 권한, route, cache key 또는 DB schema 변경 시 계약 문서, schema, fixture와 테스트를 동기화해야 한다. |

## 8. 공개 인터페이스 요약

| Method | Endpoint | 소유 서비스 | 인증 | 목적 |
|---|---|---|---|---|
| `GET` | `/` | Django | 선택 | 로그인 또는 채팅 UI 제공 |
| `GET` | `/api/auth/csrf` | Django | 불필요 | CSRF token 발급 |
| `POST` | `/api/auth/login` | Django | CSRF | 로그인 및 세션 발급 |
| `POST` | `/api/auth/logout` | Django | session + CSRF | 세션 폐기 |
| `GET` | `/api/auth/me` | Django | session | 현재 사용자 profile 조회 |
| `POST` | `/api/chat` | FastAPI | session | 질문 처리 및 답변 반환 |
| `GET` | `/api/documents/download?doc_id=...` | FastAPI | session + 문서 권한 | 등록 문서 다운로드 |
| `GET` | `/api/health` | FastAPI | 불필요 | 프로세스 liveness 확인 |
| `POST` | `/internal/auth/introspect` | Django 내부 | 내부 key + session | FastAPI 전용 세션 검증 |

공개 오류 코드와 Tool envelope의 상세 필드는 [HTTP·MCP 인터페이스](interface.md)를 따른다.

## 9. 데이터 요구사항

- account DB는 Django만 읽고 쓰며 Django migration으로 schema를 관리한다.
- document DB는 활성 문서 ID와 등록 경로 metadata를 관리하고 Document Tool만 접근한다.
- 원문은 `data/raw/**`, 생성 인덱스는 `data/faiss/**`에 위치하며 Git 추적 대상이 아니다.
- 구매·판매 원천 workbook은 오프라인 ETL 입력이며 런타임 채팅 경로에서 읽지 않는다.
- 구매·판매 런타임 조회는 도메인별 허용 View와 read-only 계정을 사용한다.
- 문서 및 DB 근거에는 source version과 freshness metadata를 가능한 범위에서 포함한다.
- 테스트 데이터는 비식별 소형 fixture와 결정적인 fake/mock을 사용한다.

## 10. 수용 기준 및 추적성

| 요구사항 영역 | 필수 자동 검증 | 추가 수용 검증 |
|---|---|---|
| 인증·RBAC | Django/FastAPI 인증, CSRF, 세션, 역할별 Tool 거부 테스트 | 실제 gateway에서 로그인·로그아웃·만료·Admin 접근 확인 |
| 라우팅·Graph | routing fixture, route별 호출, `BOTH` 병렬 병합, 재조회 테스트 | 대표 일반·문서·DB·복합 질문 시연 |
| 문서 RAG | fixture 인덱싱, 검색, 출처, 다운로드 계약 테스트 | 실제 문서 DB·FAISS·원문을 연결한 전체 흐름 |
| Text2SQL | SQL guard, 구매·판매 golden case, fake DB 계약 테스트 | 실제 read-only 계정·View·EXPLAIN·결과 정확성 검증 |
| 근거 평가 | 지원·부분·부족·충돌 상태 테스트 | 도메인 담당자의 답변·출처 정확성 검토 |
| 캐시 | hit 단락, 키 격리, TTL, 저장 정책 테스트 | 인덱스 재생성·ETL 후 freshness 및 무효화 확인 |
| UI | Django template/static/auth 상태 테스트 | 동일 origin 브라우저에서 표·차트·출처·다운로드 확인 |
| 운영 | 설정·import smoke, health, Nginx config test | 실제 외부 서비스 readiness 및 장애 복구 확인 |

변경 완료 시 다음 명령을 기준으로 검증한다. 외부 서비스 없이 통과한 fake/mock 테스트를
실제 MySQL, Redis, 원격 MCP 또는 운영 FAISS 통합 성공으로 해석하지 않는다.

```powershell
python -m pytest tests/unit
python -m pytest tests/integration
python -m pytest
git diff --check
git status --short
```

## 11. 제약사항 및 미구현 항목

1. 기본 MCP transport는 같은 프로세스 호출이며 `DOCUMENT_MCP_URL`, `DATA_MCP_URL` 기반
   원격 transport는 구현되지 않았다.
2. 기본 캐시는 프로세스 내 `MemoryCache`다. Redis adapter와 분산 cache invalidation은
   구현되지 않았다.
3. DB freshness bucket은 현재 운영 ETL과 연결되지 않았고 자동 cache 무효화가 없다.
4. `/api/health`는 외부 MCP, MySQL, Redis, FAISS 또는 OpenAI의 readiness를 확인하지 않는다.
5. 실제 외부 문서 DB·FAISS·구매·판매 DB를 한 번에 검증하는 자동 통합 테스트는 없다.
6. `tests/integration/test_etl_mysql_flow.py`는 placeholder이므로 ETL 실DB 성공의 근거가 아니다.
7. 문서 다운로드 경로 해석은 현재 in-process 경계이며 독립 원격 Document MCP Tool이 아니다.
8. Data Tool의 `chart_hint`는 `TableData.chart_type`에 완전히 전달되지 않아 UI가 막대 차트를
   기본값으로 사용할 수 있다.
9. 로컬 Nginx gateway 구성은 제공되지만 운영 Ingress/TLS/network policy와 로그인 rate
   limit은 배포 환경에서 별도로 구현·검증해야 한다.
10. 실시간성 query label과 기본 router의 자동 연결에는 현재 제한이 있어 표현에 따라 웹
    검색 분류 결과가 달라질 수 있다.

## 12. 추후 결정 필요 항목

| ID | 결정 항목 | 완료 조건 |
|---|---|---|
| TBD-001 | 운영 환경의 정량 응답시간, 처리량, 동시 사용자 및 가용성 SLO | 대상 인프라와 부하 시험 결과를 바탕으로 합의 |
| TBD-002 | Redis 도입, 분산 캐시 및 ETL/인덱스 기반 무효화 방식 | cache adapter와 freshness 공급 계약 및 통합 테스트 확정 |
| TBD-003 | 원격 MCP transport의 protocol, 인증, timeout 및 재시도 정책 | Document/Data MCP 배포 형태와 보안 요구 확정 |
| TBD-004 | readiness endpoint와 외부 의존성 판정 기준 | 운영 모니터링 및 배포 health check 정책 확정 |
| TBD-005 | 운영 gateway의 TLS, private network, rate limit 및 log redaction 정책 | 배포 플랫폼 담당자 검토와 실제 환경 검증 완료 |
| TBD-006 | 지원 브라우저, 접근성 수준 및 반응형 UI의 정량 기준 | 사용자·운영 환경 조사 후 수용 기준 추가 |

## 13. 요구사항 변경 관리

- 요구사항 변경은 해당 ID를 유지해 수정 이력을 추적하고, 의미가 다른 신규 요구는 새 ID를 부여한다.
- 아키텍처 책임 경계나 공개 계약을 바꾸는 요구는 구현 전에 관련 소유자 검토를 거친다.
- HTTP/MCP 계약 변경은 `docs/interface.md`, Pydantic/TypedDict, fixture와 계약 테스트에 동시에 반영한다.
- DB schema 변경은 도메인 schema 정의와 생성 절차를 사용하며 생성 DDL을 직접 편집하지 않는다.
- 비밀값, 원천 데이터, 생성 인덱스, 런타임 로그 및 로컬 환경 산출물은 변경 산출물에 포함하지 않는다.

# Backend / Integration 구현 계획

## 범위와 전제

이 문서는 backend 및 integration 담당자가 실제 팀원 MCP, MySQL, FAISS, Redis, LLM 구현과 결합하기 직전까지 완료할 mock/fake 기반 구현 계획이다.

- 실제 Document MCP, Data MCP, MySQL, FAISS, Redis, OpenAI 연결은 구현하지 않는다.
- RAG, 구매, 판매, ETL, DDL 소유 경로는 변경하지 않는다.
- 외부 경계는 Protocol, dependency injection, fake/mock, 계약 테스트로 대체한다.
- `docs/interface.md`의 Tool envelope와 아래에 기록한 합의된 source 선택, evidence, 오류, freshness 규칙을 기준으로 한다.
- 인터페이스 문서 변경이 필요하면 코드를 변경하지 않고 `BLOCKED`로 보고한다.

## 공통 수정 금지 경로

다음 경로는 모든 태스크에서 수정 금지다.

- `mcp_servers/document_tools/`
- `ingestion/`
- `mcp_servers/data_tools/purchase/`
- `mcp_servers/data_tools/sales/`
- `etl/purchase/`
- `etl/sales/`
- `database/purchase/`
- `database/sales/`
- `data/raw/`
- `data/faiss/`
- `tests/unit/test_document_mcp.py`
- `tests/unit/test_etl.py`
- `tests/unit/test_ingestion.py`
- `tests/integration/test_etl_mysql_flow.py`
- `docs/interface.md`
- `docs/ownership.md`
- `docs/architecture.md`
- `docs/test-scenarios.md`

## 의존성 순서

```text
B0 계약 확인
 ├─ B1 dependency injection 기반
 ├─ B2 MCP Port/Fake/envelope
 │   └─ B3 라우팅·도메인 결정
 │       └─ B4 evidence·BOTH 병합
 └─ B5 Fake LLM·응답 직렬화
     └─ B6 LangGraph orchestration
         └─ B7 cache-first API
             └─ B8 mock 통합 테스트
                 └─ B9 회귀·불변 조건 테스트
```

## 태스크

### B0 — 합의된 계약 기준 정리

- 상태: `READY` (코드 미착수)
- 목적: 확정된 데이터 도메인 선택, source 매핑, evidence 판정, 오류 매핑 계약을 구현 태스크의 입력으로 고정한다.
- 의존성: 없음
- 수정 허용 경로: 없음
- 수정 금지 경로: 공통 수정 금지 경로 전체
- 확정된 계약:
  - 질의에 구매/매입 또는 판매/매출 키워드가 명확하면 해당 단일 Data MCP source만 조회한다. 모호하면 purchase와 sales를 모두 조회한다.
  - 다중 source 결과는 공통 키인 상품 ID, 날짜, 거래유형 기준으로 정규화한다. 실제 View 또는 `UNION ALL` 구현은 도메인 담당 소유이며, backend는 정규화된 fake Tool 결과를 소비한다.
  - 병합 결과와 각 evidence에는 `origin` 값 `purchase` 또는 `sales`를 보존한다. 수치 또는 사실 해석이 충돌하면 결과를 하나로 합치지 않고 병렬 evidence로 유지해 LLM 합성 단계에 전달한다.
  - MCP `sources`와 `metadata`는 `source_id`, `source_type`, `title` 또는 `table_name`, `retrieved_at`, `index_version`, `freshness_bucket`, 선택적인 `confidence_score`를 제공한다.
  - `source_type=document`는 문서 식별자와 page로, `source_type=database`는 table name과 query snippet으로 `app/schemas/chat.py`의 `Source`에 분기 매핑한다.
  - expected metadata가 없으면 기본 문자열로 대체하지 않고 명시적 `null`과 `metadata_incomplete=true`를 보존한다. 이 상태는 evidence 평가의 감점 요인이다.
  - Pydantic validator로 MCP source/metadata와 `Source` 매핑을 검증하고, 필수 형식 불일치는 즉시 오류로 처리한다.
  - `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT`, `CONTRADICTED`는 source 수, relevance/confidence, 숫자·날짜 일치, freshness, 명시적 반증을 조합한 규칙으로 판정한다.
  - Tool error는 malformed input 400, 인증 오류 401/403, `DOC_NOT_FOUND` 404, `RATE_LIMIT` 429, `DB_TIMEOUT` 또는 `DB_CONNECTION_ERROR` 503, MCP 내부 예외 500으로 변환한다. 원본 code는 응답 body에 유지한다.
  - `TIMEOUT`, `RATE_LIMIT`은 재시도 가능으로, `NOT_FOUND`, `VALIDATION`은 재시도 불가로 표현한다. 재시도 가능 응답은 필요 시 `Retry-After`를 제공한다.
  - `index_version`과 `freshness_bucket`은 독립 필드다. index version은 재색인 버전이고 freshness bucket은 `realtime`, `recent`, `stale`, `outdated` 중 하나다. `stale`과 `outdated`는 `PARTIALLY_SUPPORTED` 감점 요인이다.
- 테스트 명령: 없음
- 완료 조건: 이 문서의 계약이 구현 태스크와 fake/contract test의 단일 기준으로 사용된다.
- 팀원 통합 보류 조건: 실제 View/`UNION ALL`, source 데이터 생성, index/freshness 갱신은 각 도메인 구현이 제공할 때까지 fake payload로 대체한다.

### B1 — dependency injection 기반 조성

- 상태: `NOT_STARTED`
- 목적: 실제 외부 연결 없이 FastAPI 앱에 fake MCP, fake LLM, in-memory cache를 주입할 수 있게 한다.
- 의존성: B0과 무관하게 시작 가능
- 수정 허용 경로:
  - `app/main.py`
  - `app/core/`
  - `app/logging/`
  - `tests/unit/test_api.py`
  - `tests/unit/test_logging.py`
- 수정 금지 경로: 공통 수정 금지 경로 전체
- 테스트 명령:

  ```powershell
  pytest tests/unit/test_api.py tests/unit/test_logging.py
  ```

- 완료 조건:
  - 앱 생성 시 테스트용 의존성을 주입할 수 있다.
  - import 또는 테스트 실행이 실제 Redis, MCP, LLM 연결을 시도하지 않는다.
  - health endpoint가 외부 설정과 파일 로그 쓰기 없이 테스트된다.
- 팀원 통합 보류 조건: 운영 로그 저장, Redis 연결, startup readiness는 실제 인프라 연결 단계까지 보류한다.

### B2 — MCP Port, Fake, Tool envelope 검증

- 상태: `NOT_STARTED`
- 목적: Document/Purchase/Sales MCP 호출을 Protocol과 fake adapter로 표현하고 Tool envelope를 정규화한다.
- 의존성: B1
- 수정 허용 경로:
  - `app/mcp/client.py`
  - `app/schemas/`
  - `tests/unit/test_data_mcp.py`
- 수정 금지 경로: 공통 수정 금지 경로 전체, `mcp_servers/data_tools/server.py`
- 테스트 명령:

  ```powershell
  pytest tests/unit/test_data_mcp.py
  ```

- 완료 조건:
  - fake adapter가 실제 네트워크 없이 document, purchase, sales 결과를 반환한다.
  - success, `NO_RESULT`, `QUERY_ERROR`, malformed payload가 정규화·검증된다.
  - fake Data MCP의 다중 source 결과는 `origin=purchase|sales`를 보존한다.
  - source/metadata가 `source_id`, `source_type`, `retrieved_at`, version/freshness 및 도메인별 인용 필드를 만족하는지 Pydantic validator로 검증한다.
  - 누락 metadata는 `null`과 `metadata_incomplete=true`로 보존하며, 형식 불일치는 즉시 오류가 된다.
  - MCP client가 SQL, MySQL, FAISS, 파일 시스템에 직접 접근하지 않는다.
- 팀원 통합 보류 조건: HTTP/MCP transport, 인증, timeout, retry, SDK 선택은 실제 MCP 서버 계약 후에만 구현한다.

### B3 — 라우팅 및 데이터 도메인 결정

- 상태: `NOT_STARTED`
- 목적: GENERAL, DOCUMENT, DATABASE, BOTH 라우팅과 데이터 도메인 표현을 계약대로 구현한다.
- 의존성: B0, B2
- 수정 허용 경로:
  - `app/agent/state.py`
  - `app/agent/nodes.py`
  - `tests/unit/test_agent.py`
- 수정 금지 경로: 공통 수정 금지 경로 전체
- 테스트 명령:

  ```powershell
  pytest tests/unit/test_agent.py
  ```

- 완료 조건:
  - 네 route와 purchase, sales, 모호한 질의의 기대 결과가 테스트로 고정된다.
  - 구매/매입 또는 판매/매출 키워드가 명확하면 단일 data source만 선택한다.
  - 데이터 도메인이 모호하면 purchase와 sales를 모두 선택하고, 그 결과에 각각의 `origin`을 유지한다.
  - BOTH가 document evidence와 database evidence를 모두 요구한다.
  - 애매한 데이터 질의에서 임의의 도메인을 선택하지 않는다.
- 팀원 통합 보류 조건: 실제 공통 View 또는 `UNION ALL` 쿼리는 구매·판매 담당 소유이며 backend는 이를 구현하지 않는다.

### B4 — evidence 평가와 BOTH 결과 병합

- 상태: `NOT_STARTED`
- 목적: 도메인별 evidence를 보존하며 부분 성공과 부족한 근거를 일관되게 판정한다.
- 의존성: B0, B2, B3
- 수정 허용 경로:
  - `app/agent/evidence_eval.py`
  - `app/agent/nodes.py`
  - `app/agent/state.py`
  - `tests/unit/test_agent.py`
- 수정 금지 경로: 공통 수정 금지 경로 전체
- 테스트 명령:

  ```powershell
  pytest tests/unit/test_agent.py
  ```

- 완료 조건:
  - document/database evidence가 별도 state 필드에 보존된다.
  - 한 Tool 실패 시 다른 Tool evidence가 유지되는 BOTH 테스트가 있다.
  - 검색 결과 0건 또는 relevance/confidence가 주입된 임계값 미만이면 `INSUFFICIENT`가 된다.
  - 핵심 숫자·날짜·필드가 source와 일치하고 metadata가 완전하면 `SUPPORTED`가 된다.
  - 일부 핵심 주장만 확인되거나 `freshness_bucket`이 `stale` 또는 `outdated`이거나 metadata가 불완전하면 `PARTIALLY_SUPPORTED`가 된다.
  - 명시적 반증 source 또는 동일 사실에 대한 상충 값이 존재할 때만 `CONTRADICTED`가 된다. 단순 low-confidence는 `CONTRADICTED`가 아니다.
  - 충돌하는 purchase/sales 결과는 병렬 evidence로 유지하며, 하나의 값으로 임의 병합하지 않는다.
- 팀원 통합 보류 조건: relevance/confidence의 실제 산출 방식과 운영 임계값은 MCP/RAG 담당이 제공할 때까지 테스트가 주입한 정책값으로 대체한다.

### B5 — Fake LLM 기반 답변 합성과 응답 직렬화

- 상태: `NOT_STARTED`
- 목적: 실제 OpenAI 호출 없이 검증된 evidence만 사용해 answer와 source를 `ChatResponse`로 변환한다.
- 의존성: B1, B2
- 수정 허용 경로:
  - `app/agent/llm.py`
  - `app/agent/prompts.py`
  - `app/agent/nodes.py`
  - `app/schemas/chat.py`
  - `tests/unit/test_agent.py`
  - `tests/unit/test_api.py`
- 수정 금지 경로: 공통 수정 금지 경로 전체
- 테스트 명령:

  ```powershell
  pytest tests/unit/test_agent.py tests/unit/test_api.py
  ```

- 완료 조건:
  - fake LLM이 실제 API key 없이 동작한다.
  - 검증된 evidence만 fake LLM에 전달된다.
  - `ChatResponse`에 answer, sources, cached, route, request_id가 올바르게 직렬화된다.
  - `Source`는 source id/type, title 또는 table name, retrieved time, document page 또는 database query snippet, `index_version`, `freshness_bucket`, `confidence_score`, `metadata_incomplete`, `origin`을 명시적으로 표현한다.
  - 내부 `file_path`가 answer 또는 source에 노출되지 않는다.
- 팀원 통합 보류 조건: 현재 `Source.document_id`와 협의된 document 식별자 명칭, 그리고 새 page/table/query snippet 필드의 호환성은 `app/schemas/chat.py` 변경 시 하위 호환 정책으로 결정한다. 실제 모델 선택, prompt 최적화, SDK retry/timeout은 실제 LLM 연결 단계까지 보류한다.

### B6 — LangGraph orchestration 조립

- 상태: `NOT_STARTED`
- 목적: route별 retrieval, evidence evaluation, answer synthesis를 cache 외부의 graph로 조립한다.
- 의존성: B2, B3, B4, B5
- 수정 허용 경로:
  - `app/agent/graph.py`
  - `app/agent/nodes.py`
  - `app/agent/state.py`
  - `tests/unit/test_agent.py`
- 수정 금지 경로: 공통 수정 금지 경로 전체
- 테스트 명령:

  ```powershell
  pytest tests/unit/test_agent.py
  ```

- 완료 조건:
  - GENERAL은 MCP를 호출하지 않는다.
  - DOCUMENT와 DATABASE는 해당 fake port만 호출한다.
  - BOTH fan-out/fan-in이 양쪽 evidence를 보존한다.
  - 모호한 DATABASE는 purchase와 sales fake port를 모두 호출하되, 충돌하는 결과를 병렬 evidence로 answer synthesis에 전달한다.
  - graph 내부에서 cache를 직접 읽거나 쓰지 않는다.
- 팀원 통합 보류 조건: 실제 MCP 동시성, retry, streaming은 실제 transport 결정 후에 처리한다.

### B7 — cache-first `POST /api/chat`

- 상태: `NOT_STARTED`
- 목적: cache lookup → graph invoke → cache write → response 순서의 API 흐름을 구현한다.
- 의존성: B1, B6
- 수정 허용 경로:
  - `app/api/chat.py`
  - `app/main.py`
  - `app/cache/`
  - `app/schemas/chat.py`
  - `tests/unit/test_api.py`
  - `tests/unit/test_cache.py`
  - `tests/integration/test_cache_flow.py`
- 수정 금지 경로: 공통 수정 금지 경로 전체
- 테스트 명령:

  ```powershell
  pytest tests/unit/test_api.py tests/unit/test_cache.py tests/integration/test_cache_flow.py
  ```

- 완료 조건:
  - cache hit에서 graph, fake LLM, fake MCP가 호출되지 않는다.
  - cache miss에서는 graph 완료 후 재사용 가능한 응답만 저장한다.
  - API 응답의 `cached` 값과 `route`가 state와 일치한다.
  - Tool error code가 FastAPI exception handler를 통해 400, 401/403, 404, 429, 500, 503으로 변환되고 원본 `error.code`를 응답 body에 보존한다.
  - 재시도 가능한 timeout/rate-limit 오류는 retry hint와 가능한 경우 `Retry-After`를 제공한다.
- 팀원 통합 보류 조건: Redis adapter, distributed invalidation, 실제 index/freshness 값과 실제 MCP retry timing은 실제 인프라 단계까지 보류한다.

### B8 — Mock 기반 document/data/BOTH 통합 테스트

- 상태: `NOT_STARTED`
- 목적: placeholder 통합 테스트를 FastAPI 요청부터 직렬화 응답까지의 fake 기반 흐름 테스트로 대체한다.
- 의존성: B2, B3, B4, B5, B6, B7
- 수정 허용 경로:
  - `tests/integration/test_chat_document_flow.py`
  - `tests/integration/test_chat_data_flow.py`
  - `tests/integration/test_cache_flow.py`
  - 구현에 필요한 `app/` 내 backend 허용 경로
- 수정 금지 경로: 공통 수정 금지 경로 전체
- 테스트 명령:

  ```powershell
  pytest tests/integration/test_chat_document_flow.py tests/integration/test_chat_data_flow.py tests/integration/test_cache_flow.py
  ```

- 완료 조건:
  - DOCUMENT에서 fake Document MCP 결과와 source 직렬화를 검증한다.
  - DATABASE에서 fake Purchase 또는 Sales MCP 결과를 검증한다.
  - 모호한 DATABASE에서 fake Purchase와 Sales MCP를 모두 호출하고 `origin`을 보존한다.
  - BOTH에서 부분 실패와 evidence 분리·병합을 검증한다.
  - 충돌한 purchase/sales evidence가 `CONTRADICTED`로 표시되고 병렬 source로 응답에 남는지 검증한다.
  - metadata 누락이 `metadata_incomplete=true` 및 `PARTIALLY_SUPPORTED`로 전파되는지 검증한다.
  - 모든 fake가 호출 기록을 제공하여 잘못된 외부 경로 호출을 검출한다.
- 팀원 통합 보류 조건: 실제 MCP process, MySQL, FAISS, Document DB는 이 테스트에 추가하지 않는다.

### B9 — 실패 경로와 불변 조건 회귀 테스트

- 상태: `NOT_STARTED`
- 목적: 외부 의존 없는 backend/integration 완료 기준을 테스트로 고정한다.
- 의존성: B8
- 수정 허용 경로:
  - `tests/unit/test_api.py`
  - `tests/unit/test_agent.py`
  - `tests/unit/test_cache.py`
  - `tests/unit/test_data_mcp.py`
  - `tests/integration/test_chat_document_flow.py`
  - `tests/integration/test_chat_data_flow.py`
  - `tests/integration/test_cache_flow.py`
- 수정 금지 경로: 공통 수정 금지 경로 전체
- 테스트 명령:

  ```powershell
  pytest tests/unit tests/integration
  ```

- 완료 조건:
  - invalid request, malformed Tool envelope, no result, partial BOTH failure, insufficient evidence, cache hit/miss가 회귀 테스트된다.
  - `DOC_NOT_FOUND`, `RATE_LIMIT`, `DB_TIMEOUT`, MCP 내부 예외의 HTTP status, `error.code`, retry hint가 회귀 테스트된다.
  - stale/outdated freshness, metadata 불완전, 명시적 반증 source가 evidence 등급에 미치는 영향이 회귀 테스트된다.
  - 테스트가 실제 DB, FAISS, MCP, Redis, API key, 네트워크를 사용하지 않는다.
  - 기존 contract와 acceptance 테스트를 약화하거나 삭제하지 않는다.
- 팀원 통합 보류 조건: 운영 인프라 장애, MySQL timeout, FAISS index corruption은 실제 통합 환경의 별도 테스트로 남긴다.

## 팀원 통합 handoff checklist

### RAG / Document MCP 담당

- `search_documents` transport endpoint와 인증 방식
- success/error Tool envelope 준수 여부
- `data`, `sources`, `metadata.index_version` 확정 schema
- `source_id`, `source_type`, `retrieved_at`, page, confidence score, metadata incomplete 상태의 실제 payload 위치
- `NO_RESULT`, `INTERNAL_ERROR` contract fixture
- 내부 `file_path` 비노출 확인
- 재색인 후 cache invalidation에 전달할 version 또는 event

### 구매 / 판매 담당

- `query_purchase`, `query_sales` endpoint와 Tool 이름
- 결과 row, source, metadata의 최소 필드
- `origin=purchase|sales`, `table_name`, `query_snippet`, `freshness_bucket`의 실제 payload 위치
- purchase/sales 선택 및 복수 도메인 질의 정책
- SELECT 제한, row limit, timeout, error code
- ETL 완료 후 freshness bucket 또는 cache invalidation 신호
- 실제 DB 없이 공유 가능한 contract fixture

### Backend / Integration 담당

- fake adapter contract test를 실제 adapter에도 적용
- HTTP/MCP transport timeout, retry, 오류 변환 구현
- real settings와 secret 주입 방식 확정
- health와 readiness 분리
- 실제 인프라 E2E marker 분리
- cache invalidation event 연결

## 위험 및 합의 필요 사항

| 위험 또는 모호점 | 영향 | 필요한 합의 |
|---|---|---|
| Tool envelope와 현재 `list[dict]` 타입 불일치 | MCP client와 graph 설계 불안정 | envelope를 단일 기준으로 확정 |
| `GraphState.data_domain`이 단일 값 | purchase+sales 모호 질의 표현 불가 | 복수 도메인과 origin을 보존하도록 state 확장 |
| `Source`의 현재 필드와 합의된 인용 필드 차이 | 하위 호환성 또는 직렬화 오류 | `app/schemas/chat.py`의 migration 정책 결정 |
| relevance/confidence의 운영 임계값 미수치화 | evidence 등급이 환경별로 달라질 수 있음 | 임계값을 주입 가능한 정책값으로 두고 운영값 확정 |
| cache version 제공자 미구현 | 오래된 답변 재사용 위험 | index/freshness 갱신 계약을 실제 파이프라인에 연결 |
| 파일 기반 logging | 읽기 전용 테스트 환경에서 app import 실패 | 테스트용 logging 주입 경계 |
| placeholder 통합 테스트 | 통합 전 오류를 검출하지 못함 | B8에서 fake 기반 시나리오로 교체 |

# Backend / Integration 구현 계획

## 범위와 전제

이 문서는 backend 및 integration 담당자가 실제 팀원 MCP, MySQL, FAISS, Redis, LLM 구현과 결합하기 직전까지 완료할 mock/fake 기반 구현 계획이다.

- 실제 Document MCP, Data MCP, MySQL, FAISS, Redis, OpenAI 연결은 구현하지 않는다.
- RAG, 구매, 판매, ETL, DDL 소유 경로는 변경하지 않는다.
- 외부 경계는 Protocol, dependency injection, fake/mock, 계약 테스트로 대체한다.
- `docs/interface.md`의 Tool envelope, BOTH 병합, evidence 평가 규칙을 기준으로 한다.
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

### B0 — 미확정 계약 확인

- 상태: `NOT_STARTED` / `BLOCKED`
- 목적: 구현 전에 데이터 도메인 선택, source 매핑, evidence 판정, 오류 매핑 계약을 확정한다.
- 의존성: 없음
- 수정 허용 경로: 없음
- 수정 금지 경로: 공통 수정 금지 경로 전체
- 확인 대상:
  - DATABASE/BOTH에서 purchase와 sales를 선택하거나 병합하는 규칙
  - Data MCP의 `sources`, `metadata` 최소 필드와 `app/schemas/chat.py`의 `Source` 매핑
  - `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT`, `CONTRADICTED` 판정 기준
  - Tool error code와 FastAPI HTTP 응답의 매핑
  - 문서 `index_version`, 데이터 freshness bucket 제공 방식
- 테스트 명령: 없음
- 완료 조건: 팀 합의로 위 계약이 확정되어 기존 인터페이스 문서만으로 구현 판단이 가능하다.
- 팀원 통합 보류 조건: 하나라도 미확정이면 B3과 B4를 시작하지 않는다.

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
  - MCP client가 SQL, MySQL, FAISS, 파일 시스템에 직접 접근하지 않는다.
- 팀원 통합 보류 조건: HTTP/MCP transport, 인증, timeout, retry, SDK 선택은 실제 MCP 서버 계약 후에만 구현한다.

### B3 — 라우팅 및 데이터 도메인 결정

- 상태: `NOT_STARTED` / `BLOCKED`
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
  - BOTH가 document evidence와 database evidence를 모두 요구한다.
  - 애매한 데이터 질의에서 임의의 도메인을 선택하지 않는다.
- 팀원 통합 보류 조건: purchase/sales 선택 또는 복수 도메인 질의 규칙이 확정되지 않으면 구현을 시작하지 않는다.

### B4 — evidence 평가와 BOTH 결과 병합

- 상태: `NOT_STARTED` / `BLOCKED`
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
  - evidence가 없거나 부족하면 답변 합성으로 진행하지 않는다.
- 팀원 통합 보류 조건: evidence 상태별 규칙과 재검색 여부가 확정되지 않으면 판정 로직을 추측하지 않는다.

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
  - 내부 `file_path`가 answer 또는 source에 노출되지 않는다.
- 팀원 통합 보류 조건: 실제 모델 선택, prompt 최적화, SDK retry/timeout은 실제 LLM 연결 단계까지 보류한다.

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
- 팀원 통합 보류 조건: Redis adapter, distributed invalidation, 실제 index/freshness 값은 실제 인프라 단계까지 보류한다.

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
  - BOTH에서 부분 실패와 evidence 분리·병합을 검증한다.
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
  - 테스트가 실제 DB, FAISS, MCP, Redis, API key, 네트워크를 사용하지 않는다.
  - 기존 contract와 acceptance 테스트를 약화하거나 삭제하지 않는다.
- 팀원 통합 보류 조건: 운영 인프라 장애, MySQL timeout, FAISS index corruption은 실제 통합 환경의 별도 테스트로 남긴다.

## 팀원 통합 handoff checklist

### RAG / Document MCP 담당

- `search_documents` transport endpoint와 인증 방식
- success/error Tool envelope 준수 여부
- `data`, `sources`, `metadata.index_version` 확정 schema
- `NO_RESULT`, `INTERNAL_ERROR` contract fixture
- 내부 `file_path` 비노출 확인
- 재색인 후 cache invalidation에 전달할 version 또는 event

### 구매 / 판매 담당

- `query_purchase`, `query_sales` endpoint와 Tool 이름
- 결과 row, source, metadata의 최소 필드
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
| `GraphState.data_domain`이 단일 값 | purchase+sales 복합 질의 표현 불가 | 다도메인 정책과 state 구조 결정 |
| Data source schema 미정 | `ChatResponse.sources` 직렬화 불가 | source 필드 매핑 확정 |
| evidence 기준 미정 | 근거 부족 결과를 답변에 사용할 위험 | 상태별 판정 및 재검색 정책 확정 |
| cache version 제공자 미정 | 오래된 답변 재사용 위험 | index/freshness 갱신 계약 |
| 파일 기반 logging | 읽기 전용 테스트 환경에서 app import 실패 | 테스트용 logging 주입 경계 |
| placeholder 통합 테스트 | 통합 전 오류를 검출하지 못함 | B8에서 fake 기반 시나리오로 교체 |

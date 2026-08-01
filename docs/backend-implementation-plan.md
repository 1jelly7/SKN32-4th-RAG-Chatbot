# Backend / Integration 구현 계획

## 1. 문서 목적과 기준

이 문서는 FastAPI Host, LangGraph, Answer Cache, MCP client 경계와 mock 기반 통합 테스트의 현재 상태 및 다음 작업 순서를 기록한다. 실제 동작 코드와 실행 설정을 문서 설명보다 우선하며, 상태는 `2026-08-01`의 `backend` 기준이다.

판단 우선순위는 다음과 같다.

1. 실제 구현과 테스트 및 `pytest.ini`, `requirements.txt`, `.env.example`
2. `docs/interface.md`, `docs/architecture.md`, `docs/ownership.md`, `docs/test-scenarios.md`
3. 이 계획 문서

계약 문서와 구현이 충돌하면 임의로 계약을 바꾸지 않는다. 관련 소유자와 변경 방향을 합의하고 계약 문서와 테스트를 먼저 또는 같은 변경에서 동기화한다.

## 2. 모든 에이전트의 작업 규칙

모든 에이전트는 작업을 시작하기 전에 루트 `AGENTS.md` 전체를 읽고 준수해야 한다. `AGENTS.md`와 이 문서가 충돌하면 `AGENTS.md`가 우선한다.

- 시작 전 `git status --short`로 기존 사용자 변경을 확인하고, 자신의 작업과 무관한 변경을 수정·정리·되돌리지 않는다.
- 해당 태스크의 허용 경로만 수정한다. RAG·도메인 소유 경로나 계약 문서 변경이 필요하면 소유자 협의 없이 진행하지 않는다.
- `.env.example`만 공개 설정 계약으로 사용한다. `.env`와 실제 API key·DB 비밀번호·사내 URL을 만들거나 커밋하지 않는다.
- unit/mock integration 테스트에서 OpenAI, Redis, MySQL, FAISS, 실제 MCP 또는 네트워크를 사용하지 않는다. 외부 I/O는 async 호출 계약을 유지하는 fake/mock으로 대체한다.
- FastAPI/Agent에 MySQL·FAISS·원문 파일 직접 접근을 추가하지 않는다. Data MCP는 SELECT 전용이고 ETL은 채팅 요청 경로에서 호출하지 않는다.
- `docs/interface.md`의 Tool envelope와 `BOTH`의 document/database evidence 분리를 유지한다. 한쪽 실패가 다른 쪽 결과를 지우지 않아야 한다.
- 기존 contract/acceptance 테스트를 삭제하거나 약화하지 않는다. placeholder 테스트 통과를 실제 통합 완료로 보고하지 않는다.
- 완료 전 변경 범위 테스트, 가능하면 `python -m pytest tests/unit`, `git diff --check`, `git status --short`를 실행하고 통과·실패·skip 및 미검증 사유를 보고한다.

각 에이전트의 작업 요청에는 최소한 목적, 의존성, 수정 허용 경로, 수정 금지 경로, 완료 조건, 검증 명령을 포함한다. 작업 중 계약 변경이나 새 외부 권한이 필요해지면 추정으로 확장하지 말고 `BLOCKED` 사유와 필요한 결정을 남긴다.

## 3. 범위와 소유권

Backend / Integration의 기본 수정 범위:

- `app/main.py`, `app/api/`, `app/schemas/`, `app/core/`
- `app/agent/`, `app/cache/`, `app/logging/`, `app/mcp/client.py`
- `mcp_servers/data_tools/server.py`
- backend 관련 `tests/unit/`, `tests/integration/`

소유자 협의 없이 수정하지 않는 범위:

- RAG: `mcp_servers/document_tools/`, `ingestion/`
- 도메인: `mcp_servers/data_tools/{purchase,sales}/`, `etl/{purchase,sales}/`, `database/{purchase,sales}/`
- 생성물·비밀값: `data/raw/`, `data/faiss/`, `logs/*.txt`, `.env*` (`.env.example` 제외)
- 계약: `docs/interface.md`, `docs/architecture.md`, `docs/ownership.md`, `docs/test-scenarios.md`

세부 Guardrail과 생성 절차는 루트 `AGENTS.md`를 따른다.

## 4. 현재 구현 스냅샷

| 영역 | 현재 상태 | 확인된 구현 | 남은 핵심 작업 |
|---|---|---|---|
| FastAPI | 부분 완료 | app factory, health, 정적 UI, `POST /api/chat` | 의존성 주입, readiness, 구조화 오류 매핑 |
| LangGraph | MVP 완료 | GENERAL/DOCUMENT/DATABASE/BOTH 순차 흐름, evidence 후 answer | MCP client 주입, 실패·충돌 경로 강화 |
| 라우팅 | 부분 완료 | 키워드 기반 네 route와 purchase/sales/both 선택 | C0 완료, 후속 라우팅 정책 보강 |
| Evidence | 부분 완료 | 빈 근거·DB 오류 기반 3단계 판정 | freshness/confidence/metadata/충돌 및 `CONTRADICTED` 판정 |
| LLM/응답 | 부분 완료 | API key 없는 demo 응답, source/table/chart 직렬화 | fake 주입, source 계약 전체 필드, 오류 테스트 |
| Cache | 부분 완료 | Graph 외부 MemoryCache, cache-first API, TTL | Redis adapter, 실제 version/freshness 공급, hit 시 외부 미호출 API 테스트 |
| MCP Host client | 미구현 | `data_query()` dispatch 형태만 존재 | transport, timeout, envelope 검증, fake adapter |
| MCP 서버 | 소유자 구현 진행 | Document server, `query_purchase`, `query_sales` 경계 존재 | backend는 직접 확장하지 않고 확정 transport에 연결 |
| 통합 테스트 | 미구현 | cache repository roundtrip만 실질 검증 | document/data/BOTH/API cache 흐름의 fake 기반 테스트 |

현재 `app/agent/nodes.py`는 전환 단계로 `mcp_servers.document_tools.search`, `data_tools.purchase`, `data_tools.sales`를 같은 프로세스에서 직접 호출한다. 새 기능은 이 임시 결합을 확대하지 않고 purchase/sales 계약의 `app/mcp/client.py` 주입 경계로 이동시키는 방향으로 구현한다.

현재 확정된 데이터 계약은 `purchase`와 `sales`이며 Tool 이름은 `query_purchase`, `query_sales`다. 복수 조회는 `both`로 표현한다. C0에서 backend와 계약 문서를 이 명칭으로 동기화했다.

## 5. 의존성 및 권장 순서

```text
C0 purchase/sales 명칭 동기화 [DONE]
  -> B0 현재 계약 고정 [DONE]
  -> B1 테스트 가능한 dependency injection [PARTIAL]
      -> B2 MCP Port/Fake/envelope [NOT_STARTED]
          -> B3 라우팅·도메인 타입 정합성 [PARTIAL]
          -> B4 evidence·BOTH 강화 [PARTIAL]
          -> B5 LLM·응답 계약 강화 [PARTIAL]
              -> B6 LangGraph를 MCP client 경계로 전환 [PARTIAL]
                  -> B7 cache-first API·오류 처리 완성 [PARTIAL]
                      -> B8 fake 기반 통합 테스트 [NOT_STARTED]
                          -> B9 전체 회귀·불변 조건 [NOT_STARTED]
```

## 6. 태스크별 계획

### C0 — purchase/sales 계약 명칭 동기화

- 상태: `DONE`
- 확정 계약: 데이터 도메인은 `purchase`, `sales`, 복수 조회 의미의 `both`이고 Tool은 `query_purchase`, `query_sales`다.
- 완료 내용:
  - backend의 `DataDomain`, 라우팅, MCP client, 설정과 테스트를 `purchase`/`sales`/`both`로 동기화했다.
  - `docs/interface.md`, `docs/architecture.md`, `docs/ownership.md`, `docs/test-scenarios.md`의 데이터 계약과 소유 경로를 purchase/sales로 동기화했다.
  - `mcp_servers/data_tools/purchase/`의 소유자 구현은 수정하지 않고 backend 경계에서 사용한다.
  - 기존 도메인 디렉터리는 소유자 결정 전 삭제·이동하지 않으며 backend와 계약 문서에서 참조하지 않는다.
- 수정 허용: backend 소유 `app/` 경로, 관련 backend 테스트, 위 계약 문서
- 수정 금지: `mcp_servers/data_tools/{purchase,sales}/`, `etl/`, `database/`, 실제 데이터·생성물
- 검증:

  ```powershell
  python -m pytest tests/unit/test_agent.py tests/unit/test_data_mcp.py tests/unit/test_api.py
  ```

### B0 — 현재 계약 고정

- 상태: `DONE`
- 기준: `search_documents`, `query_purchase`, `query_sales`, 공통 success/error envelope, `BOTH` 부분 성공 규칙
- 확인 사항:
  - route는 `GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH`다.
  - 데이터 도메인은 `purchase`, `sales`, 복수 조회 의미의 `both`다.
  - 캐시는 Graph 외부에서 처리한다.
  - 내부 `file_path`는 사용자 응답에 노출하지 않는다.
- 후속 계약 변경: 관련 소유자 검토와 계약 테스트 없이는 진행하지 않는다.

### B1 — 테스트 가능한 dependency injection

- 상태: `DONE`
- 구현됨: `create_app()`, MemoryCache, demo LLM, 외부 연결 없는 health endpoint
- 남은 작업:
  - app factory에 LLM/MCP/cache fake를 명시적으로 주입할 수 있게 한다.
  - import 시 `logs/app.log.txt` 쓰기가 테스트를 깨지 않도록 logging 경계를 주입하거나 설정한다.
  - 공유 자원의 startup/shutdown 수명주기 위치를 확정한다.
- 수정 허용: `app/main.py`, `app/core/`, `app/logging/`, 관련 API/logging 테스트
- 검증:

  ```powershell
  python -m pytest tests/unit/test_api.py tests/unit/test_logging.py
  ```

### B2 — MCP Port, Fake, envelope 정규화

- 상태: `DONE`
- 현재 문제: `app/mcp/client.py`의 transport 메서드와 기본 편의 함수가 `...`이며 Graph가 소유자 모듈을 직접 import한다.
- 남은 작업:
  - Document/Purchase/Sales 호출을 async Protocol 또는 주입 가능한 client로 표현한다.
  - `docs/interface.md`의 success/error envelope를 Pydantic 경계에서 검증하고 내부 evidence로 정규화한다.
  - malformed payload, `NO_RESULT`, `QUERY_ERROR`, timeout을 구분하는 결정적 fake를 만든다.
  - client는 SQL을 생성·수정하거나 MySQL·FAISS·파일 시스템에 접근하지 않는다.
- 수정 허용: `app/mcp/client.py`, `app/schemas/`, backend 소유 fake/fixture, `tests/unit/test_data_mcp.py`
- 검증:

  ```powershell
  python -m pytest tests/unit/test_data_mcp.py
  ```

### B3 — 라우팅 및 데이터 도메인 정합성

- 상태: `DONE`
- 구현됨: 네 route의 결정적 키워드 라우팅, purchase/sales/모호 질의의 복수 조회, `DataDomain`의 `both` 표현
- 남은 작업:
  - purchase/sales 키워드가 동시에 있거나 모두 없는 DATABASE 질의의 복수 도메인 정책을 회귀 테스트로 고정한다.
  - 각 도메인 evidence에 origin/domain을 보존하는 테스트를 추가한다.
- 수정 허용: `app/agent/state.py`, `app/agent/nodes.py`, `tests/unit/test_agent.py`
- 검증:

  ```powershell
  python -m pytest tests/unit/test_agent.py
  ```

### B4 — evidence 평가와 BOTH 부분 성공

- 상태: `DONE`
- 구현됨: document/database evidence 분리, 빈 근거와 DB 오류에 대한 기본 판정, 순차 BOTH 보존
- 남은 작업:
  - relevance/confidence, metadata 완전성, freshness를 주입 가능한 정책값으로 판정한다.
  - 명시적 반증 또는 동일 사실의 상충 값에만 `CONTRADICTED`를 사용한다.
  - 한 Tool 실패 시 다른 Tool 근거가 유지되고 `PARTIALLY_SUPPORTED`로 전달되는지 검증한다.
  - 단순 low-confidence와 실제 충돌을 구분한다.
- 수정 허용: `app/agent/evidence_eval.py`, `app/agent/nodes.py`, `app/agent/state.py`, `tests/unit/test_agent.py`
- 검증:

  ```powershell
  python -m pytest tests/unit/test_agent.py
  ```

### B5 — Fake LLM과 응답 직렬화 계약

- 상태: `DONE`
- 구현됨: API key 없는 demo 응답, 검증된 evidence 전달, `ChatResponse`, `Source`, `TableData`, Decimal/date JSON 변환
- 남은 작업:
  - LLM port/fake를 app factory에서 주입하고 호출 기록을 검증한다.
  - document/database source에 계약상 필요한 page/table/query metadata와 freshness/version 필드를 확정 계약에 맞춰 추가한다.
  - 내부 `file_path`, 질문 원문, 전체 근거가 응답·로그에 노출되지 않는 테스트를 추가한다.
- 수정 허용: `app/agent/llm.py`, `app/agent/prompts.py`, `app/agent/nodes.py`, `app/schemas/chat.py`, 관련 agent/API 테스트
- 검증:

  ```powershell
  python -m pytest tests/unit/test_agent.py tests/unit/test_api.py
  ```

### B6 — LangGraph orchestration의 MCP client 전환

- 상태: `DONE`
- 구현됨: StateGraph 조립, GENERAL 무검색, DOCUMENT/DATABASE 단일 검색, BOTH의 document→database 순차 수집, Graph 외부 cache
- 남은 작업:
  - retrieval node의 same-process 도메인 import를 B2의 주입된 MCP client로 교체한다.
  - DOCUMENT/DATABASE/BOTH가 허용된 client 메서드만 호출했는지 fake 호출 기록으로 검증한다.
  - 한 retrieval 실패 후에도 fan-in과 answer가 계약대로 끝나는지 검증한다.
- 수정 허용: `app/agent/graph.py`, `app/agent/nodes.py`, `app/agent/state.py`, `tests/unit/test_agent.py`
- 검증:

  ```powershell
  python -m pytest tests/unit/test_agent.py
  ```

### B7 — cache-first API와 오류 매핑

- 상태: `DONE`
- 구현됨: cache lookup → Graph → cache write 순서, MemoryCache TTL, route별 cache 정책, cached 응답 직렬화
- 남은 작업:
  - cache hit에서 Graph·LLM·MCP가 호출되지 않음을 API 수준에서 검증한다.
  - `document_index_version`, `database_freshness_bucket`, prompt/model 값을 실제 공급자에서 state로 주입한다.
  - Tool error를 계약에 맞는 HTTP status와 비밀정보 없는 body로 변환한다.
  - Redis adapter와 분산 무효화는 실제 인프라 연결 태스크로 분리한다.
- 수정 허용: `app/api/chat.py`, `app/main.py`, `app/cache/`, `app/schemas/chat.py`, 관련 API/cache 테스트
- 검증:

  ```powershell
  python -m pytest tests/unit/test_api.py tests/unit/test_cache.py tests/integration/test_cache_flow.py
  ```

### B8 — fake 기반 document/data/BOTH 통합 테스트

- 상태: `DONE`
- 완료 내용: document/data placeholder를 FastAPI → Graph → fake MCP/LLM → Pydantic 응답 흐름으로 교체했다. DOCUMENT, purchase/sales DATABASE, 모호한 `both`, BOTH 성공·부분 실패·전체 실패, cache hit의 외부 호출 비증가를 결정적으로 검증한다.
- 남은 placeholder: `tests/integration/test_etl_mysql_flow.py`는 ETL 소유 범위로 유지한다.
- 검증 범위:
  - FastAPI 요청부터 Graph, fake MCP/LLM, Pydantic 응답까지 DOCUMENT와 DATABASE 흐름을 검증한다.
  - BOTH 양쪽 성공, 한쪽 실패, 모두 실패와 source/evidence 분리를 검증한다.
  - cache miss 후 hit에서 외부 port 호출 횟수가 증가하지 않는지 검증한다.
  - 실제 MCP process, MySQL, FAISS, Redis, OpenAI를 사용하지 않는다.
- 수정 허용: `tests/integration/test_chat_document_flow.py`, `test_chat_data_flow.py`, `test_cache_flow.py`, 필요한 backend 소유 `app/` 경로
- 검증:

  ```powershell
  python -m pytest tests/integration/test_chat_document_flow.py tests/integration/test_chat_data_flow.py tests/integration/test_cache_flow.py
  ```

### B9 — 실패 경로 및 불변 조건 회귀

- 상태: `PARTIAL` (회귀 테스트는 추가했으나 로컬 `.venv`의 Python 경로가 없어 전체 실행은 보류)
- 완료 내용: invalid request의 cache/Graph 미호출, malformed envelope·NO_RESULT·timeout의 구조화된 오류, partial BOTH, insufficient/contradicted evidence, cache hit/miss 회귀를 fake 기반 테스트로 고정했다. unit의 로컬 MySQL 검증은 `RUN_LOCAL_MYSQL_TESTS=1`일 때만 접속을 시도한다.
- 의존성: B1~B8 완료
- 검증 범위:
  - invalid request, malformed envelope, no result, timeout, partial BOTH, insufficient/contradicted evidence, cache hit/miss를 고정한다.
  - 테스트가 외부 서비스·시간·로컬 DB 상태에 의존하지 않는지 확인한다.
  - 기존 테스트와 fixture를 약화하거나 삭제하지 않는다.
- 검증:

  ```powershell
  python -m pytest tests/unit
  python -m pytest tests/integration
  python -m pytest
  ```

## 7. 다음 실행 우선순위

1. C0에서 purchase/sales 계약 명칭 동기화를 완료했다.
2. B1에서 app factory의 MCP/LLM/cache/logging 주입 방식을 확정한다.
3. B2에서 실제 transport와 분리된 Port/Fake/envelope validator를 구현한다.
4. B3의 복수 도메인 라우팅 정책과 B4의 evidence 규칙을 테스트로 고정한다.
5. B6에서 Graph의 same-process import를 주입 client로 교체한다.
6. B7의 API 오류·cache version 공급을 완성한다.
7. B8 placeholder를 실제 fake 기반 통합 흐름으로 교체한 뒤 B9 전체 회귀를 실행한다.

## 8. 외부 팀 handoff 체크리스트

### RAG / Document MCP

- `search_documents` transport endpoint와 인증 방식
- success/error envelope fixture와 `metadata.index_version`
- source의 document id, title, page, score 필드 위치
- `NO_RESULT`, timeout, internal error 표현
- 내부 `file_path` 비노출 및 재인덱싱 후 cache 무효화 신호

### Purchase / Sales Data MCP

- `query_purchase`, `query_sales` endpoint와 인증 방식
- result row, source, table/query metadata, freshness 필드 위치
- SELECT 제한, row limit, timeout과 오류 code
- 모호한 복수 도메인 질의의 origin 보존 방식
- ETL 완료 후 freshness/cache invalidation 신호

### Backend / Integration

- 같은 contract test를 fake와 실제 adapter에 적용
- transport timeout/retry와 HTTP 오류 변환
- `.env.example`과 `Settings` 동기화 및 secret 주입 방식
- health/readiness 분리, 실제 인프라 E2E marker 분리
- cache version/freshness 공급자와 무효화 연결

## 9. 위험 및 확인 필요 사항

| 위험 | 현재 영향 | 해소 기준 |
|---|---|---|
| MCP client가 스켈레톤 | Graph가 소유자 모듈에 직접 결합 | B2/B6에서 주입 client로 전환 |
| envelope와 내부 `list[dict]` 불일치 | 오류·metadata 유실 가능 | 경계 validator와 contract fixture 추가 |
| 기존 도메인 디렉터리 잔존 | 소유자 결정 전 삭제·이동 금지 | backend와 계약 문서에서 참조하지 않음 |
| evidence 규칙이 단순함 | freshness·충돌을 정확히 판정하지 못함 | 정책값과 B4 회귀 테스트 추가 |
| cache version 값 미공급 | 오래된 답변 키 재사용 가능 | index/freshness 공급자를 API 진입 전에 주입 |
| logging이 app import 시 파일 handler 구성 | 읽기 전용 환경에서 테스트 실패 가능 | B1에서 테스트용 logging 경계 제공 |
| integration placeholder | 실제 API 흐름 회귀를 검출하지 못함 | B8 시나리오로 대체 |
| `.venv`의 로컬 Python 경로 의존 | 현재 환경에서 전체 검증이 막힐 수 있음 | `AGENTS.md` 절차로 가상환경 재생성 후 설치 |

## 10. Backend / Integration 완료 기준

- B1~B9의 남은 조건이 contract test로 고정돼 있다.
- cache hit에서 Graph, LLM, MCP가 호출되지 않는다.
- GENERAL, DOCUMENT, DATABASE, BOTH와 purchase/sales/복수 도메인이 독립적으로 검증된다.
- BOTH의 양쪽 evidence가 섞이거나 유실되지 않고 부분 실패가 구조화된다.
- API/Agent가 MySQL, FAISS, 문서 파일에 직접 접근하지 않는다.
- 테스트가 실제 비밀값, 네트워크, 로컬 DB와 외부 서비스 없이 결정적으로 실행된다.
- `python -m pytest` 결과와 실패/skip 사유를 보고한다.
- `git diff --check`와 `git status --short`로 생성물·비밀값·담당 범위 밖 변경이 없음을 확인한다.
- 모든 에이전트의 변경이 루트 `AGENTS.md`의 스타일, Guardrail, 소유권, 검증 기준을 충족한다.

# Backend 경량 에이전트 단계별 실행 프롬프트

## 사용 방법

아래 프롬프트는 C0, B1~B9를 순차 실행하기 위한 작업 지시서다. **각 단계는 반드시 이전 단계와 다른 새 에이전트**에게 배정한다. 한 에이전트에게 둘 이상의 단계를 맡기지 않으며, 이전 단계의 완료 보고와 diff를 검토한 뒤 다음 에이전트를 시작한다.

권장 순서:

```text
Agent 01: C0
  -> Agent 02: B1
  -> Agent 03: B2
  -> Agent 04: B3
  -> Agent 05: B4
  -> Agent 06: B5
  -> Agent 07: B6
  -> Agent 08: B7
  -> Agent 09: B8
  -> Agent 10: B9
```

경량 모델의 범위 이탈을 막기 위해 프롬프트를 축약하거나 여러 단계를 합치지 않는다. 각 에이전트의 최종 답변에는 변경 파일, 구현 내용, 실행 명령과 통과/실패/skip 수, 미검증 항목, 다음 단계의 선행조건을 포함시킨다.

## 공통 오케스트레이터 프롬프트

```text
W:\Projects\SKN\skn32_3rd_pj_rag_mcp_chatbot에서 backend/integration 계획을 순차 실행하라.

필수 운영 규칙:
1. C0, B1, B2, B3, B4, B5, B6, B7, B8, B9를 이 순서로 진행한다.
2. 각 단계는 반드시 서로 다른 새 에이전트에게 맡긴다. 동일 에이전트를 재사용하지 않는다.
3. 한 번에 한 단계만 실행한다. 이전 에이전트의 결과와 git diff를 검토해 완료 조건을 충족한 경우에만 다음 에이전트를 시작한다.
4. 각 에이전트에게 아래 해당 단계 프롬프트를 원문 그대로 전달한다.
5. 모든 에이전트는 루트 AGENTS.md 전체와 docs/backend-implementation-plan.md의 자기 단계 내용을 먼저 읽어야 한다.
6. 사용자 변경과 다른 에이전트의 변경을 보존한다. 무관한 파일을 수정하거나 되돌리지 않는다.
7. 계약 변경, 소유 경로 수정, 실제 외부 서비스 접근이 새로 필요하면 추정하지 말고 그 단계를 BLOCKED로 보고한다.
8. 테스트 실패를 숨기거나 테스트를 약화하지 않는다. placeholder 통과를 완료 근거로 인정하지 않는다.
9. 에이전트가 커밋·push·PR을 만들지 않게 한다. 별도 사용자 승인이 있을 때만 수행한다.
10. 단계가 BLOCKED 또는 실패하면 다음 단계를 시작하지 말고 원인과 필요한 결정을 보고한다.
```

## Agent 01 — C0 purchase/sales 계약 동기화

```text
당신은 C0만 담당하는 새 경량 에이전트다. 다른 태스크를 구현하지 마라.

시작 전 반드시 다음을 순서대로 읽어라.
- AGENTS.md 전체
- docs/backend-implementation-plan.md의 1~6절과 C0
- docs/interface.md
- docs/architecture.md
- docs/ownership.md
- docs/test-scenarios.md

목표:
- 확정 계약을 purchase/sales, query_purchase/query_sales로 통일한다.
- backend와 계약 문서에서 legacy finance/query_finance/finance_db_database 사용을 제거한다.
- 복수 도메인 값 both는 유지한다.

수정 허용:
- app/agent/state.py
- app/agent/nodes.py
- app/mcp/client.py
- app/core/config.py
- app/schemas/chat.py의 도메인 표기
- tests/unit/test_agent.py
- tests/unit/test_data_mcp.py
- 필요한 backend API 테스트
- docs/interface.md
- docs/architecture.md
- docs/ownership.md
- docs/test-scenarios.md
- docs/backend-implementation-plan.md의 C0 상태와 사실 관계

수정 금지:
- mcp_servers/data_tools/purchase/
- mcp_servers/data_tools/sales/
- mcp_servers/data_tools/finance/
- etl/
- database/
- data/, logs/, .env

구현 조건:
- 이미 존재하는 mcp_servers.data_tools.purchase.query.query_purchase 경계를 사용한다.
- legacy 디렉터리를 삭제·이동하지 않는다.
- 테스트 이름, fixture, source/domain 값도 purchase로 정합화한다.
- AGENTS.md의 비밀값·타입·async·소유권 규칙을 지킨다.

검증:
python -m pytest tests/unit/test_agent.py tests/unit/test_data_mcp.py tests/unit/test_api.py
git diff --check
git status --short

완료 시 변경 파일, finance 잔존 검색 결과, 테스트 결과, B1이 시작 가능한지 보고하라.
```

## Agent 02 — B1 dependency injection

```text
당신은 B1만 담당하는 C0과 다른 새 경량 에이전트다. C0 완료 결과를 보존하고 다른 태스크를 구현하지 마라.

먼저 AGENTS.md 전체와 docs/backend-implementation-plan.md의 B1을 읽고 git status --short를 확인하라.

목표:
- create_app()에서 MCP, LLM, cache, logging의 테스트 대역을 명시적으로 주입할 수 있게 한다.
- health 테스트가 외부 연결과 파일 로그 쓰기 없이 실행되게 한다.
- 기본 앱 동작은 유지한다.

수정 허용:
- app/main.py
- app/core/
- app/logging/
- dependency injection에 꼭 필요한 backend 소유 타입
- tests/unit/test_api.py
- tests/unit/test_logging.py

수정 금지:
- MCP/RAG/ETL/database 도메인 소유 경로
- 계약 문서
- B2 이후 기능

구현 조건:
- import 시 OpenAI, Redis, MCP, MySQL 연결을 시도하지 않는다.
- 테스트에서는 logs/app.log.txt를 만들 필요가 없어야 한다.
- 전역 기본값과 테스트 주입값의 수명주기를 분리한다.

검증:
python -m pytest tests/unit/test_api.py tests/unit/test_logging.py
git diff --check
git status --short

완료 시 주입 API, 기본 동작 호환성, 테스트 결과, B2가 사용할 주입 지점을 보고하라.
```

## Agent 03 — B2 MCP Port/Fake/envelope

```text
당신은 B2만 담당하는 새로운 경량 에이전트다. C0과 B1의 결과를 전제로 작업하며 B3 이후 로직은 구현하지 마라.

먼저 AGENTS.md 전체, docs/backend-implementation-plan.md의 B2, docs/interface.md를 읽고 현재 주입 경계를 확인하라.

목표:
- Document/Purchase/Sales async MCP port와 결정적 fake를 만든다.
- success/error Tool envelope를 검증해 내부 evidence로 정규화한다.
- malformed payload, NO_RESULT, QUERY_ERROR, timeout을 구분한다.

수정 허용:
- app/mcp/client.py
- app/schemas/의 MCP 경계 model
- backend 소유 fake/fixture
- tests/unit/test_data_mcp.py
- B1 주입부의 최소 연결 변경

수정 금지:
- mcp_servers/의 도메인 구현
- app/agent의 라우팅/evidence/graph 동작
- 실제 네트워크·DB 연결

구현 조건:
- Tool은 search_documents, query_purchase, query_sales만 사용한다.
- MCP client에서 SQL을 만들거나 수정하지 않는다.
- Any payload는 Pydantic 또는 명시적 정규화 후 내부로 전달한다.
- fake는 호출 기록을 제공한다.

검증:
python -m pytest tests/unit/test_data_mcp.py
git diff --check
git status --short

완료 시 port 시그니처, envelope model, fake 사용법, 오류 종류, B3 선행조건을 보고하라.
```

## Agent 04 — B3 라우팅·도메인 타입

```text
당신은 B3만 담당하는 새로운 경량 에이전트다. 이전 단계의 MCP port를 사용하되 evidence/graph/API를 확장하지 마라.

먼저 AGENTS.md 전체와 docs/backend-implementation-plan.md의 B3을 읽어라.

목표:
- GENERAL, DOCUMENT, DATABASE, BOTH 라우팅을 유지한다.
- DataDomain이 purchase, sales, both를 타입 안전하게 표현하게 한다.
- 명확한 구매/판매 질문은 단일 도메인, 양쪽 또는 모호한 데이터 질문은 both가 되게 한다.
- 각 조회 evidence의 domain/origin을 보존한다.

수정 허용:
- app/agent/state.py
- app/agent/nodes.py의 router/domain 선택 부분
- tests/unit/test_agent.py의 라우팅·도메인 테스트

수정 금지:
- evidence 평가 규칙
- answer 합성
- graph edge
- API/cache
- 소유자 경로

검증:
python -m pytest tests/unit/test_agent.py
git diff --check
git status --short

완료 시 키워드 규칙, both 표현, 타입 무시 주석 제거 여부와 B4 선행조건을 보고하라.
```

## Agent 05 — B4 evidence와 BOTH 부분 성공

```text
당신은 B4만 담당하는 새로운 경량 에이전트다. B3까지의 라우팅 계약을 변경하지 마라.

먼저 AGENTS.md 전체, docs/backend-implementation-plan.md의 B4, docs/interface.md의 BOTH/evidence 계약을 읽어라.

목표:
- document_evidence와 database_evidence를 별도 보존한다.
- relevance/confidence, metadata 완전성, freshness를 주입 가능한 정책으로 평가한다.
- SUPPORTED, PARTIALLY_SUPPORTED, INSUFFICIENT, CONTRADICTED를 결정적으로 판정한다.
- 한 Tool 실패 시 다른 근거가 유지되게 한다.

수정 허용:
- app/agent/evidence_eval.py
- app/agent/state.py
- app/agent/nodes.py의 evidence 누적에 필요한 최소 변경
- tests/unit/test_agent.py의 evidence/BOTH 테스트

수정 금지:
- LLM prompt/응답 schema
- MCP transport
- API/cache
- 도메인 소유 경로

구현 조건:
- low confidence만으로 CONTRADICTED를 반환하지 않는다.
- 명시적 반증 또는 동일 사실의 상충 값에만 CONTRADICTED를 사용한다.
- 한쪽 실패를 성공 근거와 섞어 덮어쓰지 않는다.

검증:
python -m pytest tests/unit/test_agent.py
git diff --check
git status --short

완료 시 판정표, 정책 입력, 부분 성공 테스트, B5 선행조건을 보고하라.
```

## Agent 06 — B5 Fake LLM·응답 직렬화

```text
당신은 B5만 담당하는 새로운 경량 에이전트다. B4 evidence 판정 규칙을 변경하지 마라.

먼저 AGENTS.md 전체, docs/backend-implementation-plan.md의 B5, docs/interface.md와 app/schemas/chat.py를 읽어라.

목표:
- 주입 가능한 async LLM port/fake와 호출 기록을 제공한다.
- 검증된 evidence만 답변 합성에 전달한다.
- document/database source와 TableData를 계약에 맞게 직렬화한다.
- 내부 file_path와 비밀값이 응답·로그에 노출되지 않게 한다.

수정 허용:
- app/agent/llm.py
- app/agent/prompts.py
- app/agent/nodes.py의 answer/source/table 변환
- app/schemas/chat.py
- tests/unit/test_agent.py
- tests/unit/test_api.py

수정 금지:
- MCP transport와 라우팅
- evidence 판정 규칙
- cache 정책
- 도메인 소유 경로

검증:
python -m pytest tests/unit/test_agent.py tests/unit/test_api.py
git diff --check
git status --short

완료 시 LLM port/fake 사용법, source 필드, 비노출 테스트와 B6 선행조건을 보고하라.
```

## Agent 07 — B6 LangGraph MCP client 전환

```text
당신은 B6만 담당하는 새로운 경량 에이전트다. 이전 단계의 port와 state 계약을 재설계하지 말고 graph 연결만 완성하라.

먼저 AGENTS.md 전체와 docs/backend-implementation-plan.md의 B6을 읽어라.

목표:
- app/agent/nodes.py의 same-process mcp_servers.* 직접 import를 주입된 MCP client 호출로 교체한다.
- GENERAL은 MCP를 호출하지 않고 DOCUMENT/DATABASE/BOTH는 허용된 port만 호출하게 한다.
- BOTH의 실패·성공 결과가 evidence node로 안전하게 합류하게 한다.
- cache가 Graph 내부로 들어오지 않게 한다.

수정 허용:
- app/agent/graph.py
- app/agent/nodes.py
- app/agent/state.py의 최소 연결 타입
- B1 app factory의 최소 graph dependency 연결
- tests/unit/test_agent.py

수정 금지:
- MCP transport 세부 구현
- evidence/LLM/cache 정책 재설계
- 도메인 소유 경로

검증:
python -m pytest tests/unit/test_agent.py
git diff --check
git status --short

완료 시 route별 fake 호출 횟수, BOTH fan-in 결과, 직접 import 제거 결과와 B7 선행조건을 보고하라.
```

## Agent 08 — B7 cache-first API·오류 매핑

```text
당신은 B7만 담당하는 새로운 경량 에이전트다. Graph 내부 동작과 도메인 코드를 변경하지 마라.

먼저 AGENTS.md 전체, docs/backend-implementation-plan.md의 B7, docs/interface.md의 오류·캐시 계약을 읽어라.

목표:
- cache lookup -> graph invoke -> cache write 순서를 API 테스트로 고정한다.
- cache hit에서 Graph, LLM, MCP 호출이 모두 0회인지 검증한다.
- document index version, database freshness, prompt/model 식별자를 cache key state에 공급한다.
- Tool 오류를 계약상 HTTP status와 비밀정보 없는 body로 변환한다.

수정 허용:
- app/api/chat.py
- app/main.py
- app/cache/
- app/schemas/chat.py의 오류 응답 경계
- tests/unit/test_api.py
- tests/unit/test_cache.py
- tests/integration/test_cache_flow.py

수정 금지:
- 실제 Redis 연결 구현(별도 승인 없이는 MemoryCache 유지)
- graph/evidence/LLM 정책
- 도메인 소유 경로

검증:
python -m pytest tests/unit/test_api.py tests/unit/test_cache.py tests/integration/test_cache_flow.py
git diff --check
git status --short

완료 시 hit/miss 호출 횟수, cache key 공급값, 오류 매핑표와 B8 선행조건을 보고하라.
```

## Agent 09 — B8 fake 기반 통합 테스트

```text
당신은 B8만 담당하는 새로운 경량 에이전트다. 새 기능을 설계하지 말고 C0~B7의 흐름을 통합 검증하라.

먼저 AGENTS.md 전체, docs/backend-implementation-plan.md의 B8, docs/test-scenarios.md를 읽어라.

목표:
- placeholder document/data 통합 테스트를 실제 FastAPI -> Graph -> fake port -> 응답 흐름으로 교체한다.
- DOCUMENT, purchase DATABASE, sales DATABASE, ambiguous both, BOTH 양쪽 성공/부분 실패/모두 실패를 검증한다.
- cache miss 후 hit에서 외부 port 호출 횟수가 증가하지 않는지 검증한다.

수정 허용:
- tests/integration/test_chat_document_flow.py
- tests/integration/test_chat_data_flow.py
- tests/integration/test_cache_flow.py
- 결정적 backend fake/fixture
- 테스트를 가능하게 하는 backend 소유 app 경로의 최소 수정

수정 금지:
- tests/integration/test_etl_mysql_flow.py
- 실제 MCP, MySQL, Redis, FAISS, OpenAI, 네트워크
- contract/acceptance 테스트 약화
- 도메인 소유 경로

검증:
python -m pytest tests/integration/test_chat_document_flow.py tests/integration/test_chat_data_flow.py tests/integration/test_cache_flow.py
git diff --check
git status --short

완료 시 대체한 placeholder, 시나리오별 호출·응답 검증, B9 선행조건을 보고하라.
```

## Agent 10 — B9 전체 회귀·불변 조건

```text
당신은 B9만 담당하는 마지막 새 경량 에이전트다. 새로운 제품 기능을 추가하지 말고 회귀·불변 조건만 완성하라.

먼저 AGENTS.md 전체, docs/backend-implementation-plan.md의 B9와 완료 기준, docs/test-scenarios.md를 읽어라.

목표:
- invalid request, malformed envelope, no result, timeout, partial BOTH, insufficient/contradicted evidence, cache hit/miss 회귀를 고정한다.
- 외부 서비스·시간·로컬 DB 상태에 의존하지 않는지 감사한다.
- C0~B8 완료 조건과 AGENTS.md Guardrail을 최종 점검한다.

수정 허용:
- backend 소유 tests/unit/
- backend 소유 tests/integration/
- 회귀 실패를 고치는 데 필요한 backend 소유 app 경로의 최소 수정
- docs/backend-implementation-plan.md의 실제 상태 갱신

수정 금지:
- 기존 테스트 삭제·약화
- 실제 인프라 연결
- RAG/도메인 소유 코드
- 범위 밖 리팩터링

검증:
python -m pytest tests/unit
python -m pytest tests/integration
python -m pytest
git diff --check
git status --short

전체 의존성 문제로 명령을 실행하지 못하면 실패를 숨기지 말고 정확한 수집 오류와 필요한 환경 조치를 보고하라. 완료 시 전체 통과/실패/skip 수, 남은 placeholder, 외부 의존성, 최종 미완료 항목을 보고하라.
```

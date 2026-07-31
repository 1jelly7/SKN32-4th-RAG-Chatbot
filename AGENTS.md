# AGENTS.md

## 1. 프로젝트와 담당 범위

이 저장소는 FastAPI Host가 LangGraph, Answer Cache, MCP Client를 통해 문서 RAG와 업무 데이터 조회를 오케스트레이션하는 구조다.

현재 작업자는 backend 및 integration 담당자다. 이번 단계의 목표는 실제 외부 팀원 산출물을 연결하기 직전까지의 통합 기반을 구현하는 것이다.

담당 범위:

- FastAPI 진입점, API, Pydantic schema
- Agent state, routing, graph 조립, evidence evaluation, LLM port
- Cache 정책·repository port·service
- MCP client port, 공통 Data MCP Tool 등록 경계
- 공통 logging, 설정, dependency injection
- 계약 테스트와 fake/mock 기반 통합 테스트

이번 단계에서는 다음을 구현하거나 실제로 연결하지 않는다.

- 실제 Document MCP / Data MCP 서버
- 실제 MySQL, Redis, FAISS, OpenAI
- 문서 ingestion, embedding, FAISS index 생성
- 구매·판매 ETL, DDL, View, Text2SQL
- 실제 API key 또는 외부 인프라

## 2. 수정 가능·금지 경로

### 수정 가능

- `app/main.py`
- `app/api/`
- `app/schemas/`
- `app/core/`
- `app/agent/`
- `app/cache/`
- `app/logging/`
- `app/mcp/client.py`
- `mcp_servers/data_tools/server.py`
- backend/integration 범위의 테스트:
  - `tests/unit/test_api.py`
  - `tests/unit/test_agent.py`
  - `tests/unit/test_cache.py`
  - `tests/unit/test_data_mcp.py`
  - `tests/unit/test_logging.py`
  - `tests/integration/test_chat_document_flow.py`
  - `tests/integration/test_chat_data_flow.py`
  - `tests/integration/test_cache_flow.py`

### 수정 금지

- `mcp_servers/document_tools/`
- `ingestion/`
- `mcp_servers/data_tools/purchase/`
- `mcp_servers/data_tools/sales/`
- `etl/purchase/`
- `etl/sales/`
- `database/purchase/`
- `database/sales/`
- `data/raw/`, `data/faiss/`
- 팀원 소유 테스트:
  - `tests/unit/test_document_mcp.py`
  - `tests/unit/test_etl.py`
  - `tests/unit/test_ingestion.py`
  - `tests/integration/test_etl_mysql_flow.py`

`docs/interface.md`, `docs/ownership.md`, `docs/architecture.md`, `docs/test-scenarios.md`의 계약 변경이 필요하면 코드를 먼저 수정하지 말고 `BLOCKED`로 보고한다.

## 3. 반드시 읽을 문서

구현 또는 계약 테스트 작성 전 아래 문서를 읽는다.

1. `README.md`
2. `docs/architecture.md`
3. `docs/interface.md`
4. `docs/ownership.md`
5. `docs/test-scenarios.md`
6. `pytest.ini`
7. `.env.example`

특히 `docs/interface.md`의 Tool 응답 envelope, BOTH 병합, evidence evaluation, cache 무효화 규칙을 따른다.

## 4. 실행 환경과 설치 명령

Python 가상환경을 사용한다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

환경 변수 파일은 필요할 때만 `.env.example`을 참고해 로컬 `.env`로 준비한다.

```powershell
Copy-Item .env.example .env
```

단, 이번 단계의 unit/integration 테스트에는 실제 API key, DB 비밀번호, 외부 URL을 넣지 않는다. 테스트는 fake 설정값 또는 dependency injection을 사용한다.

## 5. 테스트 명령

기본 테스트 명령은 다음과 같다.

```powershell
pytest
pytest tests/unit
pytest tests/integration
pytest tests/unit/test_api.py
pytest tests/unit/test_agent.py
pytest tests/unit/test_cache.py
```

테스트는 네트워크·DB·FAISS·실제 MCP에 연결하지 않아야 한다.

읽기 전용 환경에서 pytest capture 또는 파일 로깅이 막히면 다음처럼 실행할 수 있다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest -p no:cacheprovider -s -q
```

테스트 결과 보고에는 실행 명령, 통과/실패 수, 실패 원인을 포함한다.

## 6. 코드 규칙과 타입 힌트 규칙

- Python 함수와 메서드에는 매개변수·반환 타입을 명시한다.
- 외부 경계는 `Protocol`, Pydantic model, `TypedDict` 중 적절한 타입으로 표현한다.
- `Any`는 MCP/외부 payload 경계에서만 최소한으로 사용하고, 내부로 전달하기 전에 정규화한다.
- 비동기 I/O 경계는 `async def`로 두되, fake 구현도 동일한 호출 계약을 유지한다.
- API 요청/응답은 `app/schemas/`의 Pydantic model로 검증한다.
- Agent는 MySQL, FAISS, 파일 시스템에 직접 접근하지 않는다.
- MCP Client는 SQL을 만들거나 수정하지 않고 Tool 호출·timeout·응답 검증만 담당한다.
- cache read/write는 `app/cache/service.py`를 통한 Graph 외부 경계에 둔다.
- 비밀값, 질문 원문, 전체 근거 본문, DB 인증정보를 로그에 남기지 않는다.
- `...` 스켈레톤을 구현할 때는 명시적 fake/port인지 실제 구현 예정 코드인지 테스트로 구분한다.

## 7. MCP 경계 및 읽기/쓰기 권한 규칙

Host와 외부 시스템의 경계는 다음과 같다.

```text
FastAPI / Agent
  -> Cache service
  -> MCP client port
  -> Document MCP / Data MCP port
```

규칙:

- `app/`은 문서 파일, FAISS, MySQL에 직접 연결하지 않는다.
- 문서 검색은 `search_documents` Tool 계약을 통해서만 수행한다.
- 데이터 조회는 `query_purchase`, `query_sales` Tool 계약을 통해서만 수행한다.
- Data MCP는 SELECT 전용이다. INSERT, UPDATE, DELETE, DDL은 금지한다.
- ETL은 챗봇 API 또는 Agent에서 호출하지 않는다.
- Document MCP는 원문 파일을 수정하지 않는다.
- 이번 단계에는 실제 MCP transport 대신 `Protocol`과 fake/mock adapter를 사용한다.
- Tool 성공/실패 응답은 `docs/interface.md`의 공통 envelope를 유지한다.
- `BOTH`는 document evidence와 database evidence를 별도로 보존하며, 한쪽 실패 시 부분 응답 계약을 깨지 않는다.

## 8. 테스트 불변 조건

다음 조건은 항상 유지한다.

- 기존 contract 및 acceptance 테스트를 약화하거나 삭제하지 않는다.
- 팀원 소유 모듈을 구현하거나 리팩터링하지 않는다.
- 실제 DB, FAISS, 외부 MCP, API key를 unit test에서 사용하지 않는다.
- 외부 통합은 dependency injection 및 fake/mock으로 대체한다.
- 인터페이스 문서 변경이 필요하면 코드 변경 전에 `BLOCKED`로 보고한다.
- cache hit 테스트는 Graph, LLM, MCP port가 호출되지 않았음을 검증한다.
- DOCUMENT, DATABASE, GENERAL, BOTH 라우팅은 각각 독립적으로 검증한다.
- BOTH 테스트는 두 evidence 채널이 섞이거나 한쪽 결과가 유실되지 않음을 검증한다.
- fake MCP 응답도 실제 Tool envelope와 동일한 success/error 구조를 사용한다.
- 테스트 fixture는 결정적이어야 하며 시간, 네트워크, 로컬 DB 상태에 의존하지 않는다.

## 9. Git/커밋 규칙

- `main`에는 직접 push하지 않는다.
- backend/integration 작업은 backend 계열 기능 브랜치에서 수행하고, 최종 병합은 `develop`을 거친다.
- 한 커밋은 하나의 목적만 가진다.
- 커밋 전 관련 unit test와 mock 기반 integration test를 실행한다.
- 팀원 소유 경로가 변경된 경우 커밋하지 말고 소유자와 조율한다.
- Tool 이름, 응답 형식, cache key, BOTH 병합, source 형식 변경은 독립 커밋으로 분리하고 관련 담당자의 검토를 요청한다.
- 비밀값, `.env`, 실제 데이터, FAISS 산출물, 로그 파일을 커밋하지 않는다.

## 10. 완료 보고 형식

작업 완료 또는 중단 시 아래 형식으로 보고한다.

```md
## 결과

- 상태: DONE | BLOCKED
- 구현 범위:
  - ...
- 변경 파일:
  - ...
- 추가/변경한 계약 테스트:
  - ...
- 실행한 테스트:
  - `<command>` — 결과
- 외부 의존성:
  - fake/mock으로 대체한 대상
  - 실제 통합 시 필요한 담당 팀원 산출물
- 계약 확인 사항:
  - 확정된 내용
  - 아직 미확정인 내용
- BLOCKED 사유:
  - 없으면 `없음`
```

`BLOCKED`일 때는 필요한 문서 변경 또는 외부 팀원 결정 사항을 구체적으로 적고, 추정으로 인터페이스를 변경하지 않는다.

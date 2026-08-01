# AGENTS.md

## 1. 프로젝트 개요

사내 문서 RAG와 구매·판매 업무 데이터 Text2SQL을 하나의 채팅 API로 제공하는 MCP 기반 챗봇이다. FastAPI가 LangGraph, 캐시, Document/Data MCP를 조율하며 정적 HTML/CSS/JavaScript UI를 함께 제공한다.
런타임은 Python이며 의존성은 `pip`와 `requirements.txt`로 관리한다. 주요 기술은 FastAPI, Pydantic, LangGraph, OpenAI SDK, MCP, FAISS, MySQL, Redis, pytest이고 Node.js/TypeScript/package manager는 사용하지 않는다.

## 2. 실행 및 테스트 명령

Python 버전은 저장소에 고정돼 있지 않다. 기존 `.venv`는 로컬 경로에 종속될 수 있으므로 실행되지 않으면 삭제 후가 아니라 새 가상환경을 만들어 사용한다. lockfile은 없으며 `requirements.txt`가 유일한 Python 의존성 목록이다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

개발 서버:

```powershell
python -m uvicorn app.main:app --reload
```

테스트:

```powershell
python -m pytest
python -m pytest tests/unit
python -m pytest tests/integration
python -m pytest tests/unit/test_etl.py
```

`pytest.ini`는 `tests/`, `test_*.py`, `unit`/`integration` marker와 async auto mode를 정의한다. 현재 `tests/integration/test_chat_document_flow.py`, `test_chat_data_flow.py`, `test_etl_mysql_flow.py`는 placeholder이므로 통과해도 실제 외부 통합 완료를 뜻하지 않는다. 린트·포맷·타입 검사·빌드 도구 설정과 CI 설정은 현재 없으므로 임의의 명령을 추가하지 않는다.

`app/core/config.py`의 `Settings`가 환경 변수의 실행 기준이며 `.env.example`이 비밀값 없는 변수 템플릿이다. 로컬에서는 이를 `.env`로 복사한 뒤 `OPENAI_*`, `REDIS_URL`, `MYSQL_READ_*`, `MYSQL_WRITE_*`, `MYSQL_DATABASE`, `DOCUMENT_MCP_URL`, `DATA_MCP_URL`, `FAISS_PATH`, `DOCUMENT_DB_*`를 팀이 제공한 값으로 채운다. 단위 테스트는 가능한 한 API key, 네트워크, MySQL, Redis, FAISS 없이 실행한다.

## 3. 코드 스타일 및 규칙

- Python 파일·모듈·변수·함수는 `snake_case`, 클래스·Pydantic model·`TypedDict`는 `PascalCase`, 상수는 `UPPER_SNAKE_CASE`를 쓴다. 예: `make_cache_key`, `GraphState`, `INDEX_FILENAME`.
- 새 Python 함수와 메서드는 매개변수와 반환 타입을 명시한다. `list[str]`, `dict[str, Any]`, `str | None` 같은 내장 generic/union 문법을 쓰고, 경계 타입은 Pydantic model, `TypedDict`, `Protocol`, `Literal`로 표현한다. `Any`는 MCP payload·JSON 표 데이터 같은 외부 경계에서만 최소화한다.
- import는 `from __future__ import annotations`(필요 시), 표준 라이브러리, 제3자 패키지, 프로젝트 모듈 순으로 빈 줄을 두어 구분한다. 절대 import(`from app...`, `from ingestion...`)를 사용하며 alias 설정은 없다.
- I/O 경계(FastAPI handler, LLM/MCP 호출, 문서 검색)는 `async def` 계약을 유지하고, 순수 변환·검증·캐시 저장소는 동기 함수로 둔다. 예외는 입력/파일 문제를 `ValueError`·`FileNotFoundError`로 명확히 발생시키고 외부 호출 경계에서는 `raise ... from exc` 또는 비밀정보 없는 `HTTPException`으로 변환한다.
- API 요청·응답은 `app/schemas/`의 Pydantic model로 검증하고, 그래프 상태는 `app/agent/state.py`의 `GraphState`를 사용한다. 캐시는 그래프 밖의 `app/cache/service.py`에서만 읽고 쓴다.
- FastAPI/Agent는 MySQL, FAISS, 원문 파일에 직접 접근하지 않는다. 현재 `app/agent/nodes.py`는 전환 단계로 MCP Tool과 같은 async 시그니처의 `mcp_servers.*` 함수를 같은 프로세스에서 호출한다. 이 경계를 우회하는 새 직접 접근을 추가하지 말고 `docs/interface.md`의 envelope와 `BOTH`의 document/database evidence 분리를 유지한다.
- Data MCP 조회는 SELECT 전용이며 ETL은 API/Agent 요청 경로에서 호출하지 않는다. 질문 원문, 전체 근거, API key, DB 비밀번호, 내부 `file_path`를 로그나 사용자 응답에 남기지 않는다.
- 웹 UI는 `app/web/`의 vanilla HTML/CSS/JavaScript다. React 컴포넌트, TypeScript, 별도 상태 관리·데이터 패칭 라이브러리는 현재 패턴이 아니다. API 호출과 응답/표/차트 렌더링은 `app/web/chat.js`에 둔다.
- 테스트는 `tests/unit/test_<기능>.py`, `tests/integration/test_<흐름>.py`에 두고 `pytest` 함수와 `@pytest.mark.parametrize`/`@pytest.mark.asyncio`를 사용한다. 외부 연결은 결정적 fake/mock 또는 `tmp_path`로 대체하고, 실제 로컬 MySQL이 필요한 검증은 명시적으로 skip한다. 기존 contract/acceptance 테스트를 삭제하거나 약화하지 않는다.
- 자동 포매터는 없지만 구현 코드의 기존 형식인 4칸 들여쓰기, 한 줄 하나의 명확한 동작, 짧은 한국어 docstring/comment를 따른다. 광범위한 `except Exception`은 외부 경계의 부분 실패 처리처럼 필요한 경우에만 이유와 `# noqa: BLE001`을 함께 둔다.
- 새 코드의 주석과 docstring은 프로젝트에 참여하지 않은 개발자도 이해할 수 있도록 Python 표준 스타일로 작성한다. 구현 자체를 반복하기보다 책임, 입력·출력, 외부 경계, 중요한 분기와 제약의 이유를 간결하고 정확하게 설명한다. 변경하지 않는 기존 주석을 정리·재작성하는 일은 별도 요청 없이는 하지 않는다.
- MCP Tool 및 Tool 호출 경계에는 경량 모델이 올바른 Tool을 선택할 수 있도록 docstring을 반드시 둔다. docstring에는 Tool의 목적, 사용해야 하는 질문 또는 입력, 반환 evidence/envelope의 의미, 사용하면 안 되는 경우와 도메인·읽기 전용 같은 핵심 제약을 명시한다. API key·비밀번호·내부 `file_path` 등 비밀정보나 내부 경로는 docstring·주석에 쓰지 않는다.

## 4. 금지 구역 (Guardrails)

- `.env`, `.env.local`, `*.env.local`: 비밀값과 환경별 연결 정보다. `.env.example`을 복사해 로컬에서만 채우고 수정·커밋하지 않는다.
- `.env.example`: 추적되는 공개 설정 계약이므로 실제 key·비밀번호·사내 URL을 넣지 않는다. `app/core/config.py`의 `Settings` 필드가 추가·삭제될 때만 함께 갱신하고 통합 담당과 공유한다.
- `data/raw/**`: 실제 문서와 ETL 원천 데이터이며 Git 제외 대상이다. 테스트 데이터는 `tests/fixtures/`에 비식별 소형 fixture로 추가하고 원천 데이터는 직접 수정·커밋하지 않는다.
- `data/faiss/**`: `scripts/ingest_documents.py` 또는 `scripts/rebuild_faiss_index.py`가 만드는 `index.faiss`/`metadata.json` 산출물이다. 손으로 편집·커밋하지 말고 원천·인덱싱 코드를 바꾼 뒤 스크립트로 재생성한다.
- `logs/*.txt`, `logs/*.log.txt`: 런타임 생성 로그다. 편집·커밋하지 말고 로그 형식 변경은 `app/logging/` 또는 해당 ETL logger에서 수행한다.
- `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `dist/`, `build/`, coverage 산출물: 로컬 환경·캐시·빌드 결과다. 소스처럼 수정하지 말고 필요하면 도구로 재생성한다.
- `database/sales/ddl.sql`: `python -m etl.sales.ddl` 출력으로 재생성되는 DDL이다. 직접 편집하지 말고 `etl/sales/schema.py`를 변경한 뒤 생성 명령으로 갱신하고 diff를 검토한다.
- `requirements.txt`: lockfile이 없으므로 임의 정리·버전 변경은 재현성을 직접 바꾼다. 새 직접 import나 호환성 수정이 필요한 경우에만 통합 담당과 공유하고 설치 및 전체 테스트를 다시 실행한다.
- `mcp_servers/document_tools/`, `ingestion/`는 RAG 소유이고, `mcp_servers/data_tools/{purchase,sales}/`, `etl/{purchase,sales}/`, `database/{purchase,sales}/`는 도메인 소유다. legacy `finance/` 경로도 소유자 결정 없이 수정·삭제·이동하지 않는다. 담당 범위 밖에서는 소유자와 계약·생성 절차를 먼저 합의한다.
- `docs/interface.md`, `docs/architecture.md`, `docs/ownership.md`, `docs/test-scenarios.md`는 Tool/API/소유권 계약이다. 구현과 충돌해 변경이 필요하면 추정으로 코드를 선행 수정하지 말고 관련 소유자 검토 후 문서와 계약 테스트를 함께 갱신한다.
- 생성된 API client나 schema client, 배포 설정, CI workflow는 현재 저장소에 없다. 존재하지 않는 산출물이나 설정을 추측해 만들지 않는다.

## 5. 완료 기준

- [ ] 변경 파일이 담당 범위 안에 있고, `git diff --check`와 `git status --short`로 비밀값·생성물·금지 구역 변경이 없는지 확인했다.
- [ ] 변경 범위의 단위 테스트를 실행했고, 가능하면 `python -m pytest tests/unit`을 통과했다.
- [ ] API/그래프/캐시/MCP 경계를 변경했다면 관련 mock 기반 통합 테스트를 실행하고 placeholder 통과를 실제 통합 성공으로 보고하지 않았다.
- [ ] 전체 의존성이 준비된 환경에서는 `python -m pytest`를 실행해 통과 수, 실패/skip 수와 원인을 보고했다.
- [ ] 린트·타입 검사·빌드는 현재 검증된 프로젝트 명령이 없음을 확인했으며, 임의 도구 결과를 완료 기준으로 대체하지 않았다.
- [ ] Tool 이름·응답 envelope·source 형식·`BOTH` 병합·cache key/무효화·환경 변수·DB schema가 바뀌었다면 관련 문서, Pydantic/TypedDict 계약, fixture와 테스트를 함께 동기화했다.
- [ ] 새 코드는 기존 async 경계, 타입 표현, import 순서, 오류·비밀정보 처리 및 소유권 규칙과 일치한다.

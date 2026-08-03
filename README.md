# 사내 지식 RAG·Text2SQL MCP 챗봇 구현 명세서

> **목적**: 이 문서는 프로젝트 구조, 책임 경계, 실행 흐름, 구현 우선순위 및 테스트 기준을 이해하고 작업을 시작할 수 있도록 작성한 구현 기준 문서다.

## 1. 프로젝트 목표

사용자가 웹 채팅 화면에서 질문하면 시스템은 질문의 성격을 판별한다. 사내 문서 근거가 필요하면 FAISS 기반 RAG를, 정형 업무 데이터가 필요하면 MySQL 기반 Text2SQL을 사용한다. 두 근거가 모두 필요할 때만 병렬 또는 순차적으로 두 경로를 수행한다.

사내 문서와 MySQL은 애플리케이션이 직접 접근하지 않는다. `Document MCP Server`는
내부 문서 DB에서 관련 파일 경로를 먼저 조회한 뒤 해당 파일을 읽고, `Data MCP Server`는
업무 DB를 조회한다. 같은 조건의 질문에 대한 답변은 Answer Cache에서 먼저 찾고, 캐시가
적중하면 OpenAI, LangGraph, MCP, FAISS, MySQL 호출을 모두 생략한다.

### 필수 기술

| 영역 | 기술 | 사용 목적 |
|---|---|---|
| Backend | Python, FastAPI | 웹 UI에 HTTP API 제공 |
| LLM | OpenAI 저비용 모델 | 라우팅 보조, Text2SQL, 최종 답변 생성 |
| Orchestration | LangGraph | 조건부 라우팅, 상태 전달, 노드 실행 제어 |
| External access | MCP | 문서 검색과 DB 조회를 표준 Tool 경계로 분리 |
| RAG | FAISS + Embedding | 사내 비정형 문서 검색 |
| DB | MySQL | 정형 업무 데이터 저장·조회 |
| Cache | Redis (개발 단계는 In-memory 가능) | 동일 질문의 모델 호출 생략 |
| Test | pytest | 기능별 단위·통합 테스트 |

## 2. 핵심 원칙

1. **Cache first**: 모든 `/api/chat` 요청은 코드 규칙으로 생성한 캐시 키를 사용해 먼저 Answer Cache를 조회한다.
2. **Explicit question routing**: 질문을 `GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH`로 분류하고, `GENERAL`은 검색 없이 답변하며 `DOCUMENT`는 문서만, `DATABASE`는 업무 DB만, `BOTH`는 두 경로를 모두 조회한다.
3. **MCP-only data access**: LangGraph/FastAPI는 FAISS와 MySQL에 직접 연결하지 않는다.
4. **Read/write separation**: Data MCP는 읽기 전용 MySQL 연결을 사용하고 ETL은 적재 전용 연결을 사용한다.
5. **Evidence-grounded answer**: 검색 또는 조회 근거가 있을 때는 그 근거 범위 안에서만 답변한다.
6. **Bootcamp scope**: 초기 구현은 단순하고 검증 가능해야 한다. 불필요한 마이크로서비스, Docker, Kubernetes는 포함하지 않는다.

## 3. 시스템 흐름

```text
사용자
  -> Static Web UI
  -> FastAPI POST /api/chat
  -> Answer Cache 조회
       -> Hit: 캐시 답변 즉시 반환
       -> Miss: LangGraph 실행
            -> Query Router
               -> GENERAL: 최종 답변 생성
               -> DOCUMENT: Document MCP -> 문서 DB 경로 조회 -> 파일 로드 -> FAISS RAG
               -> DATABASE: Data MCP -> Text2SQL -> MySQL SELECT
               -> BOTH: Document MCP + Data MCP
            -> Evidence Eval
            -> OpenAI 최종 답변 생성
            -> Answer Cache 저장
  -> Web UI에 답변·출처·캐시 여부 표시
```

### 질문 라우팅 규칙

| route | 선택 기준 | 실행 경로 |
|---|---|---|
| `GENERAL` | 사내 근거가 필요 없는 일반 개념 질문 | LLM 답변만 생성 |
| `DOCUMENT` | 정책, 규정, 가이드, 매뉴얼, 설계 문서 질문 | Document MCP 호출 |
| `DATABASE` | 수치, 현황, 집계, 기간별 실적, 고객/매출 질문 | Data MCP 호출 |
| `BOTH` | 문서 정책과 실제 수치·현황이 함께 필요한 질문 | 두 MCP 호출 후 근거 통합 |

현재 라우터는 키워드·규칙 기반으로만 동작한다. 문서·데이터 키워드가 모두 없으면
`GENERAL`, 데이터 도메인이 모호하면 purchase와 sales를 모두 조회한다. 저비용 LLM
라우터는 아직 구현하지 않았으며 도입 전 fallback·비용·오류 계약을 먼저 확정해야 한다.
`BOTH`는 document 다음 database 순서로 두 결과를 수집한다.

## 4. Evidence Eval 기준

`Evidence Eval`은 “검색 결과가 질문의 답변 근거로 쓸 수 있는가”를 판단하는 LangGraph 노드다. 사실을 새로 생성하는 노드가 아니다.

### 코드/규칙으로 판정할 항목

- 문서 DB 조회 결과에 파일 경로와 문서 식별자가 있는지
- 조회한 파일 경로와 실제 로드한 문서가 일치하는지
- 문서 수정일·인덱스 버전·DB 조회 시각의 최신성
- 중복 문서 청크 또는 중복 DB 행 제거
- 질문의 기간, 조직, 단위, 필수 필터 누락 여부

### LLM을 제한적으로 사용할 항목

- 질문과 문서 청크의 의미적 정합성
- 문서 정책과 DB 집계 조건의 정의/기간/단위 충돌
- 최종 답변 문장과 출처의 연결 여부

판정 결과는 `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT`, `CONTRADICTED`로
구조화한다. `INSUFFICIENT`이면 같은 retrieval 경로를 한 번만 보강 조회하고, 이후에도
부족하면 HTTP 422와 `EVIDENCE_INSUFFICIENT`를 반환한다. `CONTRADICTED`는 재시도하지
않고 성공 응답의 `evidence_status`와 경고 답변으로 구별한다.

## 5. 디렉토리 구조와 책임

```text
skn32_3rd_pj_rag_mcp_chatbot/
│
├── README.md                         # 프로젝트 소개·설치·실행 방법
├── requirements.txt                  # Python 의존성
├── pytest.ini                        # pytest 경로·marker 설정
├── .env.example                      # 환경변수 템플릿
├── .gitignore                        # 비밀값·데이터·FAISS 산출물 제외
│
├── docs/
│   ├── architecture.md               # 시스템 흐름과 코드 경계
│   ├── interface.md                  # MCP Tool 인터페이스 계약
│   ├── ownership.md                  # 코드 소유권과 변경 규칙
│   └── test-scenarios.md             # 테스트 시나리오와 완료 기준
│
├── app/                              # FastAPI Host 및 LangGraph 애플리케이션
│   ├── main.py                       # FastAPI 생성, router/static UI 등록
│   ├── api/
│   │   ├── chat.py                   # POST /api/chat: graph 호출 및 응답 반환
│   │   └── system.py                 # GET /api/health, 최소 관리자 API
│   ├── core/
│   │   └── config.py                 # .env 기반 설정 객체
│   ├── logging/
│   │   ├── logger.py                 # 공통 로그 기록 인터페이스
│   │   └── formatter.py              # 한 줄 1이벤트 로그 포맷
│   ├── schemas/
│   │   └── chat.py                   # ChatRequest/ChatResponse/Source Pydantic 모델
│   ├── agent/
│   │   ├── graph.py                  # LangGraph StateGraph, 조건부 edge
│   │   ├── state.py                  # 그래프 공유 상태 타입
│   │   ├── nodes.py                  # cache/router/retrieve/answer/write 노드
│   │   ├── evidence_eval.py          # 공통 근거 판정 경계
│   │   ├── prompts.py                # router/eval/answer 프롬프트
│   │   └── llm.py                    # OpenAI 호출 어댑터
│   ├── cache/
│   │   ├── key.py                    # 안전한 답변 캐시 키 생성
│   │   ├── repository.py             # Redis 또는 개발용 in-memory adapter
│   │   ├── policy.py                 # 질문 종류별 TTL·무효화 정책
│   │   └── service.py                # Graph 실행 전 조회·실행 후 저장 경계
│   ├── mcp/
│   │   └── client.py                 # Document/Data MCP Tool 호출 어댑터
│   └── web/
│       ├── index.html                # 최소 단일 채팅 화면
│       ├── chat.js                   # API 호출 및 비신뢰 응답 escape 후 출처·표 렌더링
│       └── style.css                 # 최소 UI 스타일
│
├── mcp_servers/                      # 사내 지식 접근 MCP Server들
│   ├── document_tools/               # RAG 담당
│   │   ├── server.py                 # search_documents Tool 등록·서버 시작
│   │   ├── document_db.py            # 내부 문서 DB에서 파일 경로 조회
│   │   ├── file_loader.py            # 조회된 경로의 문서 파일 로드
│   │   ├── search.py                 # 경로 조회 -> 파일 로드 -> RAG 검색
│   │   ├── rag.py                    # query embedding, top-k, rerank
│   │   ├── faiss_store.py            # FAISS index/metadata load·search
│   │   └── types.py                  # 문서 경로·청크·인덱스 타입
│   └── data_tools/
│       ├── server.py                 # 도메인 Tool 등록·공통 실행
│       ├── purchase/                 # 구매 담당: query_purchase, Text2SQL, read-only MySQL
│       └── sales/                    # 판매 담당: query_sales, Text2SQL, read-only MySQL
│
├── ingestion/                        # 문서 -> FAISS 배치 인덱싱
│   ├── loaders.py                    # PDF/TXT/Markdown 원문 로드
│   ├── chunking.py                   # 문맥 보존 청킹
│   ├── metadata.py                   # source, title, file_path, update 메타데이터
│   ├── embedding.py                  # 청크 embedding 생성
│   └── index.py                      # FAISS 및 metadata 저장·버전 갱신
│
├── etl/                              # 원천 정형 데이터 -> MySQL 적재 배치
│   ├── purchase/                     # 구매 담당: ETL, UPSERT, 실행 이력
│   └── sales/                        # 판매 담당: ETL, UPSERT, 실행 이력
│
├── database/
│   ├── purchase/                     # 구매 테이블·View DDL, 용어집
│   └── sales/                        # 판매 테이블·View DDL, 용어집
│
├── data/                             # Git 미추적 실제/산출 데이터
│   ├── raw/
│   │   ├── documents/                # 문서 DB 경로가 가리키는 파일 저장소(직접 순회 금지)
│   │   └── source_data/              # ETL 입력 CSV/Excel/JSON
│   └── faiss/                        # FAISS index, metadata, version 파일
│
├── scripts/
│   ├── ingest_documents.py           # 문서 증분 인덱싱 CLI
│   ├── rebuild_faiss_index.py        # 전체 인덱스 재구축 CLI
│   └── load_mysql_data.py            # ETL 파이프라인 CLI
│
├── logs/                             # 임시 텍스트 로그 저장소(현재 Git 미추적)
│   ├── app.log.txt                   # 통합 흐름
│   ├── rag.log.txt                   # RAG 실행
│   ├── etl_purchase.log.txt          # 구매 ETL
│   └── etl_sales.log.txt             # 판매 ETL
│
└── tests/                            # pytest 단일 테스트 루트
    ├── conftest.py                   # mock LLM/MCP/Redis 및 test DB fixture
    ├── fixtures/
    │   ├── documents/                # 비식별 소형 RAG fixture
    │   ├── source_data/              # 소형 ETL fixture
    │   └── cases/                    # routing/rag/text2sql/etl golden cases
    ├── unit/
    │   ├── test_api.py               # API 형식·입력 검증
    │   ├── test_agent.py             # router/evidence/state 노드
    │   ├── test_cache.py             # cache key/TTL/hit/miss
    │   ├── test_document_mcp.py      # 문서 DB 경로 조회·파일 로드·RAG 순서
    │   ├── test_data_mcp.py          # 구매·판매 Tool dispatch
    │   ├── test_ingestion.py         # loader/chunk/embedding/index
    │   └── test_etl.py               # extract/transform/validate/load
    └── integration/
        ├── test_chat_document_flow.py # API -> Graph -> Document MCP 흐름
        ├── test_chat_data_flow.py     # API -> Graph -> Data MCP 흐름
        ├── test_cache_flow.py         # cache hit 시 외부 호출 없음
        └── test_etl_mysql_flow.py     # ETL -> test MySQL insert/upsert 흐름
```

## 6. 모듈별 구현 지시

### `app/api/chat.py`

- 입력: `question`, 선택적 `session_id`.
- `graph.ainvoke()`에 초기 상태를 전달한다.
- 출력: `answer`, `sources`, `tables`, `cached`, `route`, `evidence_status`, `request_id`.
- 스트리밍은 MVP 완료 후 Server-Sent Events로 추가한다.

### `app/agent/graph.py`, `nodes.py`, `evidence_eval.py`

캐시 miss 상태에 대해 다음 노드를 명시적으로 구성한다.

1. `query_router`: `GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH`를 결정한다.
2. `document_retrieval`: Document MCP Tool을 호출한다.
3. `database_retrieval`: Data MCP Tool을 호출한다.
4. `evidence_eval`: 규칙 기반 검증 후 필요한 경우 LLM 의미 검증을 수행한다.
5. `answer_synthesis`: 검증된 evidence만 컨텍스트에 넣어 답변·출처를 만든다.

`BOTH`는 두 retrieval 결과를 동일 state의 `document_evidence`, `database_evidence` 또는 통합 `evidence`에 축적한 뒤 `evidence_eval`로 보낸다. 구현상 한쪽 결과를 덮어쓰지 않게 주의한다.
근거 판정 로직의 소유 경계는 `app/agent/evidence_eval.py`이며, 그래프 노드 조립 시 이
모듈을 사용한다.

### `app/cache/`

`app/cache/service.py`가 FastAPI와 LangGraph 사이의 단일 캐시 진입점이다. API 계층은
그래프 실행 전에 `lookup_cached_answer`, 실행 완료 후 `write_answer_cache`를 호출한다.
LangGraph 노드는 캐시를 직접 읽거나 쓰지 않는다.

캐시 키는 최소 아래 요소를 해시해야 한다.

```text
normalized_question + conversation context hash
+ document_index_version + database freshness bucket + prompt_version + model_id
```

개발 단계에는 in-memory cache adapter를 사용해도 되지만, 배포 환경에서는 Redis adapter로 교체한다. DB 질문 TTL은 짧게(예: 1~5분), 문서 질문은 문서 갱신 정책에 맞춰 길게(예: 1시간) 설정한다.

### `mcp_servers/document_tools/`

`search_documents(query, top_k)` Tool은 다음 순서를 지킨다.

```text
내부 문서 DB에서 관련 파일 경로 조회 -> 해당 파일 로드
-> query embedding -> FAISS 검색 -> optional rerank
-> chunk text + metadata + source 반환
```

문서 DB에서는 문서 본문을 바로 가져오지 않고 `document_id`, `title`, `file_path`,
`updated_at`만 조회한다. 반환값은 최소 `chunk_id`, `document_id`, `title`, `content`,
`score`, `updated_at`을 포함하며 내부 `file_path`는 출처 구성에 사용하되 사용자 응답에는
노출하지 않는다.

### `mcp_servers/data_tools/`

`query_purchase(question)`와 `query_sales(question)`는 각 도메인 소유 모듈에서 구현한다.
공통 서버는 두 도메인의 Tool 등록과 요청 전달만 담당한다.

```text
mcp_servers/data_tools/
├── server.py                 # 통합: Tool 등록·도메인 전달
├── purchase/                 # 구매: query_purchase, schema, text2sql, mysql
└── sales/                    # 판매: query_sales, schema, text2sql, mysql
```

```text
스키마/용어집 제공 -> SQL 생성 -> read-only MySQL 실행
-> 결과 행 수 제한 -> 결과와 실행 메타데이터 반환
```

### `ingestion/`

문서 인덱싱은 API 요청 경로에서 실행하지 않는다. `scripts/ingest_documents.py`를 통해 배치 실행한다.

```text
내부 문서 DB -> file_path 조회 -> 파일 로드 -> clean/chunk -> metadata
-> embedding -> FAISS index + metadata -> data/faiss
```

문서 변경 시 인덱스 버전을 증가시키고 cache key에서 이 버전을 사용한다. 문서 DB의 경로
또는 실제 파일이 변경되면 이전 버전 키가 재사용되지 않게 한다.

### `etl/purchase/`, `etl/sales/`

ETL은 챗봇 조회와 분리된 배치 작업이다.

```text
data/raw/source_data -> extract -> transform -> validate -> MySQL load
```

- 각 도메인은 `extract.py`, `transform.py`, `validate.py`, `load.py`, `pipeline.py`를 자체
  디렉터리에 둔다. 다른 도메인의 테이블·적재 규칙을 직접 수정하지 않는다.
- `load.py`: 단일 transaction으로 INSERT/UPSERT한다. ETL 전용 MySQL 계정을 사용한다.
- `pipeline.py`: 처리 입력/성공/실패 행 수와 오류를 해당 도메인 로그에 남긴다.

`scripts/load_mysql_data.py`는 도메인별 파이프라인 선택과 입력 검증을 완료한 뒤에만 각
디렉터리의 `pipeline.py`를 호출해야 한다. 챗봇 API나 `app/agent/`에서 ETL을 호출하지 않는다.

## 7. 환경변수와 연결 계정

`.env`에는 비밀값을 보관하고 Git에 절대 커밋하지 않는다.

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
REDIS_URL=redis://localhost:6379/0
MYSQL_READ_HOST=localhost
MYSQL_READ_USER=chatbot_reader
MYSQL_READ_PASSWORD=
MYSQL_WRITE_HOST=localhost
MYSQL_WRITE_USER=etl_writer
MYSQL_WRITE_PASSWORD=
MYSQL_DATABASE=chatbot
DOCUMENT_MCP_URL=http://localhost:8001
DATA_MCP_URL=http://localhost:8002
FAISS_PATH=data/faiss
DOCUMENT_DB_HOST=localhost
DOCUMENT_DB_USER=document_reader
DOCUMENT_DB_PASSWORD=
DOCUMENT_DB_DATABASE=documents
```

| 계정 | 접근 방식 | 사용하는 코드 |
|---|---|---|
| `document_reader` | 문서 식별자·파일 경로 읽기 | `mcp_servers/document_tools/document_db.py` |
| `chatbot_reader` | 업무 데이터 읽기 | `mcp_servers/data_tools/{purchase,sales}/mysql.py` |
| `etl_writer` | 업무 데이터 적재 | `etl/{purchase,sales}/load.py` |
| Redis 계정 | 지정 namespace의 get/set/delete | `app/cache/repository.py` |

## 8. 테스트 기준

테스트는 `tests/` 한 곳에 둔다. 단위 테스트는 OpenAI, Redis, MCP, MySQL을 fake/mock으로
대체한다. 현재 chat integration 테스트도 외부 서비스를 사용하지 않는 in-process fake
기반 계약 테스트다. 실제 MySQL 검증은 `RUN_LOCAL_MYSQL_TESTS=1`일 때 same-process
Data MCP를 주입하는 opt-in 테스트만 실행하며, ETL의 실제 MySQL 통합 테스트는 아직
placeholder다.

### 필수 단위 테스트

- 동일 질문·동일 문맥·동일 버전이면 cache key가 동일하다.
- 대화 문맥 또는 문서 버전이 달라지면 cache key가 달라진다.
- `DOCUMENT`, `DATABASE`, `GENERAL`, `BOTH` 라우팅이 기대대로 동작한다.
- 문서 검색이 문서 DB 경로 조회 → 파일 로드 → RAG 순서로 수행된다.
- ETL이 중복 제거·필수값 검증·타입 변환을 수행한다.
- Evidence Eval이 근거 부족 및 충돌 상태를 올바르게 반환한다.

### 필수 통합 테스트

- 문서 질문이 API → Graph → Document MCP 흐름으로 처리된다.
- 데이터 질문이 API → Graph → Data MCP 흐름으로 처리된다.
- cache hit 시 LLM/MCP 호출 mock이 호출되지 않는다.
- ETL이 테스트 MySQL에 insert/upsert하고 기대 데이터를 저장한다.

```bash
pytest                         # 전체 테스트
pytest tests/unit              # 빠른 단위 테스트
pytest tests/integration       # 통합 테스트
pytest tests/unit/test_etl.py  # ETL 기능만
```
## 사내규정 챗봇(RAG) 실행 방법
 
### 1. 사전 준비
`.env`에 아래 값을 채운다.
 
```
DOCUMENT_DB_HOST=127.0.0.1
DOCUMENT_DB_USER=
DOCUMENT_DB_PASSWORD=
DOCUMENT_DB_DATABASE=erp_system
FAISS_PATH=data/faiss
EMBEDDING_BACKEND=sbert
```
 
### 2. DB 생성 (최초 1회)
 
```
mysql -u root -p < database/document/schema.sql
```
 
### 3. 원천 문서 배치
사내규정 PDF(취업규칙, 법인카드 관리지침 등)를 `data/raw/documents/`에 둔다.
 
### 4. 문서 경로 등록
 
```
python scripts/register_documents.py
```
 
### 5. 인덱싱
 
```
python scripts/ingest_documents.py
```
 
문서를 추가·교체하거나 `EMBEDDING_BACKEND`를 바꾸면 다시 실행한다.
 
### 6. 실행 확인
 
```
uvicorn app.main:app --reload
```
 
`http://127.0.0.1:8000`에서 확인한다.

## 판매(Sales) 도메인 ETL 실행 방법

### 1. 사전 준비

`.env`에 아래 값을 채운다.
```env
MYSQL_WRITE_HOST=localhost
MYSQL_WRITE_USER=etl_writer
MYSQL_WRITE_PASSWORD=
MYSQL_DATABASE=sales
```

### 2. DB 생성 (최초 1회, 관리자 계정으로 실행)
```bash
mysql -u root -p < database/sales/create_sales_db.sql
```
`.env`의 `MYSQL_WRITE_USER`/`MYSQL_WRITE_PASSWORD`와 스크립트 안 계정 정보를 동일하게 맞춘다.

### 3. 테이블 생성
```bash
mysql -u etl_writer -p sales < database/sales/ddl.sql
```

### 4. 원천 데이터 배치
`ERP_Sales_Data_Full.xlsx`를 `data/raw/source_data/`에 둔다.

### 5. ETL 실행
```bash
python -m etl.sales.run_all data/raw/source_data/ERP_Sales_Data_Full.xlsx
```
실행 로그는 `logs/etl_sales.log.txt`에서 확인한다. 동일 원천으로 재실행해도 UPSERT라 행 수는 늘지 않는다(멱등성).
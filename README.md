# 사내 지식 RAG·Text2SQL MCP 챗봇 구현 명세서

> **목적**: 이 문서는 프로젝트 구조, 책임 경계, 실행 흐름, 구현 우선순위 및 테스트 기준을 이해하고 작업을 시작할 수 있도록 작성한 구현 기준 문서다.

## 1. 프로젝트 목표

사용자가 웹 채팅 화면에서 질문하면 시스템은 질문의 성격을 판별한다. 사내 문서 근거가 필요하면 FAISS 기반 RAG를, 정형 업무 데이터가 필요하면 MySQL 기반 Text2SQL을 사용한다. 두 근거가 모두 필요할 때만 병렬 또는 순차적으로 두 경로를 수행한다.

사내 문서와 MySQL은 애플리케이션이 직접 접근하지 않는다. `Document MCP Server` 및 `Data MCP Server`를 통해서만 접근한다. 같은 조건의 질문에 대한 답변은 Answer Cache에서 먼저 찾고, 캐시가 적중하면 OpenAI, LangGraph, MCP, FAISS, MySQL 호출을 모두 생략한다.

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

1. **Cache first**: 모든 `/api/chat` 요청은 먼저 Answer Cache를 조회한다.
2. **Selective retrieval**: 모든 질문에 문서와 DB를 둘 다 조회하지 않는다.
3. **MCP-only data access**: LangGraph/FastAPI는 FAISS와 MySQL에 직접 연결하지 않는다.
4. **Read/write separation**: Data MCP의 MySQL 계정은 `SELECT` 전용, ETL 계정만 `INSERT`/`UPDATE` 권한을 가진다.
5. **Evidence-grounded answer**: 검색 또는 조회 근거가 있을 때는 그 근거 범위 안에서만 답변한다.
6. **Deterministic safety first**: 권한, ACL, SQL guard, 캐시 키는 LLM이 아닌 코드 규칙으로 처리한다.
7. **Bootcamp scope**: 초기 구현은 단순하고 검증 가능해야 한다. 불필요한 마이크로서비스, Docker, Kubernetes는 포함하지 않는다.

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
               -> DOCUMENT: Document MCP -> FAISS RAG
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

초기에는 키워드·규칙 기반 라우팅을 우선 구현한다. 규칙으로 모호한 질문만 저비용 LLM 라우터를 호출한다. `BOTH` 경로는 반드시 구현하되, 첫 MVP에서는 두 결과를 순차 수집해도 된다.

## 4. Evidence Eval 기준

`Evidence Eval`은 “검색 결과가 질문의 답변 근거로 쓸 수 있는가”를 판단하는 LangGraph 노드다. 사실을 새로 생성하는 노드가 아니다.

### 코드/규칙으로 판정할 항목

- 문서 ACL 및 사용자 역할 일치 여부
- 허용된 문서 저장소·테이블·컬럼인지 여부
- SQL이 단일 `SELECT`인지, 금지 키워드가 없는지, `LIMIT`이 적용됐는지
- 문서 수정일·인덱스 버전·DB 조회 시각의 최신성
- 중복 문서 청크 또는 중복 DB 행 제거
- 질문의 기간, 조직, 단위, 필수 필터 누락 여부

### LLM을 제한적으로 사용할 항목

- 질문과 문서 청크의 의미적 정합성
- 문서 정책과 DB 집계 조건의 정의/기간/단위 충돌
- 최종 답변 문장과 출처의 연결 여부

판정 결과는 `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT`, `CONTRADICTED`처럼 구조화한다. 근거가 부족하면 최대 1회 재검색/재생성하고, 그 이후에는 근거 부족을 명시한다.

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
│   └── architecture.md               # 이 문서를 복사/유지할 설계 기준 문서
│
├── app/                              # FastAPI Host 및 LangGraph 애플리케이션
│   ├── main.py                       # FastAPI 생성, router/static UI 등록
│   ├── api/
│   │   ├── chat.py                   # POST /api/chat: graph 호출 및 응답 반환
│   │   └── system.py                 # GET /api/health, 최소 관리자 API
│   ├── core/
│   │   ├── config.py                 # .env 기반 설정 객체
│   │   ├── security.py               # 사용자·역할·부서 권한 컨텍스트
│   │   └── logging.py                # 요청·캐시·MCP·LLM 로그 형식
│   ├── schemas/
│   │   └── chat.py                   # ChatRequest/ChatResponse/Source Pydantic 모델
│   ├── agent/
│   │   ├── graph.py                  # LangGraph StateGraph, 조건부 edge
│   │   ├── state.py                  # 그래프 공유 상태 타입
│   │   ├── nodes.py                  # cache/router/retrieve/eval/answer/write 노드
│   │   ├── prompts.py                # router/eval/answer 프롬프트
│   │   └── llm.py                    # OpenAI 호출 어댑터
│   ├── cache/
│   │   ├── key.py                    # 안전한 답변 캐시 키 생성
│   │   ├── repository.py             # Redis 또는 개발용 in-memory adapter
│   │   └── policy.py                 # 질문 종류별 TTL·무효화 정책
│   ├── mcp/
│   │   └── client.py                 # Document/Data MCP Tool 호출 어댑터
│   └── web/
│       ├── index.html                # 최소 단일 채팅 화면
│       ├── chat.js                   # API 호출·응답·출처 렌더링
│       └── style.css                 # 최소 UI 스타일
│
├── mcp_servers/                      # 사내 지식 접근 MCP Server들
│   ├── document/
│   │   ├── server.py                 # search_documents Tool 등록·서버 시작
│   │   ├── search.py                 # query+권한 -> ACL -> 검색 결과 반환
│   │   ├── rag.py                    # query embedding, top-k, rerank
│   │   ├── faiss_store.py            # FAISS index/metadata load·search
│   │   └── acl.py                    # 문서 ACL 필터
│   └── data/
│       ├── server.py                 # query_business_data Tool, schema Resource 등록
│       ├── query.py                  # 자연어 -> SQL -> guard -> MySQL 조회
│       ├── text2sql.py               # LLM SQL 생성·의미 확인
│       ├── sql_guard.py              # SELECT-only, whitelist, limit, timeout 검사
│       ├── mysql.py                  # 읽기 전용 MySQL 연결·쿼리 실행
│       └── schema.py                 # 허용 스키마·용어집 Resource 제공
│
├── ingestion/                        # 문서 -> FAISS 배치 인덱싱
│   ├── loaders.py                    # PDF/TXT/Markdown 원문 로드
│   ├── chunking.py                   # 문맥 보존 청킹
│   ├── metadata.py                   # source, title, update, ACL 메타데이터
│   ├── embedding.py                  # 청크 embedding 생성
│   └── index.py                      # FAISS 및 metadata 저장·버전 갱신
│
├── etl/                              # 원천 정형 데이터 -> MySQL 적재 배치
│   ├── extract.py                    # CSV/Excel/JSON/API 원천 읽기
│   ├── transform.py                  # 표준화, 타입변환, 결측/중복 처리, 집계
│   ├── validate.py                   # 필수값·범위·키·참조·코드 품질 검사
│   ├── load.py                       # ETL 전용 계정으로 INSERT/UPSERT, transaction
│   └── pipeline.py                   # extract -> transform -> validate -> load 실행
│
├── config/
│   └── text2sql_policy.yaml          # 허용 테이블/컬럼, 민감 컬럼, LIMIT, 금지 SQL
│
├── data/                             # Git 미추적 실제/산출 데이터
│   ├── raw/
│   │   ├── documents/                # 사내 원본 문서
│   │   └── source_data/              # ETL 입력 CSV/Excel/JSON
│   └── faiss/                        # FAISS index, metadata, version 파일
│
├── scripts/
│   ├── ingest_documents.py           # 문서 증분 인덱싱 CLI
│   ├── rebuild_faiss_index.py        # 전체 인덱스 재구축 CLI
│   └── load_mysql_data.py            # ETL 파이프라인 CLI
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
    │   ├── test_document_mcp.py      # RAG·ACL·FAISS adapter
    │   ├── test_data_mcp.py          # Text2SQL·SQL guard·result format
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

- 입력: `question`, 선택적 `session_id`, `user_context`.
- `security.py`에서 신뢰 가능한 사용자 컨텍스트를 생성한다. 운영 환경에서 사용자 권한을 클라이언트 입력으로 신뢰하면 안 된다.
- `graph.ainvoke()`에 초기 상태를 전달한다.
- 출력: `answer`, `sources`, `cached`, 필요 시 `route` 및 `request_id`.
- 스트리밍은 MVP 완료 후 Server-Sent Events로 추가한다.

### `app/agent/graph.py` 및 `nodes.py`

다음 노드를 명시적으로 구성한다.

1. `cache_lookup`: Cache hit면 `cached=True`와 답변을 상태에 넣는다.
2. `query_router`: `GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH`를 결정한다.
3. `document_retrieval`: Document MCP Tool을 호출한다.
4. `database_retrieval`: Data MCP Tool을 호출한다.
5. `evidence_eval`: 규칙 기반 검증 후 필요한 경우 LLM 의미 검증을 수행한다.
6. `answer_synthesis`: 검증된 evidence만 컨텍스트에 넣어 답변·출처를 만든다.
7. `cache_write`: cache miss로 생성된 답변만 저장한다.

`BOTH`는 두 retrieval 결과를 동일 state의 `document_evidence`, `database_evidence` 또는 통합 `evidence`에 축적한 뒤 `evidence_eval`로 보낸다. 구현상 한쪽 결과를 덮어쓰지 않게 주의한다.

### `app/cache/`

캐시 키는 최소 아래 요소를 해시해야 한다.

```text
normalized_question + tenant/user permission scope + conversation context hash
+ document_index_version + database freshness bucket + prompt_version + model_id
```

개발 단계에는 in-memory cache adapter를 사용해도 되지만, 배포 환경에서는 Redis adapter로 교체한다. DB 질문 TTL은 짧게(예: 1~5분), 문서 질문은 문서 갱신 정책에 맞춰 길게(예: 1시간) 설정한다.

### `mcp_servers/document/`

`search_documents(query, user_context, top_k)` Tool은 다음 순서를 지킨다.

```text
권한 범위 확인 -> query embedding -> FAISS 후보 검색 -> ACL filter
-> optional rerank -> chunk text + metadata + source 반환
```

반환값은 최소 `chunk_id`, `document_id`, `title`, `content`, `score`, `updated_at`, `allowed_roles`를 포함한다. ACL은 검색 후 필터링만 하지 말고, 가능하면 metadata filter 후보 단계에도 적용한다.

### `mcp_servers/data/`

`query_business_data(question, user_context)` Tool의 순서는 아래와 같다.

```text
스키마/용어집 제공 -> SQL 생성 -> SQL Guard -> 권한 필터 적용
-> read-only MySQL 실행 -> 결과 행 수 제한 -> 결과와 실행 메타데이터 반환
```

`sql_guard.py`는 최소 다음을 차단한다.

- `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`
- 다중 statement와 세미콜론 기반 우회
- 허용 목록 밖 테이블·컬럼
- `LIMIT` 없는 대용량 조회
- 설정된 쿼리 timeout 초과

### `ingestion/`

문서 인덱싱은 API 요청 경로에서 실행하지 않는다. `scripts/ingest_documents.py`를 통해 배치 실행한다.

```text
data/raw/documents -> load -> clean/chunk -> metadata/ACL -> embedding
-> FAISS index + metadata -> data/faiss
```

문서 변경 시 인덱스 버전을 증가시키고, cache key에서 이 버전을 사용한다. 문서 내용/ACL 변경 시 관련 캐시를 무효화하거나 이전 버전 키가 재사용되지 않게 한다.

### `etl/`

ETL은 챗봇 조회와 분리된 배치 작업이다.

```text
data/raw/source_data -> extract -> transform -> validate -> MySQL load
```

- `extract.py`: 입력 형식별 reader를 추가한다.
- `transform.py`: 컬럼명, 타입, 날짜, 통화, 코드값을 표준화하고 중복을 제거한다.
- `validate.py`: 오류 레코드를 명확히 보고한다. 품질 오류가 임계치를 넘으면 load하지 않는다.
- `load.py`: 단일 transaction으로 INSERT/UPSERT한다. ETL 전용 MySQL 계정을 사용한다.
- `pipeline.py`: 처리 입력/성공/실패 행 수와 오류를 로그에 남긴다.

## 7. 환경변수와 권한

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
```

| 계정 | 권한 | 사용하는 코드 |
|---|---|---|
| `chatbot_reader` | 허용 View/Table에 `SELECT`만 | `mcp_servers/data/mysql.py` |
| `etl_writer` | 지정된 적재 테이블에 `INSERT`, 제한적 `UPDATE` | `etl/load.py` |
| Redis 계정 | 지정 namespace의 get/set/delete | `app/cache/repository.py` |

## 8. 테스트 기준

테스트는 `tests/` 한 곳에 둔다. `tests/conftest.py`는 공통 fixture를 제공한다. 단위 테스트는 OpenAI, Redis, MCP, MySQL을 mock으로 대체하고, 통합 테스트만 테스트용 실제 인프라 또는 로컬 서버를 이용한다.

### 필수 단위 테스트

- 동일 질문·동일 권한·동일 버전이면 cache key가 동일하다.
- 권한 또는 문서 버전이 달라지면 cache key가 달라진다.
- `DOCUMENT`, `DATABASE`, `GENERAL`, `BOTH` 라우팅이 기대대로 동작한다.
- ACL이 없는 문서는 Document MCP 결과에서 제외된다.
- SQL Guard가 쓰기 쿼리, 다중 쿼리, 비허용 테이블, LIMIT 누락을 거부한다.
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

## 9. 구현 순서

1. FastAPI `/api/health`, 최소 UI, `ChatRequest/ChatResponse` 구현.
2. In-memory Answer Cache와 cache hit/miss 단위 테스트 구현.
3. LangGraph `GENERAL` 및 `DOCUMENT` 라우팅과 mock MCP Client 구현.
4. Document MCP, 문서 ingestion, FAISS 검색, ACL 필터 구현.
5. Data MCP, schema policy, Text2SQL skeleton, SQL Guard 구현.
6. ETL extract/transform/validate/load와 테스트 MySQL 통합 테스트 구현.
7. Evidence Eval 및 `BOTH` 경로 구현.
8. Redis adapter, 실제 OpenAI 호출, 비용·오류 로그를 연결.

## 10. 완료 조건

- [ ] 동일 질문 재요청 시 캐시 답변이 반환되고 LLM/MCP 호출이 없다.
- [ ] 문서 질문은 Document MCP를 통해서만 FAISS를 조회한다.
- [ ] 데이터 질문은 Data MCP를 통해서만 MySQL을 읽기 조회한다.
- [ ] `BOTH` 질문에서 문서/DB 근거가 모두 보존되고 출처와 함께 답변된다.
- [ ] Data MCP가 어떤 경우에도 DML/DDL을 실행하지 않는다.
- [ ] ETL만 MySQL 쓰기 권한을 가지며, 검증 실패 데이터는 적재하지 않는다.
- [ ] pytest 단위·통합 테스트가 통과한다.
- [ ] 실제 사내 문서·원천 데이터·`.env`·FAISS 산출물은 Git에 커밋하지 않는다.

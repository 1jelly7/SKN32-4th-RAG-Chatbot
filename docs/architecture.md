# 아키텍처와 코드 경계

## 목적

이 문서는 [README](../README.md)의 프로젝트 설명을 실제 코드 구조와 연결한다.
현재 애플리케이션은 FastAPI가 인증, 캐시, LangGraph를 조율하고, LangGraph는 MCP Client
경계를 통해 문서 검색과 구매·판매 조회를 요청한다. ETL과 문서 인덱싱은 채팅 요청과
분리된 배치 작업이다.

## 전체 구성

```text
Browser (HTML/CSS/JavaScript, Chart.js)
  -> FastAPI
      -> Auth: 서명된 HttpOnly 세션 + 서버 측 활성 세션 확인
      -> RBAC: admin / hr / finance
      -> Answer Cache: MemoryCache
      -> LangGraph
          -> Router
          -> Document retrieval -> MCP Client -> Document Tool service
          -> Database retrieval -> MCP Client -> Purchase/Sales Tool service
          -> Evidence evaluation
          -> Answer synthesis
      -> ChatResponse / document download

Offline preparation
  -> document registration -> document_paths
  -> document ingestion -> persistent FAISS index
  -> purchase/sales ETL -> MySQL tables and read-only views
```

FastAPI와 Agent는 원문 파일, FAISS, 업무 MySQL을 직접 조회하지 않는다. 현재 기본
transport는 `InProcessMCPPort`이며 같은 Python 프로세스에서 Tool service를 호출한다.
`.env`의 `DOCUMENT_MCP_URL`, `DATA_MCP_URL`을 사용하는 원격 MCP transport는 아직
연결되지 않았다.

## HTTP 요청 흐름

### 인증과 공통 처리

1. `POST /api/auth/login`이 계정 저장소의 활성 계정과 scrypt 비밀번호 해시를 검증한다.
2. 성공하면 HMAC 서명된 `chatbot_session` 쿠키를 `HttpOnly`, `SameSite=Lax`로 발급하고
   서버의 `SessionStore`에 세션을 등록한다.
3. `/api/chat`, `/api/auth/me`, `/api/auth/logout`, 문서 다운로드는 유효한 쿠키와 활성
   서버 세션을 요구한다.
4. HTTP middleware는 요청마다 `request_id`, `X-Request-ID`, `Server-Timing`을 만들고
   비밀값 없는 요청 완료 로그를 기록한다.

역할별 DB 허용 범위는 `app/auth/policy.py`가 결정한다.

| 역할 | 허용 DB |
|---|---|
| `admin` | `account_db`, `document_db`, `purchase_db`, `sales_db` |
| `hr` | `account_db`, `document_db` |
| `finance` | `document_db`, `purchase_db`, `sales_db` |

UI에서 버튼을 숨기는 것만으로 권한을 판단하지 않는다. Data/Document Tool 진입점에서
서버가 만든 사용자 컨텍스트를 다시 검사한다.

### 채팅 처리

```text
POST /api/chat
  -> Pydantic ChatRequest 검증
  -> 인증 사용자·세션을 포함한 cache key 생성
  -> cache hit: Graph/LLM/MCP 호출 없이 즉시 응답
  -> cache miss: LangGraph
       -> Router
       -> Retrieval (필요한 route만)
       -> Evidence Eval
       -> 근거 부족이면 동일 route 1회 재조회
       -> Answer Synthesis
  -> 재사용 가능한 답변만 cache 저장
  -> ChatResponse
```

라우터는 명시 키워드를 우선 사용하고, 키워드가 없는 일부 질문은 임베딩 앵커 유사도로
`DOCUMENT` 또는 `DATABASE`를 보강 판정한다. 허용 route는 다음 네 가지다.

| route | 처리 |
|---|---|
| `GENERAL` | 검색 없이 LLM 답변 생성 |
| `DOCUMENT` | Document Tool만 호출 |
| `DATABASE` | 질문에 따라 구매, 판매 또는 두 Data Tool 호출 |
| `BOTH` | Document 이후 Database를 순서대로 호출해 근거를 분리 보존 |

`BOTH`는 현재 병렬 fan-out이 아니라 `document -> database` 순차 흐름이다. 한 도메인
조회가 실패해도 다른 근거가 있으면 `PARTIALLY_SUPPORTED` 응답을 만들 수 있다.

## 문서 RAG 경계

문서 등록·인덱싱과 질의 시 검색을 분리한다.

### 배치 준비

```text
data/raw/documents/
  -> scripts/register_documents.py
  -> MySQL document_paths (활성 문서 ID와 경로 metadata)
  -> scripts/ingest_documents.py 또는 scripts/rebuild_faiss_index.py
  -> data/faiss/index.faiss + metadata.json
```

인덱스에는 청크 본문과 공개 출처 metadata가 저장된다. 원천 문서와 FAISS 산출물은 Git에
커밋하지 않는다.

### 질의 시 검색

1. `document_db.py`가 모든 활성 문서의 `document_id`, `title`, `file_path`,
   `updated_at`을 허용 목록으로 조회한다. 제목 `LIKE`로 사전 필터링하지 않는다.
2. `rag.py`가 배치 생성된 영구 FAISS 인덱스를 프로세스 내에서 재사용한다.
3. 벡터 검색과 어휘 검색 결과를 합치고, 활성 `document_id`에 포함된 청크만 남긴다.
4. 직접 검색 최고 점수가 기준보다 낮으면 Agent가 동의어 확장 질의를 추가 호출한다.
5. 사용자 응답에는 문서 ID, 제목, 페이지, 발췌문, 인덱스 버전만 전달하고 내부
   `file_path`는 제거한다.

질문마다 원문 PDF/TXT/Markdown을 다시 읽거나 임시 인덱스를 만들지 않는다. 원문 파일
로드는 등록·인덱싱, 시작 시 선택적 warm-up, 다운로드 경계에서만 사용한다.

### 원문 다운로드

출처 카드의 `download_url`은 `GET /api/documents/download?doc_id=...`를 가리킨다.
Host의 in-process `resolve_document_download` 경계가 활성 문서 ID를 등록 경로로 해석한
후 파일을 반환한다. 클라이언트는 파일 경로를 입력할 수 없고 응답에도 경로가 노출되지
않는다. 이 다운로드 경계는 현재 독립 원격 Document MCP 서버 Tool로 등록돼 있지 않다.

## 구매·판매 Text2SQL 경계

```text
자연어 질문
  -> 도메인 schema·용어집을 LLM에 제공
  -> SQL 또는 NO_SQL 생성
  -> 단일 SELECT/WITH, 허용 View, 금지 키워드, LIMIT <= 200 검사
  -> ETL/admin 계정으로 EXPLAIN 사전 검증
  -> 실패 시 오류 문맥으로 SQL 1회 재작성
  -> 도메인 read-only 계정으로 실행
  -> 행·SQL·실행 metadata를 공통 envelope로 반환
```

구매와 판매는 서로 다른 허용 View 목록과 DB 계정을 사용한다. API/Agent 경로에서는
INSERT, UPDATE, DELETE, DDL과 ETL을 실행하지 않는다. 결과가 없거나 LLM이 해당 스키마로
답할 수 없다고 판단하면 `NO_RESULT`가 되며, Graph에서는 빈 근거로 평가한다.

원천 구매·판매 데이터는 AdventureWorks2022 Excel 자료를 바탕으로 하며, 프로젝트 팀이
LLM으로 설계한 교육·테스트용 합성 데이터를 추가했다. 이 증강 과정은 오프라인 데이터
준비 단계이며 채팅 런타임의 LLM 호출과는 별개다. 판매 workbook 재생성 스크립트는 고정
seed와 규칙을 사용하고 실행 중 LLM API를 호출하지 않는다.

## 근거 평가와 응답

`evidence_eval.py`는 새 사실을 만들지 않고 관련성, 신뢰도, 필수 metadata, freshness와
명시적 사실 충돌만 결정적으로 평가한다.

| 상태 | 처리 |
|---|---|
| `SUPPORTED` | 채택 근거로 답변 생성, 캐시 가능 |
| `PARTIALLY_SUPPORTED` | 확인된 근거만 사용하고 부분 실패 안내, 현재 캐시하지 않음 |
| `INSUFFICIENT` | 동일 retrieval 경로를 최대 1회 재조회한 뒤 안전한 부족 안내 |
| `CONTRADICTED` | 재조회하지 않고 단일 답변을 만들 수 없다는 안내 |

현재 두 번째 평가도 `INSUFFICIENT`이면 예외를 발생시키지 않고 HTTP 200의 안전한 안내를
반환한다. HTTP 422 `EVIDENCE_INSUFFICIENT` 매핑은 MCP Client 예외가 API 경계까지 직접
전파될 때를 위한 공개 오류 계약이다.

문서 출처는 `document_id`별 카드로 합쳐 페이지와 발췌문을 중복 제거한다. DB 근거는
표와 공개 SQL로 변환하며, 경로·비밀번호·token 계열 컬럼은 제거한다. 도메인 Tool의
`chart_hint`는 metadata에 존재하지만 현재 `TableData.chart_type`으로 전달되지 않아 UI는
막대 차트를 기본값으로 사용한다.

## 캐시와 상태

- 기본 저장소는 프로세스 내 `MemoryCache`다. `RedisCache`는 인터페이스만 있고 구현되지 않았다.
- 키 재료는 정규화 질문, 대화 문맥 해시, 사용자 ID·역할·세션·허용 DB, 문서 인덱스
  버전, DB freshness bucket, 프롬프트 버전, 모델 식별자다.
- TTL은 `GENERAL`/`DATABASE`/`BOTH` 300초, `DOCUMENT` 3600초다.
- `GENERAL`과 `SUPPORTED` 결과만 저장한다. 오류, `PARTIALLY_SUPPORTED`,
  `INSUFFICIENT`, `CONTRADICTED`, 기존 hit는 저장하지 않는다.
- 문서 검색 결과의 실제 인덱스 버전은 응답 후 앱의 cache-key context에 반영된다.
- DB freshness bucket은 현재 `unknown`이며 ETL 완료 후 자동 갱신·분산 무효화는 연결되지 않았다.

## 배치와 초기화

| 배치 | 책임 |
|---|---|
| `scripts/register_documents.py` | 문서 경로 등록 |
| `scripts/ingest_documents.py` | 문서 로드·청킹·임베딩·FAISS 생성 |
| `scripts/rebuild_faiss_index.py` | 문서 변경 후 인덱스 재생성 |
| `etl/purchase/`, `etl/sales/` | 원천 workbook 검증·변환·UPSERT |
| `scripts/seed_accounts.py` | 초기 로그인 계정 시딩 |
| `scripts/setup_all.py` | Windows 로컬 DB·문서·ETL 초기화 보조 |

`scripts/setup_all.py`는 MySQL 8.0 기본 설치 경로와 여러 로컬 계정·비밀번호를 전제로
한다. 또한 현재 파일 이동 후 내부 상대경로가 프로젝트 루트 실행 방식과 일치하지 않는
부분이 있으므로, 경로·계정·DB명을 검토하고 각 수동 명령으로 검증하기 전에는 재현 가능한
원클릭 설치로 간주하지 않는다.

## 소유권 기반 배치

| 경로 | 책임 | 담당 |
|---|---|---|
| `app/` | FastAPI, 인증, Graph, 캐시, 공통 로그, UI | Backend/통합 |
| `ingestion/`, `mcp_servers/document_tools/` | 문서 등록·검색·FAISS | RAG PDF |
| `mcp_servers/data_tools/server.py` | Data Tool 등록과 공통 envelope | Backend/통합 |
| `mcp_servers/data_tools/purchase/`, `etl/purchase/`, `database/purchase/` | 구매 조회·ETL·DDL | RAG Purchasing |
| `mcp_servers/data_tools/sales/`, `etl/sales/`, `database/sales/` | 판매 조회·ETL·DDL | RAG Sales |

상세 담당자와 변경 절차는 [ownership.md](ownership.md), Tool과 HTTP 계약은
[interface.md](interface.md), 검증 범위는 [test-scenarios.md](test-scenarios.md)를 따른다.

## 현재 구현 제한

- 기본 MCP transport는 same-process이며 원격 URL transport가 없다.
- Redis adapter와 readiness endpoint가 없다. `/api/health`는 프로세스 liveness만 확인한다.
- 실제 외부 문서 DB·FAISS·구매·판매 DB를 한 번에 연결하는 자동 통합 테스트는 없다.
- `tests/integration/test_etl_mysql_flow.py`는 placeholder다.
- DB freshness/source version의 운영 공급과 ETL 기반 캐시 무효화가 연결되지 않았다.
- `query_classification.py`의 위험·신선도 label은 단위 테스트 대상이지만 기본 router에서
  `query_labels`로 주입되지 않아 일반 질문의 실시간성 fallback에 자동 연결되지 않는다.

# 테스트 시나리오 및 완료 기준

## 목적

현재 자동 검증과 아직 외부 인프라가 필요한 목표 수용 시나리오를 구분한다. fake 기반
chat 흐름 통과는 실제 원격 MCP·DB·FAISS 연결 완료를 뜻하지 않는다.

## 현재 자동 검증

2026-08-02 기준 자동 테스트는 다음 범위를 검증한다.

| 테스트 파일 | 검증 범위                                                    |
|---|--------------------------------------------------------------|
| `tests/unit/test_agent.py` | route/domain 판정, evidence 상태, BOTH fan-in, 1회 보강 조회 |
| `tests/unit/test_cache.py`, `tests/integration/test_cache_flow.py` | 질문·세션 문맥별 키와 Graph 외부 cache short-circuit         |
| `tests/unit/test_api.py` | `/api/health`, session cache 격리, 공개 오류 매핑            |
| `tests/unit/test_document_mcp.py` | 문서 DB 경로 조회 → 파일 로드 → RAG 호출 순서                |
| `tests/unit/test_data_mcp.py` | 구매·판매 Tool dispatch, 공통 envelope와 오류 분류 |
| `tests/unit/test_etl.py` | legacy finance 및 구매·판매 ETL 변환 계약 |
| `tests/unit/test_logging.py` | 5필드 로그 포맷                                              |
| `tests/integration/test_chat_document_flow.py` | fake Document MCP 기반 API→Graph 흐름                        |
| `tests/integration/test_chat_data_flow.py` | fake purchase/sales MCP 기반 API→Graph 흐름                  |
| `tests/integration/test_chat_error_flow.py` | empty/query/malformed/timeout HTTP 매핑                      |

chat integration 테스트는 외부 서비스가 없는 in-process fake 기반 계약 테스트다.
`test_etl_mysql_flow.py`만 placeholder이므로 ETL 외부 통합 완료의 근거로 사용하지 않는다.
`RUN_LOCAL_MYSQL_TESTS=1` opt-in agent 테스트는 same-process Data MCP 뒤의 sales DB 조회만
검증하며 Document MCP 또는 ETL 통합을 증명하지 않는다.

## 공통 테스트 데이터

| 구분 | 최소 준비물 |
|---|---|
| 문서 DB | 문서 식별자·제목·파일 경로·갱신 시각 레코드 3건 이상 |
| 문서 파일 | 문서 DB 경로와 일치하는 PDF/TXT/Markdown 3건 이상 |
| 구매 | 공급업체별 구매 금액 샘플 데이터 |
| 판매 | 월별·상품별 매출 샘플 데이터 |
| 질문 | 문서 2개, 구매 2개, 판매 2개, BOTH 1개, 실패 질문 2개 |

## 목표 단위 수용 테스트

### TS-U01: 문서 경로 조회

- 내부 문서 DB 조회 결과가 `document_id`, `title`, `file_path`, `updated_at`을 포함한다.
- 문서 본문을 DB 응답으로 직접 받지 않는다.
- 조회 결과가 없으면 빈 목록을 반환한다.

### TS-U02: 문서 파일 로드 및 검색

- 문서 DB에서 반환된 경로만 파일 로더에 전달한다.
- PDF/TXT/Markdown 파일을 읽은 뒤 RAG 검색을 실행한다.
- 사용자 응답에는 내부 파일 경로가 포함되지 않는다.

### TS-U03: 구매 질의 Tool

- `query_purchase`가 구매 스키마와 읽기 전용 DB 연결을 사용한다.
- envelope metadata에 생성 SQL, 행 수, 실행 시간을 반환한다. freshness와 source version은
  공급자가 제공하기 전까지 완료된 계약으로 간주하지 않는다.

### TS-U04: 판매 질의 Tool

- `query_sales`가 판매 스키마와 읽기 전용 DB 연결을 사용한다.
- envelope metadata에 생성 SQL, 행 수, 실행 시간을 반환한다. freshness와 source version은
  공급자가 제공하기 전까지 완료된 계약으로 간주하지 않는다.

### TS-U05: 캐시 처리

- 동일 질문·동일 문맥·동일 버전의 캐시 키가 동일하다.
- 문맥 또는 문서 인덱스 버전이 바뀌면 키가 달라진다.
- 캐시는 LangGraph 실행 전과 실행 완료 후에만 접근한다.

### TS-U06: evidence_eval 판정

- 관련성이 낮거나 부족한 근거는 `INSUFFICIENT`로 판정한다.
- 서로 충돌하는 근거는 `CONTRADICTED`로 판정한다.
- `INSUFFICIENT`는 같은 retrieval 경로를 한 번만 보강하고 이후 422
  `EVIDENCE_INSUFFICIENT`로 종료한다.
- `CONTRADICTED`는 보강 조회하지 않고 성공 응답의 `evidence_status`로 구별한다.

### TS-U06A: MCP 오류 분류

- `INVALID_INPUT`, `NO_RESULT`, `QUERY_ERROR`, `EVIDENCE_INSUFFICIENT`, `INTERNAL_ERROR`는
  Host client에서 서로 다른 의미로 보존한다.
- timeout은 HTTP 504와 `TIMEOUT`으로 반환하며 query error로 축약하지 않는다.
- malformed envelope는 provider 오류 메시지를 노출하지 않고 `INTERNAL_ERROR`로 처리한다.

### TS-U07: ETL 멱등성 및 실행 이력

- 동일 원천 데이터로 ETL을 두 번 실행해도 행 수가 증가하지 않는다.
- 구매·판매 로그에 실행 시각, 처리 행 수, 검증 결과가 기록된다.

## 목표 통합 수용 테스트

### TS-I01: 문서 질의 전체 흐름

```text
캐시 미스 -> Router(DOCUMENT) -> Document MCP
-> 문서 DB 경로 조회 -> 파일 로드 -> RAG -> evidence_eval -> 답변
```

완료 조건은 HTTP 200, 문서 출처 존재, 내부 파일 경로 미노출, RAG 실행 로그 존재다.

### TS-I02: 구매 질의 전체 흐름

`Router(DATABASE, purchase)`가 `query_purchase`만 호출하고 테스트 DB의 수치와 같은 결과를
반환한다.

### TS-I03: 판매 질의 전체 흐름

`Router(DATABASE, sales)`가 `query_sales`만 호출하고 테스트 DB의 수치와 같은 결과를
반환한다.

### TS-I04: BOTH 병합

문서+판매 질문이면 `search_documents`와 `query_sales`를 호출하고 두 출처를 구분해
표시한다. 한쪽 결과만 성공하면 부분 응답으로 진행한다.

### TS-I05: 캐시 적중

같은 질문을 두 번 요청했을 때 두 번째 요청은 LLM과 MCP를 호출하지 않는다.

### TS-I06: 문서 경로 또는 파일 없음

문서 DB에 경로가 없거나 파일이 사라진 경우 해당 상태를 명확히 보고하고 임의 경로의
파일을 대신 읽지 않는다.

### TS-I07: FAISS 재인덱싱

문서 DB에 파일 경로를 추가하고 재인덱싱한 뒤 새 `index_version`이 응답 metadata와
캐시 키에 반영된다.

## 발표 필수 시나리오

| 번호 | 질문 | 검증 포인트 |
|---|---|---|
| D01 | 사내 문서 질문 | 문서 DB 경로 조회, 파일 로드, RAG, 출처 |
| D02 | 구매 집계 질문 | 구매 Tool, 수치 근거 |
| D03 | 판매 집계 질문 | 판매 Tool, 수치 근거 |
| D04 | 문서+판매 복합 질문 | BOTH 병합, 도메인별 출처 |
| D05 | 반복 질문 | 캐시 적중 |

## 목표 완료 판정

- 담당 기능의 단위 테스트가 통과한다.
- 실제 문서 DB·파일·MCP·FAISS·업무 DB를 연결한 통합 테스트가 통과한다.
- `interface.md`의 응답 형식과 병합 규칙을 준수한다.
- 오류 상황에서 구조화된 응답을 반환한다.
- 발표 필수 시나리오 D01~D05를 로컬 환경에서 재현할 수 있다.

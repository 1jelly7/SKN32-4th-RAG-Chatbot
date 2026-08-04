# MCP Tool 인터페이스 계약

## 목적

FastAPI/LangGraph Host와 MCP Server 간 Tool 호출 형식을 정의한다.

- Host는 문서 파일·FAISS·업무 DB에 직접 접근하지 않고 MCP Tool만 호출한다.
- 캐시는 LangGraph 실행 전에 `app/cache/`에서 처리한다.
- 검색·조회 결과는 evidence_eval을 통과해야 최종 답변에 사용된다.

## 현재 구조와 계약 단계

| 계약 영역 | 현재 경로 | 소유자 | 상태 |
|---|---|---|---|
| 문서 경로 조회 | `mcp_servers/document_tools/document_db.py` | RAG 담당 | 비동기 DB 조회 구현 |
| 문서 파일 로드 | `mcp_servers/document_tools/file_loader.py` | RAG 담당 | 로더 조합 구현 |
| 문서 검색 | `mcp_servers/document_tools/search.py` | RAG 담당 | 경로 조회 → 파일 로드 → RAG 순서 구현 |
| 공통 데이터 서버 | `mcp_servers/data_tools/server.py` | 통합 담당 | Tool 등록·공통 envelope 구현 |
| 구매 조회 | `mcp_servers/data_tools/purchase/` | 구매 담당 | Text2SQL·read-only 조회 구현 |
| 판매 조회 | `mcp_servers/data_tools/sales/` | 판매 담당 | Text2SQL·read-only 조회 구현 |
| 근거 평가 | `app/agent/evidence_eval.py` | 통합 담당 | 결정적 정책 평가 구현; Graph가 1회 보강 제어 |

Host는 현재 같은 프로세스의 Tool service를 비동기 MCP port로 호출한다. 아래 envelope는
구현된 Host/Data Tool 계약이다. 원격 URL transport와 실제 외부 문서 DB·FAISS·업무 DB를
모두 사용하는 수용 검증은 아직 완성되지 않았다.

## 요청 처리 순서

1. **캐시 조회**: 정규화된 질문과 버전 정보로 캐시를 조회한다.
2. **Router**: 질문을 `GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH`로 분류한다.
3. **MCP Tool 호출**: 분류에 따라 `search_documents`, `query_purchase`, `query_sales`를 호출한다.
4. **evidence_eval**: 반환된 근거가 질문에 답하기에 충분한지 검증한다.
5. **답변 합성**: 검증된 근거만으로 최종 답변을 생성한다.
6. **캐시 저장**: 재사용 가능한 최종 응답을 저장한다.

## 캐시 책임

- 캐시는 `app/cache/`에서만 처리하며 LangGraph 그래프 진입 전에 위치한다.
- 캐시 키는 정규화 질문, 대화 문맥 해시, 문서 인덱스 버전, DB freshness bucket,
  프롬프트 버전, 모델 식별자를 정렬·직렬화해 SHA-256으로 해시한다.
- `session_id`가 있으면 원문을 저장하지 않고 SHA-256 해시를 대화 문맥 식별자로 사용해
  서로 다른 세션의 동일 질문이 같은 답변 항목을 공유하지 않게 한다.
- 문서 재인덱싱 또는 데이터 재적재가 끝나면 관련 캐시를 무효화한다.
- Router, MCP Client, evidence_eval은 캐시를 직접 읽거나 쓰지 않는다.

## 공통 응답 형식

### 성공

```json
{
  "status": "success",
  "domain": "document | purchase | sales | both",
  "message": null,
  "data": [],
  "sources": [],
  "metadata": {}
}
```

### 실패

```json
{
  "status": "error",
  "domain": "document | purchase | sales | both",
  "message": "사용자에게 표시 가능한 오류 설명",
  "error_code": "INVALID_INPUT | NO_RESULT | FORBIDDEN | QUERY_ERROR | EVIDENCE_INSUFFICIENT | TIMEOUT | INTERNAL_ERROR",
  "data": [],
  "sources": [],
  "metadata": {}
}
```

Host의 공개 HTTP 매핑은 `INVALID_INPUT=400`, `FORBIDDEN=403`, `NO_RESULT=404`,
`EVIDENCE_INSUFFICIENT=422`, `QUERY_ERROR=502`, `INTERNAL_ERROR=502`,
`TIMEOUT=504`다. MCP timeout은 `QUERY_ERROR`로 축약하지 않는다. malformed envelope는
provider의 `INTERNAL_ERROR`와 별도로 Host 검증 실패로 처리하되 공개 코드는
`INTERNAL_ERROR`를 사용한다.

## Tool 1: 문서 검색

- Tool 이름: `search_documents`
- 구현 경로: `mcp_servers/document_tools/`
- 담당: RAG 담당

### 입력

```json
{
  "query": "휴가 신청 절차를 알려줘",
  "top_k": 3
}
```

### 내부 처리 계약

1. 내부 문서 DB에서 질문과 관련된 경로 레코드를 조회한다.
2. 경로 레코드는 `document_id`, `title`, `file_path`, `updated_at`만 포함한다.
3. `file_loader.py`가 조회된 경로의 PDF/TXT/Markdown 파일을 읽는다.
4. 읽은 문서만 RAG 검색 대상으로 전달한다.
5. 내부 `file_path`는 사용자 응답에 노출하지 않는다.

### 성공 응답

```json
{
  "status": "success",
  "domain": "document",
  "message": null,
  "data": [
    { "content": "휴가 신청은 ...", "score": 0.87 }
  ],
  "sources": [
    { "document_id": "hr_policy_001", "title": "인사 규정", "page": 12 }
  ],
  "metadata": {
    "index_version": "v3",
    "result_count": 1
  }
}
```

검색 결과가 없으면 `error_code="NO_RESULT"`, 경로 조회·파일 로드·인덱스 처리에 실패하면
`error_code="INTERNAL_ERROR"`를 반환한다.

## 문서 원본 다운로드 HTTP API

- Endpoint: `GET /api/documents/download?doc_id=<document_id>`
- 인증: 유효한 로그인 세션과 `document_db` 접근 권한이 필요하다.
- `doc_id`는 Chat API가 문서 출처 카드에 발급한 `document_id`만 사용한다. 클라이언트가 파일 경로를 전달할 수 없으며, 서버는 `document_paths`의 활성 레코드로만 경로를 해석한다.
- 성공 시 원본 파일을 `application/octet-stream`으로 반환하고, 한글 파일명을 포함해 `Content-Disposition: filename*=UTF-8''...` 헤더를 사용한다.
- 등록되지 않았거나 비활성인 ID, 또는 원본이 없는 경우 `404`를 반환한다. 서버 내부 파일 경로는 어떤 응답에도 포함하지 않는다.

## Chat API 문서 출처 카드

`POST /api/chat`의 `sources` 중 `source_type="document"` 항목은 검색 청크 단위가 아니라 문서 단위다. 같은 `document_id`의 청크는 하나로 합치며, `pages`는 오름차순 중복 제거 목록이고 `chunks`는 페이지별 발췌문이다. `download_url`은 해당 문서 ID의 다운로드 API URL이다. DB 출처 항목의 계약은 변경하지 않는다.

## Tool 2: 구매 데이터 조회

- Tool 이름: `query_purchase`
- 구현 경로: `mcp_servers/data_tools/purchase/`
- 담당: 구매 담당

### 입력

```json
{ "question": "공급업체별 구매 금액을 알려줘" }
```

### 처리 순서

```text
구매 스키마·용어집 제공 -> SELECT SQL 생성 -> read-only MySQL 실행
-> 결과와 실행 metadata 반환
```

## Tool 3: 판매 데이터 조회

- Tool 이름: `query_sales`
- 구현 경로: `mcp_servers/data_tools/sales/`
- 담당: 판매 담당

### 입력

```json
{ "question": "2025년 1분기 상품별 매출을 알려줘" }
```

### 처리 순서

```text
판매 스키마·용어집 제공 -> SELECT SQL 생성 -> read-only MySQL 실행
-> 결과와 실행 metadata 반환
```

### 성공 응답 metadata

판매 Tool은 공통 `generated_sql`, `row_count`, `elapsed_ms`와 함께 도메인 metadata를
그대로 반환한다. `views_used`, `data_coverage`, `retry_count`, `currency`, `truncated`,
`chart_hint`를 포함하며, `chart_hint`는 `bar` 또는 `line`이다. 빈 결과는
`NO_RESULT`와 원인·재질문 방법이 포함된 `message`를 반환한다.

```json
{
  "status": "success",
  "domain": "sales",
  "message": null,
  "data": [{"order_month": "2026-01", "total_sales": 1234.5}],
  "sources": [],
  "metadata": {
    "generated_sql": "SELECT ...",
    "row_count": 1,
    "elapsed_ms": 12.3,
    "views_used": ["v_sales_order"],
    "data_coverage": {"min_order_date": "...", "max_order_date": "..."},
    "retry_count": 0,
    "currency": "JOD",
    "truncated": false,
    "chart_hint": "line"
  }
}
```

## 라우팅 규칙과 BOTH 병합

| 질문 유형 | 호출 Tool | 병합 방식 |
|---|---|---|
| 일반 질문 | 없음 | LLM 단독 응답 |
| 문서 질문 | `search_documents` | 단일 결과 사용 |
| 구매 질문 | `query_purchase` | 단일 결과 사용 |
| 판매 질문 | `query_sales` | 단일 결과 사용 |
| 문서+수치 질문 | 관련 Tool 모두 호출 | 도메인별 근거를 보존해 병합 |

`BOTH`에서는 각 Tool 응답을 별도 evidence로 유지한다. 한 Tool이 실패해도 다른 Tool 결과가
있으면 부분 응답으로 진행하고, 모든 Tool이 실패하면 `NO_RESULT`를 반환한다.

## evidence_eval 계약

```json
{
  "evidence_status": "SUPPORTED | PARTIALLY_SUPPORTED | INSUFFICIENT | CONTRADICTED",
  "reason": "관련성 낮음 | 근거 부족 | 상충하는 근거",
  "filtered_evidence": []
}
```

`INSUFFICIENT`이면 원래 route의 retrieval을 정확히 한 번 보강 실행한다. 두 번째 평가도
`INSUFFICIENT`이면 HTTP 422 `EVIDENCE_INSUFFICIENT`로 전환한다. `CONTRADICTED`는 저신뢰
근거와 구별하며 재시도하지 않는다. 이 경우 공개 성공 응답의 `evidence_status`를
`CONTRADICTED`로 유지하고, 상충 때문에 단일 답변을 만들 수 없다는 경고를 반환한다.

`ChatResponse`는 `answer`, `sources`, `tables`, `cached`, `route`, `evidence_status`,
`request_id`를 반환한다. cache hit도 저장된 `evidence_status`를 보존한다.

## 변경 규칙

- Tool 이름, 공통 응답 필드, BOTH 병합 형식 변경은 통합 담당과 관련 도메인 담당이 함께 검토한다.
- 문서 경로 레코드 형식 변경은 RAG 담당과 통합 담당이 함께 검토한다.
- 인덱스 버전 스키마 변경은 RAG 담당과 통합 담당이 함께 검토한다.

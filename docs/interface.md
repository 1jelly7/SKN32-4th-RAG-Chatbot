# MCP Tool 인터페이스 계약

## 목적

FastAPI/LangGraph Host와 MCP Server 간 Tool 호출 형식을 정의한다.

- Host는 문서·DB에 직접 접근하지 않고 MCP Tool만 호출한다.
- 캐시는 LangGraph 실행 전단에서 단일 책임으로 처리한다.
- 검색·조회 결과는 evidence_eval을 통과해야 최종 답변에 사용된다.

## 현재 구조와 계약 단계

| 계약 영역 | 현재 경로 | 소유자 | 상태 |
|---|---|---|---|
| 문서 검색 | `mcp_servers/document_tools/` | RAG 담당 | Tool 경계와 타입 정의 단계 |
| 공통 데이터 서버·Guard | `mcp_servers/data_tools/server.py`, `sql_guard.py` | 통합 담당 | 최소 SELECT/쓰기 차단 구현 |
| 재무 조회 | `mcp_servers/data_tools/finance/` | 재무 담당 | 도메인 인터페이스 스켈레톤 |
| 판매 조회 | `mcp_servers/data_tools/sales/` | 판매 담당 | 도메인 인터페이스 스켈레톤 |
| 근거 평가 | `app/agent/evidence_eval.py` | 통합 담당 | 경계 분리 단계 |

아래 Tool 응답은 구현해야 할 계약이다. 현재 MCP transport와 실제 DB·FAISS 호출은 아직
완성되지 않았으므로, 미구현 경로가 이 형식의 성공 응답을 반환한다고 가정해서는 안 된다.

## 요청 처리 순서

1. **캐시 조회**: 정규화된 질문으로 캐시를 조회한다. 적중 시 LangGraph, MCP, LLM을 모두 호출하지 않고 즉시 응답한다.
2. **Router**: 질문을 `GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH`로 분류한다.
3. **MCP Tool 호출**: 분류에 따라 `search_documents`, `query_finance`, `query_sales`를 호출한다.
4. **evidence_eval**: 반환된 근거가 질문에 답하기에 충분하고 신뢰할 수 있는지 검증한다.
5. **답변 합성**: evidence_eval을 통과한 근거만으로 최종 답변을 생성한다.
6. **캐시 저장**: 최종 응답을 캐시에 저장한다.

## 캐시 책임 (단일 위치)

- 캐시는 `app/cache/`에서만 처리하며, LangGraph 그래프 진입 전에 위치한다.
- 캐시 키: 정규화 질문, `user_id`, `tenant_id`, `role`, 권한 목록, 문서 인덱스 버전,
  대화 문맥 해시, DB freshness bucket, 프롬프트 버전, 모델 식별자를 정렬·직렬화해
  SHA-256으로 해시한다.
- 현재 구현은 위 값이 GraphState에 제공되면 모두 키에 반영한다. 실제 재인덱싱·ETL
  완료 시 무효화 호출은 후속 구현 범위다.
- 캐시 대상: evidence_eval을 통과한 최종 응답만 저장한다.
- 캐시 무효화: 문서 재인덱싱 또는 데이터 재적재 시 관련 도메인 캐시를 명시적으로 삭제한다.
- 다른 모듈(Router, MCP Client, evidence_eval)은 캐시를 직접 읽거나 쓰지 않는다.

## 공통 응답 형식

### 성공

```json
{
  "status": "success",
  "domain": "document | finance | sales",
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
  "domain": "document | finance | sales",
  "message": "사용자에게 표시 가능한 오류 설명",
  "error_code": "INVALID_INPUT | NO_RESULT | QUERY_ERROR | EVIDENCE_INSUFFICIENT | INTERNAL_ERROR",
  "data": [],
  "sources": [],
  "metadata": {}
}
```

## Tool 1: 문서 검색

- Tool 이름: `search_documents`
- 제공 서버: Document MCP Server
- 담당: RAG 담당자
- 구현 경로: `mcp_servers/document_tools/`

### 입력

```json
{
  "query": "휴가 신청 절차를 알려줘",
  "top_k": 3
}
```

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
    "index_built_at": "2026-07-25T10:00:00+09:00",
    "result_count": 1
  }
}
```

### FAISS 인덱스 버전 관리

- `index_version`은 `ingestion/` 재실행 시마다 정수 또는 날짜 기반으로 증가시킨다.
- 인덱스 파일과 함께 `manifest.json`(버전, 문서 수, 생성 시각, 임베딩 모델명)을 저장한다.
- Document MCP Server는 시작 시 `manifest.json`을 읽어 `index_version`을 응답 메타데이터에 포함한다.
- 재인덱싱 완료 전까지는 이전 버전 인덱스로 계속 서비스한다.

### 실패 규칙

- 검색 결과가 없으면 `error_code="NO_RESULT"`.
- 인덱스 로드 실패 시 `error_code="INTERNAL_ERROR"`.

## Tool 2: 재무 데이터 조회

- Tool 이름: `query_finance`
- 제공 서버: Data MCP Server (재무 모듈)
- 담당: 재무 데이터 담당자
- 구현 경로: `mcp_servers/data_tools/finance/`

### 입력

```json
{ "question": "2025년 분기별 매출과 영업이익을 알려줘" }
```

### 성공 응답

```json
{
  "status": "success",
  "domain": "finance",
  "message": null,
  "data": [
    { "quarter": "2025-Q1", "revenue": 1000000, "operating_profit": 120000 }
  ],
  "sources": [ { "view_name": "vw_finance_quarterly_summary" } ],
  "metadata": { "generated_sql": "SELECT ...", "row_count": 1 }
}
```

### 조회 제한 (SQL Guard 공통 정책 적용)

- 허용 View: `database/policy/finance_allowed_views.yaml`에 선언한 목록
- `SELECT` 문만 허용, 결과 최대 100건.
- SQL Guard는 공통 모듈(`mcp_servers/data_tools/sql_guard.py`)에서 검증하며, 허용 View 목록만 `database/policy/`의 도메인별 정책 파일에서 관리한다.

## Tool 3: 판매 데이터 조회

- Tool 이름: `query_sales`
- 제공 서버: Data MCP Server (판매 모듈)
- 담당: 판매 데이터 담당자
- 구현 경로: `mcp_servers/data_tools/sales/`

### 입력

```json
{ "question": "2025년 1분기 상품별 매출을 알려줘" }
```

### 성공 응답

```json
{
  "status": "success",
  "domain": "sales",
  "message": null,
  "data": [ { "product_name": "상품A", "sales_amount": 500000, "quantity": 120 } ],
  "sources": [ { "view_name": "vw_sales_product_summary" } ],
  "metadata": { "generated_sql": "SELECT ...", "row_count": 1 }
}
```

### 조회 제한

- 허용 View: `database/policy/sales_allowed_views.yaml`에 선언한 목록
- `SELECT` 문만 허용, 결과 최대 100건.
- SQL Guard는 재무와 동일한 공통 모듈을 사용한다.

## 라우팅 규칙과 BOTH 병합

| 질문 유형 | 호출 Tool | 병합 방식 |
|---|---|---|
| 문서 질문 | `search_documents` | 단일 결과 사용 |
| 재무 질문 | `query_finance` | 단일 결과 사용 |
| 판매 질문 | `query_sales` | 단일 결과 사용 |
| BOTH (문서+수치) | 관련 Tool 병렬 호출(fan-out) | 아래 병합 규칙 적용(fan-in) |
| 외부 일반 지식 | 없음 | LLM 단독 응답, 출처 없음 명시 |

### BOTH fan-out/fan-in 규칙

1. Router가 `BOTH`로 분류하면 필요한 Tool들을 병렬로 호출한다.
2. 각 Tool 응답은 `domain`을 유지한 채 하나의 리스트(`evidence_pool`)로 모은다.
3. 한 Tool이 실패(`status="error"`)해도 다른 Tool 결과가 있으면 부분 응답으로 진행한다.
4. 모든 Tool이 실패하면 최종 응답은 `error_code="NO_RESULT"`로 반환한다.
5. `evidence_pool`은 evidence_eval에 그대로 전달되어 도메인별로 개별 검증한다.
6. 최종 답변에는 사용된 모든 도메인의 `sources`를 도메인별로 구분해 표시한다.

```json
{
  "status": "success",
  "domain": "both",
  "data": {
    "document": [ { "content": "...", "score": 0.8 } ],
    "sales": [ { "product_name": "상품A", "sales_amount": 500000 } ]
  },
  "sources": {
    "document": [ { "document_id": "sales_policy_002" } ],
    "sales": [ { "view_name": "vw_sales_product_summary" } ]
  },
  "metadata": { "merged_domains": ["document", "sales"] }
}
```

## evidence_eval 계약

- 담당: 통합 담당자(로직) + 각 도메인 담당자(판정 기준 검토)
- 위치: MCP Tool 호출과 답변 합성 사이의 LangGraph 노드
- 입력: Tool 응답의 `data`, `sources`, 원본 질문
- 출력:

```json
{
  "evidence_status": "SUPPORTED | PARTIALLY_SUPPORTED | INSUFFICIENT | CONTRADICTED",
  "reason": "관련성 낮음 | 근거 부족 | 상충하는 근거",
  "filtered_evidence": []
}
```

- `evidence_status="INSUFFICIENT"`이면 재검색(최대 1회) 또는 `error_code="EVIDENCE_INSUFFICIENT"` 응답으로 전환한다.
- 판정 기준: 검색 점수 임계값과 같은 규칙 기반 필터를 우선 적용하고, 애매한 경우에만 경량 LLM 판정을 추가한다.

## 변경 규칙

- Tool 이름, 공통 응답 필드, BOTH 병합 형식 변경은 통합 담당자 승인 후 적용한다.
- 허용 View 추가·변경은 도메인 담당자가 제안하고, SQL Guard 공통 로직은 통합 담당자가 반영한다.
- 인덱스 버전 스키마 변경은 RAG 담당자와 통합 담당자가 함께 검토한다.

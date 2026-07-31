# 아키텍처와 코드 경계

## 목적

이 문서는 README의 구현 명세와 `ownership.md`의 소유권 규칙을 실제 디렉터리 구조에
연결한다. 애플리케이션은 문서와 MySQL에 직접 접근하지 않고 MCP 경계를 통해서만 읽는다.
ETL은 챗봇 요청 경로와 분리된 배치 작업이다.

## 요청 흐름

```text
Static Web UI
  -> FastAPI /api/chat
  -> app/cache/ (cache hit이면 즉시 응답)
  -> app/agent/ (route 결정)
      -> app/mcp/client.py
          -> Document MCP: mcp_servers/document_tools/
          -> Data MCP: mcp_servers/data_tools/{finance,sales}/
  -> app/agent/evidence_eval.py
  -> answer synthesis
  -> app/cache/ (안전한 응답만 저장)
```

`GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH`는 `app/agent/state.py`의 허용 route다.
`BOTH`에서는 문서 근거와 업무 데이터 근거를 별도 상태 필드에 보존한 뒤 근거 평가에서
합친다.

## 소유권 기반 배치

| 경로 | 책임 | 접근 경계 |
|---|---|---|
| `app/`, `app/cache/`, `app/logging/` | 통합 담당 | FastAPI·그래프·캐시·공통 로그만 소유 |
| `ingestion/`, `mcp_servers/document_tools/` | RAG 담당 | FAISS 읽기/인덱싱, 원문 수정 금지 |
| `mcp_servers/data_tools/server.py`, `sql_guard.py` | 통합 담당 | Tool 등록과 SELECT 전용 공통 검증 |
| `mcp_servers/data_tools/finance/`, `etl/finance/`, `database/finance/` | 재무 담당 | 재무 View 조회와 재무 ETL |
| `mcp_servers/data_tools/sales/`, `etl/sales/`, `database/sales/` | 판매 담당 | 판매 View 조회와 판매 ETL |
| `database/policy/` | 각 도메인 담당 | 허용 View 목록만 변경; Guard 로직은 변경 금지 |

`logs/app.log.txt`, `logs/etl_finance.log.txt`, `logs/etl_sales.log.txt`는 런타임 임시 로그
경로이며 Git에서는 제외한다.

## 현재 구현 단계

현재는 구조 정렬과 단위 검증을 위한 스켈레톤 단계다. 라우팅, 메모리 캐시, 캐시 키,
헬스 체크, 최소 ACL 및 쓰기 SQL 차단은 구현돼 있다. 실제 LangGraph 조립, MCP transport,
FAISS/MySQL 연결, 도메인별 Text2SQL·ETL, evidence_eval은 후속 단계다. 상세 계약은
`interface.md`, 현재·목표 테스트 구분은 `test-scenarios.md`를 따른다.

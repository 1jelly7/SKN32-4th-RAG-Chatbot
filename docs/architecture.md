# 아키텍처와 코드 경계

## 목적

이 문서는 README의 구현 명세와 `ownership.md`의 소유권 규칙을 실제 디렉터리 구조에
연결한다. 애플리케이션은 문서 파일과 업무 DB에 직접 접근하지 않고 MCP 경계를 사용한다.
ETL은 챗봇 요청 경로와 분리된 배치 작업이다.

## 요청 흐름

```text
Static Web UI
  -> FastAPI /api/chat
  -> app/cache/ (cache hit이면 즉시 응답)
  -> app/agent/ (route 결정)
      -> app/mcp/client.py
          -> Document MCP
              -> 내부 문서 DB에서 file_path 조회
              -> 조회된 경로의 파일 로드
              -> FAISS RAG
          -> Data MCP: mcp_servers/data_tools/{finance,sales}/
  -> app/agent/evidence_eval.py
  -> answer synthesis
  -> app/cache/ (검증된 응답만 저장)
```

`GENERAL`, `DOCUMENT`, `DATABASE`, `BOTH`는 `app/agent/state.py`의 허용 route다.
`BOTH`에서는 문서 근거와 업무 데이터 근거를 별도 상태 필드에 보존한 뒤 근거 평가에서
합친다.

## 문서 획득 경계

Document MCP는 문서 본문을 DB에서 직접 받지 않는다.

1. `document_db.py`가 질문과 관련된 `document_id`, `title`, `file_path`, `updated_at`을
   내부 문서 DB에서 조회한다.
2. `file_loader.py`가 조회된 경로의 PDF/TXT/Markdown 파일을 읽는다.
3. `rag.py`가 해당 문서만 대상으로 검색한다.
4. 내부 `file_path`는 처리용 metadata로 보존하고 사용자 응답에는 노출하지 않는다.

## 소유권 기반 배치

| 경로 | 책임 | 접근 경계 |
|---|---|---|
| `app/`, `app/cache/`, `app/logging/` | 통합 담당 | FastAPI·그래프·캐시·공통 로그 |
| `ingestion/`, `mcp_servers/document_tools/` | RAG 담당 | 문서 DB 경로 조회·파일 로드·FAISS |
| `mcp_servers/data_tools/server.py` | 통합 담당 | Tool 등록과 도메인 전달 |
| `mcp_servers/data_tools/finance/`, `etl/finance/`, `database/finance/` | 재무 담당 | 재무 조회와 재무 ETL |
| `mcp_servers/data_tools/sales/`, `etl/sales/`, `database/sales/` | 판매 담당 | 판매 조회와 판매 ETL |

`logs/app.log.txt`, `logs/rag.log.txt`, `logs/etl_finance.log.txt`,
`logs/etl_sales.log.txt`는 런타임 임시 로그 경로이며 Git에서는 제외한다.

## 현재 구현 단계

현재는 구조 정렬과 단위 검증을 위한 스켈레톤 단계다. 라우팅, 메모리 캐시, 캐시 키,
헬스 체크, 문서 DB 경로 조회 순서와 도메인 dispatch 경계는 구현돼 있다. 실제 LangGraph
조립, MCP transport, 문서 DB·FAISS·업무 DB 연결, 도메인별 Text2SQL·ETL,
evidence_eval은 후속 단계다. 상세 계약은 `interface.md`, 현재·목표 테스트 구분은
`test-scenarios.md`를 따른다.

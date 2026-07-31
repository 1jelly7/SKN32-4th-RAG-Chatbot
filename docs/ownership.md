# 코드 소유권 및 변경 규칙

## 역할 정의

| 역할 | 담당자 | 책임 |
|---|---|---|
| 통합 담당 | 팀원 A | FastAPI, LangGraph, MCP Client, 캐시, evidence_eval, SQL Guard 공통 로직, 공통 로그 기록 진입점 |
| RAG 담당 | 팀원 B | 문서 전처리, 청킹, 임베딩, FAISS, 인덱스 버전 관리, Document MCP |
| 재무 담당 | 팀원 C | 재무 ETL, 재무 테이블·View, 재무 허용 View 정책, ETL 실행 이력, 재무 로그 포맷 정의 |
| 판매 담당 | 팀원 D | 판매 ETL, 판매 테이블·View, 판매 허용 View 정책, ETL 실행 이력, 판매 로그 포맷 정의 |

> 실제 팀원 이름이 정해지면 팀원 A~D를 GitHub ID로 교체한다.

## 디렉터리 구조 (로그 반영 수정본)

```text
skn32_3rd_pj_rag_mcp_chatbot/
├── app/
│   ├── main.py                           # 통합 담당
│   ├── api/                              # 통합 담당
│   ├── agent/
│   │   ├── graph.py                      # 통합 담당 (Router, BOTH fan-out/fan-in)
│   │   ├── nodes.py                      # 통합 담당
│   │   └── evidence_eval.py              # 통합 담당(로직) + 도메인 담당(기준 검토)
│   ├── mcp/
│   │   └── client.py                     # 통합 담당
│   ├── cache/                            # 통합 담당 (Graph 진입 전 단일 책임)
│   └── logging/
│       ├── logger.py                     # 통합 담당 (공통 로그 기록 인터페이스)
│       └── formatter.py                  # 통합 담당 (로그 포맷 통일)
│
├── ingestion/                            # RAG 담당 (문서 → FAISS, index_version 갱신)
├── mcp_servers/
│   ├── document_tools/                   # RAG 담당
│   └── data_tools/
│       ├── server.py                     # 통합 담당 (Tool 등록)
│       ├── sql_guard.py                  # 통합 담당 (공통 SQL 검증 로직)
│       ├── finance/                      # 재무 담당 (query_finance 구현)
│       └── sales/                        # 판매 담당 (query_sales 구현)
│
├── etl/
│   ├── finance/                          # 재무 담당 (ETL, UPSERT, 실행 이력)
│   └── sales/                            # 판매 담당 (ETL, UPSERT, 실행 이력)
│
├── database/
│   ├── policy/
│   │   ├── finance_allowed_views.yaml    # 재무 담당 작성, 통합 담당 검토
│   │   └── sales_allowed_views.yaml      # 판매 담당 작성, 통합 담당 검토
│   ├── finance/                          # 재무 담당 (테이블·View DDL, 용어집)
│   └── sales/                            # 판매 담당 (테이블·View DDL, 용어집)
│
├── logs/
│   ├── app.log.txt                       # 통합 흐름 런타임 로그(추적 제외)
│   ├── etl_finance.log.txt               # 재무 ETL 런타임 로그(추적 제외)
│   └── etl_sales.log.txt                 # 판매 ETL 런타임 로그(추적 제외)
│
├── tests/                                # 기능별 담당자 + 통합 담당
├── requirements.txt                      # 통합 담당
├── .env.example                          # 통합 담당
├── .gitignore                            # 통합 담당
└── docs/                                 # 문서별 오너
```

> 장기적으로는 애플리케이션 로그와 ETL 실행 로그를 DB 테이블에 저장한다. 현재 부트캠프 단계에서는 우선 `logs/*.txt` 파일에 임시 저장하고, 이후 DB 로깅 모듈로 교체한다.

## 현재 구현 단계와 디렉터리 규칙

- `app/core/`에는 환경 설정과 사용자 컨텍스트만 둔다. 공통 로그는 `app/logging/`만
  사용한다.
- `app/agent/evidence_eval.py`는 노드에서 분리돼 있으나, 실제 판정 로직은 아직
  스켈레톤이다.
- 재무의 기존 공통 ETL 스켈레톤은 `etl/finance/`로 이동했다. `etl/sales/`는 판매
  소유의 독립 스켈레톤으로 새로 만들었다. 두 디렉터리는 서로의 테이블·적재 규칙을
  직접 import하거나 수정하지 않는다.
- `mcp_servers/data_tools/finance/`와 `sales/`는 도메인별 `query_*`, `schema.py`,
  `text2sql.py`, `mysql.py`를 소유한다. `server.py`와 `sql_guard.py`만 공통 영역이다.
- `database/policy/*.yaml`은 빈 허용 목록으로 시작한다. 실제 View를 추가할 때는
  해당 도메인 담당자가 정책·DDL·테스트를 함께 변경하고 통합 담당자가 Guard 연동을
  검토한다.
- 로그 파일은 생성 산출물이므로 `.gitignore`의 `logs/*.log.txt` 규칙으로 제외하며,
  디렉터리 자체는 `logs/.gitkeep`으로 유지한다.

## 로그 저장 정책

| 항목 | 현재 방식 | 향후 방식 | 책임자 |
|---|---|---|---|
| API/Agent 실행 로그 | `logs/app.log.txt` | DB 로그 테이블 | 통합 담당 |
| 재무 ETL 실행 로그 | `logs/etl_finance.log.txt` | DB 로그 테이블 | 재무 담당 |
| 판매 ETL 실행 로그 | `logs/etl_sales.log.txt` | DB 로그 테이블 | 판매 담당 |
| 에러 로그 | 각 txt 파일에 동일 포맷 기록 | DB 로그 테이블 + 알림 | 해당 기능 담당 + 통합 담당 |

### 로그 포맷 원칙

- 한 줄 1이벤트 원칙을 사용한다.
- 최소 필드: `timestamp`, `level`, `module`, `event`, `message`
- 가능하면 JSON Lines 형식 또는 구분자 고정 텍스트 형식을 사용한다.
- 예시:

```text
2026-07-31T11:00:00+09:00 | INFO | app.agent.graph | route_selected | domain=sales
2026-07-31T11:00:05+09:00 | ERROR | etl.finance.load | upsert_failed | row_id=1042 reason=duplicate key
```

- DB 저장으로 전환할 때도 같은 필드를 유지해 마이그레이션 비용을 줄인다.

## 디렉터리 소유권 표

| 영역 | 코드 오너 | 협의 대상 | 변경 원칙 |
|---|---|---|---|
| `app/main.py`, `app/api/` | 통합 담당 | 전체 | 진입점은 통합 담당자만 최종 병합 |
| `app/agent/graph.py` | 통합 담당 | RAG·재무·판매 | Tool 계약 확정 후 변경, BOTH 병합 로직 포함 |
| `app/agent/evidence_eval.py` | 통합 담당 | RAG·재무·판매 | 판정 기준은 도메인 담당자와 협의 |
| `app/mcp/client.py` | 통합 담당 | RAG·재무·판매 | Tool 호출 공통 모듈 |
| `app/cache/` | 통합 담당 | 전체 | 캐시 키·TTL·무효화 정책의 유일한 소유자 |
| `app/logging/` | 통합 담당 | 전체 | txt 로그 기록 인터페이스와 포맷의 유일한 소유자 |
| `ingestion/` | RAG 담당 | 통합 담당 | 인덱스 버전·manifest 갱신 책임 포함 |
| `mcp_servers/document_tools/` | RAG 담당 | 통합 담당 | `search_documents` 계약 준수 |
| `mcp_servers/data_tools/server.py` | 통합 담당 | 재무·판매 | Tool 등록과 공통 실행만 담당 |
| `mcp_servers/data_tools/sql_guard.py` | 통합 담당 | 재무·판매 | SELECT 전용 검증, 허용 View 로딩 로직 |
| `mcp_servers/data_tools/finance/` | 재무 담당 | 통합 담당 | `query_finance` 구현 |
| `mcp_servers/data_tools/sales/` | 판매 담당 | 통합 담당 | `query_sales` 구현 |
| `etl/finance/` | 재무 담당 | 통합 담당 | UPSERT 및 실행 이력 관리 책임 포함 |
| `etl/sales/` | 판매 담당 | 통합 담당 | UPSERT 및 실행 이력 관리 책임 포함 |
| `database/policy/` | 도메인 담당(각자) | 통합 담당 | 허용 View 목록만 관리, SQL Guard 로직은 수정 불가 |
| `database/finance/`, `database/sales/` | 도메인 담당(각자) | 통합 담당 | 테이블·View DDL, 용어집 |
| `logs/app.log.txt` | 통합 담당 | 전체 | 공통 실행 로그 저장 |
| `logs/etl_finance.log.txt` | 재무 담당 | 통합 담당 | 재무 ETL 로그 저장 |
| `logs/etl_sales.log.txt` | 판매 담당 | 통합 담당 | 판매 ETL 로그 저장 |
| `tests/` | 기능별 담당자 | 통합 담당 | 담당 기능 테스트를 함께 작성 |
| `requirements.txt`, `.env.example`, `.gitignore` | 통합 담당 | 전체 | 변경 전 팀 공유 |

## 공통 영역 변경 절차

1. 변경 제안자가 Issue에 변경 이유와 영향을 작성한다.
2. 인터페이스·병합 로직·로그 포맷 변경이면 관련 문서를 먼저 수정한다.
3. 공통 코드 오너(통합 담당)가 방향을 승인한다.
4. 기능 브랜치에서 구현 후 PR을 생성한다.
5. 코드 오너가 최종 병합한다.

## 데이터, 인덱스, 로그 책임

| 항목 | 책임자 | 세부 내용 |
|---|---|---|
| FAISS 인덱스 버전 | RAG 담당 | 재인덱싱 시 `manifest.json`의 `index_version` 증가 |
| ETL 멱등성 | 재무·판매 담당 | 동일 원천 재실행 시 UPSERT로 중복 방지 |
| ETL 실행 이력 | 재무·판매 담당 | 실행 시각, 처리 행 수, 검증 결과를 로그 파일에 기록 |
| SQL Guard 로직 | 통합 담당 | SELECT 전용 검증, 허용 View 외 차단 |
| 허용 View 목록 | 도메인 담당(각자) | `database/policy/*.yaml` 갱신 |
| 캐시 무효화 트리거 | 통합 담당 + 도메인 담당 | 재인덱싱·ETL 적재 완료 시 관련 캐시 삭제 요청 |
| `.gitignore` 관리 | 통합 담당 | 가상환경, 캐시, 로컬 설정, 산출물 제외 규칙 유지 |
| 로그 저장소 전환 | 통합 담당 + 각 도메인 담당 | txt 저장 방식을 이후 DB 저장으로 마이그레이션 |

## 브랜치 권한 및 규칙

| 목적 | 브랜치 예시 |
|---------------|----------------|
| 재무 ETL·Text2SQL | `rag_finance` |
| 판매 ETL·Text2SQL | `rag_sales` |
| 문서 검색 | `rag` |
| MCP | `backend` |
| 백엔드 통합 | `develop` |

- `main` 브랜치에는 직접 push하지 않는다.
- 기능 구현은 위 브랜치 중 해당 목적 브랜치에서 진행하고, 최종 병합은 `develop`을 거쳐 `main`으로 반영한다.
- 공통 코드 변경 PR에는 관련 담당자를 리뷰어로 지정한다.
- 충돌 해결이 필요한 경우, 해당 파일의 코드 오너가 최종 방향을 결정한다.

## 권한 경계

| 경로 | DB 권한 | 금지 사항 |
|---|---|---|
| `etl/finance/`, `etl/sales/` | INSERT, UPDATE, UPSERT | 챗봇 API에서 호출 금지 |
| `mcp_servers/data_tools/` | SELECT 전용 | INSERT, UPDATE, DELETE, DDL 금지 |
| `app/agent/` | DB 직접 접근 없음 | SQL 직접 실행 금지 |
| `app/logging/` | 현재 파일 쓰기만 허용 | 임의 DB 쓰기 금지, DB 로그 전환 전까지 txt만 사용 |
| `mcp_servers/document_tools/` | FAISS 읽기 | 원문 파일 수정 금지 |

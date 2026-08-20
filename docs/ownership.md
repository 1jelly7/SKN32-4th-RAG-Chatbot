# 코드 소유권 및 변경 규칙

## 목적

이 문서는 [README](../README.md)의 팀 역할을 실제 디렉터리와 변경 협의
절차에 연결한다. 소유자는 혼자만 수정할 수 있다는 뜻이 아니라, 계약 변경의 최종 검토와
관련 산출물 동기화를 책임진다는 뜻이다.

## 역할 정의

| 담당 | 프로젝트 역할 | 주 책임 |
|---|---|---|
| 문동원 | PM · RAG Sales | 일정·통합 조율, 판매 데이터·ETL·Text2SQL, 판매 증강 데이터 검토 |
| 박회종 | Backend | Django UI·계정·인증, FastAPI 인증 확인/RBAC, LangGraph, MCP Client, 캐시, 공통 API·로그 통합 |
| 이태혁 | RAG PDF | 문서 등록, 로더·청킹·임베딩, FAISS, 문서 DB 경로, Document Tool |
| 이호원 | RAG Purchasing | 구매 데이터·ETL·Text2SQL, 구매 증강 데이터 검토 |

GitHub 리뷰어 자동 지정이 필요하면 위 실명을 각자의 GitHub ID로 매핑해 별도
`CODEOWNERS` 도입을 검토한다. 현재 저장소에는 `CODEOWNERS`가 없으므로 이 문서가 협의
기준이다.

## 디렉터리와 책임

```text
skn32_3rd_pj_rag_mcp_chatbot/
├── app/
│   ├── main.py, api/, schemas/          # Backend
│   ├── auth/                            # Backend (Django 인증 확인 gateway, legacy 롤백 코드)
│   ├── agent/                           # Backend + 근거 기준은 각 도메인 협의
│   ├── mcp/                             # Backend
│   ├── cache/                           # Backend
│   ├── core/                            # Backend
│   ├── logging/                         # Backend
│   └── web/vendor/                      # Backend (UI 전환 기간 Chart.js 호환 source)
├── django_app/                           # Backend (UI·계정·인증·Admin·migration)
├── shared/                               # Backend (프레임워크 독립 권한 계약)
├── ingestion/                           # RAG PDF
├── mcp_servers/
│   ├── document_tools/                  # RAG PDF
│   └── data_tools/
│       ├── server.py                    # Backend
│       ├── purchase/                    # RAG Purchasing
│       └── sales/                       # RAG Sales
├── etl/
│   ├── purchase/                        # RAG Purchasing
│   └── sales/                           # RAG Sales
├── database/
│   ├── account/                         # Backend
│   ├── document/                        # RAG PDF + Backend 협의
│   ├── purchase/                        # RAG Purchasing
│   └── sales/                           # RAG Sales
├── scripts/                             # 스크립트 기능의 도메인 소유자
├── tests/                               # 기능 소유자 작성, Backend 계약 검토
├── docs/                                # 아래 문서 소유권 표 참조
├── data/raw/                            # 로컬 원천; Git 제외
├── data/faiss/                          # 생성 인덱스; Git 제외
├── logs/                                # 런타임 로그; Git 제외
├── requirements.txt                    # Backend, 팀 공유 필수
├── .env.example                        # Backend, 공개 설정 계약
└── .gitignore                          # Backend
```

## 영역별 소유권

| 영역 | 주 소유자 | 필수 협의 대상 | 변경 원칙 |
|---|---|---|---|
| `app/main.py`, `app/api/`, `app/schemas/` | 박회종 | 영향 도메인 | HTTP 필드·상태·오류 매핑과 테스트 동기화 |
| `django_app/accounts/`, `database/account/` | 박회종 | 전체 | 계정·세션·migration 변경 시 API/이관 테스트 갱신 |
| `django_app/web/` | 박회종 | API/도메인 담당 | Django template·static namespace와 ChatResponse 계약 유지 |
| `app/auth/`, `shared/auth_policy.py` | 박회종 | 전체 | 인증 확인·역할·DB 권한 변경 시 API/MCP 테스트 갱신 |
| `app/agent/graph.py`, `nodes.py`, `state.py` | 박회종 | 문동원·이태혁·이호원 | route, BOTH 병렬 합류, DB 하위 도메인 순서와 evidence 계약 보존 |
| `app/agent/evidence_eval.py` | 박회종 | 세 도메인 담당 | 판정 임계값·필수 metadata를 도메인별 검토 |
| `app/mcp/client.py`, `mcp_servers/data_tools/server.py` | 박회종 | 관련 Tool 소유자 | Tool 이름·payload·envelope의 Host 정본 |
| `app/cache/` | 박회종 | 전체 | 키 재료·TTL·무효화의 유일한 앱 경계 |
| `app/core/`, `.env.example` | 박회종 | 전체 | 설정 필드 추가·삭제를 함께 반영, 비밀값 금지 |
| `app/logging/` | 박회종 | 전체 | API/Agent 로그 인터페이스와 민감정보 제거 |
| `app/web/vendor/` | 박회종 | 없음 | 전환 기간 vendor 호환 source만 유지하고 검증 후 Django 정본으로 이동 |
| `ingestion/` | 이태혁 | 박회종 | 로더·청킹·임베딩·인덱스 버전 책임 |
| `mcp_servers/document_tools/` | 이태혁 | 박회종 | 활성 문서 ID 허용 목록, FAISS 검색, 경로 미노출 |
| `database/document/` | 이태혁 | 박회종 | `document_paths`와 다운로드 ID 매핑 동기화 |
| `mcp_servers/data_tools/purchase/` | 이호원 | 박회종 | `query_purchase`, 구매 schema·SQL guard |
| `etl/purchase/`, `database/purchase/` | 이호원 | 박회종 | 구매 적재·DDL·View·read-only grant |
| `mcp_servers/data_tools/sales/` | 문동원 | 박회종 | `query_sales`, 판매 schema·SQL guard |
| `etl/sales/`, `database/sales/` | 문동원 | 박회종 | 판매 적재·DDL·View·read-only grant |
| `requirements.txt`, `.gitignore` | 박회종 | 전체 | 재현성·제외 범위 변경 전 팀 공유 |

## scripts 소유권

| 경로 | 소유자 | 주의점 |
|---|---|---|
| `scripts/register_documents.py`, `ingest_documents.py`, `rebuild_faiss_index.py` | 이태혁 | 문서 DB와 FAISS version을 함께 검증 |
| `scripts/generate_sales_synthetic_data.py` | 문동원 | 원천 보존, 고정 seed, 합성 데이터 표시 유지 |
| 구매 적재·View 보조 스크립트 | 이호원 | `etl/purchase/`와 중복 계약을 만들지 않음 |
| 판매 적재 보조 스크립트 | 문동원 | `etl/sales/`를 정본으로 유지 |
| `django_app/manage.py`, 계정 migration | 박회종 | 관리자 생성과 기존 계정 이관 시 평문·해시 로그 금지 |
| `scripts/seed_accounts.py` | 박회종 | legacy rollback 전용; 활성 Django 계정 관리에 사용 금지 |
| 평가·성능 스크립트 | 박회종 | fixture·공개 응답만 기록하고 질문 원문·근거·비밀값 로그 금지 |

현재 통합 `scripts/setup_all.py`는 존재하지 않는다. 새 통합 초기화 도구를 만들려면
Backend 단독으로 DB·경로를 추정하지 말고 문서, 구매, 판매 담당자가 각 단계의 명령,
멱등성, 권한과 실패 복구를 함께 검토한다.

## 접근 경계

| 경로 | 허용 | 금지 |
|---|---|---|
| `app/api/`, `app/agent/` | MCP Client 호출 | MySQL·FAISS·원문 직접 접근, SQL 직접 실행 |
| `django_app/` | account DB ORM·migration, Django 세션 | 업무 DB·FAISS·MCP 직접 접근 |
| `shared/auth_policy.py` | Document/Purchase/Sales Tool 접근 역할 정의 | Django 전용 `account_db`를 허용 업무 DB로 노출 |
| `mcp_servers/document_tools/` | 활성 문서 metadata 조회, FAISS 읽기, 승인된 다운로드 해석 | 임의 경로 접근, 원문 수정, 경로 공개 |
| `mcp_servers/data_tools/` | 허용 View의 단일 SELECT/WITH | 쓰기 SQL, DDL, ETL 호출 |
| `etl/purchase/`, `etl/sales/` | 검증 후 INSERT/UPDATE/UPSERT | API 요청 경로에서 실행 |
| `app/cache/` | 최종 답변 cache get/set/delete | Graph 노드에서 저장소 직접 접근 |
| `app/logging/` | 비밀값 없는 파일 로그 | 질문 원문, 전체 근거, API key, 비밀번호, 내부 경로 기록 |

`LEGACY_AUTH_ROLLBACK_WINDOW=true`인 동안 `django_app/accounts/admin.py`는 계정 추가·삭제와
이관 계정 변경을 막는다. 이 잠금을 해제하거나 legacy 인증 소스를 제거하는 변경은
rollback 종료 결정, 계정 DB 백업·감사 결과와 함께 Backend/통합 담당이 검토한다.

## 생성물과 원천 데이터

| 항목 | 책임 | 규칙 |
|---|---|---|
| `data/raw/**` | 각 데이터 도메인 | 원천·증강 데이터 로컬 보관, 수정·커밋 금지 |
| `data/faiss/**` | 이태혁 | 인덱싱 스크립트로만 재생성, 수동 편집·커밋 금지 |
| `database/sales/ddl.sql` | 문동원 | `python -m etl.sales.ddl`로 재생성 |
| `logs/app.log.txt` | 박회종 | 런타임 생성, Git 제외 |
| `logs/etl_purchase.log.txt` | 이호원 | ETL 실행 시 생성, Git 제외 |
| `logs/etl_sales.log.txt` | 문동원 | ETL 실행 시 생성, Git 제외 |

`logs/rag.log.txt`는 README와 과거 설계에서 계획한 경로지만 현재 RAG 코드에는 전용 파일
handler가 연결돼 있지 않다. 구현 전까지 존재하는 로그처럼 완료 보고하지 않는다.

## 로그 계약

API/Agent는 Python logging을 통해 `logs/app.log.txt`에 기록한다. 구매·판매 pipeline은
각 ETL 로그 파일에 구분자 텍스트를 추가한다.

- 한 줄 1이벤트를 지향한다.
- 공통 formatter의 최소 필드는 `timestamp`, `level`, `module`, `event`, `message`다.
- 요청 식별자는 허용하지만 질문 원문, 전체 evidence, 세션 token, DB 자격증명은 기록하지 않는다.
- DB 로깅은 현재 구현되지 않았으며 파일 로그를 임의 DB 쓰기로 교체하지 않는다.

## 데이터·인덱스·캐시 책임

| 항목 | 책임자 | 완료 조건 |
|---|---|---|
| 문서 등록 경로 | 이태혁 | DB의 활성 ID와 실제 원천 파일 일치 |
| FAISS 인덱스 버전 | 이태혁 | 재인덱싱 산출물 metadata와 검색 응답 일치 |
| 구매 ETL 멱등성·검증 | 이호원 | transform/validate 통과 후 UPSERT |
| 판매 ETL 멱등성·검증 | 문동원 | transform/validate 통과 후 UPSERT |
| LLM 증강 데이터 검토 | 문동원·이호원 | 원천과 분리, PK/참조/타입/계산/중복 검증 |
| cache key·TTL | 박회종 | 사용자·버전 격리 테스트 통과 |
| ETL 후 cache 무효화 | 박회종 + 도메인 담당 | 현재 미구현; 구현 시 freshness 공급과 테스트 필요 |

LLM으로 생성·설계한 구매·판매 합성 데이터는 교육·테스트용 파생 데이터다. 원천 데이터
이용 조건을 대체하지 않으며 실제 기업 실적으로 해석하지 않는다.

## 문서 소유권

| 문서 | 주 소유자 | 검토자 |
|---|---|---|
| `docs/architecture.md` | 박회종 | 전체 도메인 담당 |
| `docs/interface.md` | 박회종 | Tool 소유자 |
| `docs/ownership.md` | 문동원(PM) | 전체 |
| `docs/test-scenarios.md` | 박회종 | 기능별 테스트 소유자 |
| `../README.md` | 문동원(PM) | 전체 |

## 공통 영역 변경 절차

1. 변경 제안자가 변경 이유, 영향 경로, 계약 호환성을 Issue 또는 PR에 기록한다.
2. `architecture`, `interface`, `ownership`, `test-scenarios` 중 영향 문서를 먼저 또는 같은
   변경 묶음에서 갱신한다.
3. 주 소유자와 필수 협의 대상이 route, envelope, schema, 보안 경계를 검토한다.
4. 기능 코드와 결정적 unit/fake integration 테스트를 함께 수정한다.
5. `git diff --check`, 관련 테스트, 가능하면 전체 테스트 결과를 확인한다.
6. 주 소유자가 최종 병합한다.

## 브랜치와 병합

저장소에는 `main`, `develop`, `backend`, `feat/backend-integration-foundation` 계열 브랜치가
확인된다. 과거 역할 브랜치 이름만을 영구 규칙으로 고정하지 않고 다음 원칙을 적용한다.

- `main`에 직접 push하지 않는다.
- 기능 브랜치는 목적이 드러나는 이름을 사용하고 PR로 `develop`에 병합한다.
- 공통 계약 변경은 관련 도메인 소유자를 리뷰어로 지정한다.
- `develop` 검증 후 릴리스 단위로 `main`에 반영한다.
- 충돌은 해당 파일 주 소유자가 관련 담당자와 계약을 확인한 뒤 해결한다.

## 보존해야 할 계약 문서

`docs/architecture.md`, `docs/interface.md`, `docs/ownership.md`,
`docs/test-scenarios.md`는 구현과 함께 유지해야 하는 정본 문서다. 코드와 충돌하면 문서만
낙관적으로 바꾸지 말고 실제 구현·테스트 상태를 `구현됨`, `선택 실행`, `미구현`으로
구분한다.

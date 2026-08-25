# Project Progress

> Last updated: 2026-08-21 (문서 질의 startup 장애 복구) KST
> Source logs: `docs/progress/<role>/YYYY-MM-DD.md`

## Current Verified State

- Django 인증·계정 서비스와 FastAPI 내부 인증 확인 gateway를 구현했다. 구현 직후 `.venv` 기준선은 전체 pytest 393 passed, 27 skipped였고, 후속 정적 검토 수정 뒤에는 사용자 요청에 따라 테스트를 재실행하지 않았다.
- 일반 지식 질의는 근거가 없다는 이유만으로 일괄 거절하지 않으며, 사내·최신성·고위험·인용 요구 질의는 검증 근거가 없을 때 안전 응답을 유지한다.
- 문서 DB 접근 오류는 내부 오류로 뭉개지지 않고 Document MCP의 `QUERY_ERROR`로 분류된다. 지원 등록 절차로 문서 DB 스키마와 등록 문서 경로를 확인했다.
- 로컬 문서 검색 점수에 맞춘 문서 전용 최소 점수 `0.12`를 적용했다. 대표 문서 질의의 실제 Chat API는 HTTP 200, `DOCUMENT`, `SUPPORTED`, source 1개와 비어 있지 않은 답변을 반환했다.
- `skn_3rd` 환경 전체 테스트는 127 passed, 2 skipped이며 `git diff --check`를 통과했다.
- 상세 근거와 변경 범위는 `docs/progress/integration/2026-08-02.md` Session 3에 기록했다.
- `법인카드 발급 규정` 질의의 간헐적 HTML 502 원인을 SBERT 예열 중 FastAPI startup 지연으로 특정하고, API 선기동·백그라운드 예열과 UI 비JSON 응답 방어를 적용했다. 상세 기록은 [`docs/progress/integration/2026-08-21.md`](docs/progress/integration/2026-08-21.md) Session 1에 있다.
- 로그인·세션 기반 RBAC가 Chat API와 MCP 데이터 도구 경계에 적용됐으며, 관리자 실제 브라우저 로그인·새로고침 세션 복원·로그아웃 UI 전환을 확인했다.
- `skn_3rd` 환경 전체 테스트는 134 passed, 2 skipped이며 `git diff --check`를 통과했다. 상세 기록은 `docs/progress/integration/2026-08-03.md` Session 2에 있다.
- 문서 Chat 출처는 청크 대신 원본 문서 단위 카드로 병합되며, 정렬·중복 제거된 페이지와 발췌문, 보호된 다운로드 URL을 반환한다. 상세 기록은 `docs/progress/integration/2026-08-04.md` Session 1에 있다.
- Sales `query_sales`는 뷰 5개, 조회 전용 계정, SQL 가드와 EXPLAIN 사전검증으로 강화됐고 실제 OpenAI·MySQL opt-in 테스트를 포함한 33개 검증을 통과했다.
- Purchase `query_purchase`는 DB·계정이 아예 없던 상태에서 시작해 ETL 재작성·실적재(25/50/123/32/32건, 멱등성 확인)·뷰 5개·조회 전용 계정·스키마 리소스·프롬프트를 sales와 동등하게 완성했고, 실제 OpenAI·MySQL opt-in 테스트 33건과 브라우저 수동 확인(finance 정상 응답, hr FORBIDDEN)을 통과했다. 이전에 "DB 계정 권한 문제"로 알려졌던 P0-3의 근본 원인이 실은 DB 부재였음이 밝혀졌다.

## Area Status

| Area | Status | Current State | Evidence / Latest Log | Blocker or Next Decision |
|---|---|---|---|---|
| Backend | In progress | Django가 계정·세션을 소유하고 FastAPI가 내부 인증 확인 결과만 사용하도록 분리했으며 정적 재검토 결함을 보정했다. | `docs/progress/integration/2026-08-20.md` Session 2 | 최신 수정 후 테스트와 실제 account DB 이관 감사가 남아 있다. |
| RAG | Partially verified | 문서 DB 등록·로컬 검색·대표 실제 API 흐름이 검증됐다. | `docs/progress/integration/2026-08-02.md` Session 3 | 라벨된 질의셋으로 최소 점수와 top-k 품질을 평가해야 한다. |
| Sales | Partially verified | `query_sales`에 뷰 화이트리스트, SQL 가드, EXPLAIN 사전검증과 1회 재시도를 적용했고 실제 OpenAI·MySQL opt-in 계약 테스트를 통과했다. | `docs/progress/sales/2026-08-02.md` | 원격 MCP transport와 채팅 차트 응답 계약의 end-to-end 검증이 남아 있다. |
| Purchase | Verified | `query_purchase`를 sales와 동등한 3중 방어(뷰·조회 전용 계정·SQL 가드) + 시맨틱 레이어 + EXPLAIN 자기수정 구조로 완성했다. DB·ETL·뷰·계정을 전부 새로 만들고 실제 데이터로 적재·검증했다. | `docs/progress/purchase/2026-08-03.md` | `docs/team_share/04_chart_spec.md`(sales와 공유) 통합 담당 구현 대기, `server.py` envelope 확장 요청 대기. |
| Integration | In progress | Django/FastAPI gateway 분리와 문서 질의 startup 장애 수정을 반영했다. | [`docs/progress/integration/2026-08-21.md`](docs/progress/integration/2026-08-21.md) Session 1 | 재시작 후 startup 직후 브라우저·gateway E2E와 원격 MCP 검증이 남아 있다. |

## Active Work

- [ ] `[backend/integration]` 실제 account DB에 Django migration을 적용하고 계정 감사를 실행한다.
- [ ] `[backend/integration]` 정적 재검토 수정 후 Django check, migration check와 전체 pytest를 재실행한다.
- [ ] `[integration]` startup 백그라운드 예열 수정 후 gateway 재시작 직후 문서 질문의 HTTP 200 및 출처 표시를 확인한다.
- [ ] `[integration]` `/api/auth/*`, `/admin/*`, `/django-static/*`과 FastAPI 경로 라우팅 및 rollback을 검증한다.
- [ ] `[rag/integration]` 라벨된 사내 문서 질의셋으로 문서 최소 점수 `0.12`와 top-k의 recall/precision을 측정한다.
- [ ] `[integration]` 원격 Document MCP transport와 독립 프로세스 E2E를 실행한다.
- [ ] `[integration]` Redis 및 문서 version/freshness 기반 캐시 무효화를 검증한다.
- [ ] `[backend/integration]` Sales/Purchase가 제공하는 `chart_hint`·`metadata`를 보존하는 Data MCP envelope와 채팅 그래프 렌더링을 통합·검증한다.
- [ ] `[backend/integration]` 운영 계정 저장소·원격 MCP·Redis를 연결한 opt-in RBAC E2E와 HTTPS 세션 쿠키 설정을 검증한다.

## Verified Milestones

- [x] 2026-08-02 일반 지식/검증 필요 질의의 답변 정책을 분리하고, 이전 프롬프트 응답 캐시를 버전 갱신으로 무효화했다.
- [x] 2026-08-02 문서 DB 오류·문서 등록·검색 점수 보정 문제를 단계적으로 분리해 대표 문서 RAG API를 HTTP 200 / `SUPPORTED`로 복구했다.
- [x] 2026-08-02 `skn_3rd` 환경에서 전체 pytest 127 passed, 2 skipped 및 `git diff --check` 통과를 확인했다.
- [x] 2026-08-03 로그인 UI·HttpOnly 세션·역할 기반 접근 제어를 적용하고, 실제 브라우저의 관리자 메인 화면 전환 문제를 수정했다.
- [x] 2026-08-03 `skn_3rd` 환경에서 전체 pytest 134 passed, 2 skipped 및 `git diff --check` 통과를 확인했다.
- [x] 2026-08-02 Sales Text2SQL을 뷰 기반 조회와 SQL 가드로 강화하고, 실제 OpenAI·MySQL opt-in 테스트 33건을 통과했다.
- [x] 2026-08-03 Purchase DB·ETL·뷰·조회 전용 계정을 처음부터 새로 만들고, `query_purchase` Text2SQL을 sales 수준으로 완성해 실제 OpenAI·MySQL opt-in 테스트 33건 + 브라우저 RBAC 확인을 통과했다.

## Key Decisions

| Date | Decision | Rationale | Trade-off / Follow-up | Source |
|---|---|---|---|---|
| 2026-08-02 | 안정적 일반 지식과 검증 근거가 필수인 질의를 분리한다. | 일반 질문의 불필요한 거절을 막으면서 사내·최신성·고위험 정보의 근거 요구를 보존한다. | 질의 분류 규칙은 실제 질의셋으로 계속 보정한다. | Session 3 |
| 2026-08-02 | 문서 검색 점수는 문서 전용 최소 점수 `0.12`로 평가한다. | 로컬 n-gram FAISS 점수 범위가 다른 evidence의 전역 기준과 다르다. | 라벨된 평가 데이터셋으로 임계값을 재조정한다. | Session 3 |
| 2026-08-02 | 문서 DB 외부 오류는 `QUERY_ERROR`로 보존한다. | 사용자에게 내부 세부 정보를 노출하지 않으면서 운영 원인을 구분한다. | 원격 MCP에서도 동일한 envelope 계약을 검증한다. | Session 3 |
| 2026-08-03 | 권한은 UI가 아닌 Chat API와 MCP 데이터 도구 양쪽에서 검증한다. | UI 경로 우회나 직접 MCP 호출에도 역할 범위를 보존한다. | 운영 저장소·원격 MCP를 포함한 E2E가 후속으로 필요하다. | `integration/2026-08-03.md` Session 2 |
| 2026-08-03 | 로그인 오버레이의 `hidden` 상태를 CSS에서 명시적으로 `display: none` 처리한다. | 레이아웃의 `display: grid`가 기본 숨김 동작을 덮어쓰는 실제 UI 장애를 방지한다. | 다른 오버레이에도 hidden 스타일 충돌 여부를 검토한다. | `integration/2026-08-03.md` Session 2 |
| 2026-08-02 | Sales Text2SQL은 원본 테이블 대신 의미 기반 뷰와 화이트리스트로 조회한다. | 도메인 컬럼·집계 정의를 일관되게 유지하고 임의 테이블 접근을 방지한다. | 원격 MCP 환경에서도 동일한 envelope와 권한 경계를 검증한다. | `docs/progress/sales/2026-08-02.md` |
| 2026-08-03 | Purchase 구매액은 Cancelled 상태만 제외한다(Approved 포함). | purchase에는 sales의 Draft에 해당하는 상태가 없고, Approved도 승인된 확정 구매로 본다(사용자 결정). | 취소 외 상태 해석이 바뀌면 뷰 정의를 다시 검토해야 한다. | `docs/progress/purchase/2026-08-03.md` |
| 2026-08-03 | Purchase는 EXPLAIN 전용 계정으로 공용 admin(JangGGo) 대신 도메인 전용 ETL 계정(PURCHASE_DB_*)을 쓴다. | JangGGo에는 purchase.* 권한이 없어(도메인별 계정 분리 설계) EXPLAIN이 Access denied로 실패했다. | sales와 계정 모델이 다르므로 향후 다른 도메인 추가 시 이 차이를 먼저 확인해야 한다. | `docs/progress/purchase/2026-08-03.md` |
| 2026-08-20 | 계정·세션은 Django가 소유하고 FastAPI는 내부 인증 확인 API만 호출한다. | 세션 DB·SECRET_KEY 공유 없이 로그아웃·비활성화·역할 변경을 즉시 반영한다. | 보호 요청당 내부 호출 지연과 Django 가용성 의존성이 추가된다. | `docs/progress/integration/2026-08-20.md` |
| 2026-08-20 | `account_db`는 Django에만 허용하고 Admin 정적 파일은 `/django-static/*`로 분리한다. | FastAPI/MCP 책임 누수와 `/static` 경로 충돌을 제거한다. | 최신 정적 수정 후 테스트와 실제 gateway 검증이 필요하다. | `docs/progress/integration/2026-08-20.md` Session 2 |

## Blockers and Open Questions

- **[Severity: High] [Backend/Integration] Django 인증 분리 실행 검증 보류**
  - 영향: 구현 직후 기준선은 통과했지만 정적 검토 수정 후 테스트, 실제 MySQL 이관·브라우저 E2E와 경로 라우팅은 실행하지 않았다.
  - 필요 조치: 최신 전체 테스트, 테스트 account DB 이관과 감사, 경로 라우팅·rollback을 순서대로 검증한다.

- **[Severity: Medium] [RAG] 문서 최소 점수의 광범위한 품질 검증 미완료**
  - 영향: 대표 질의는 통과했지만 전체 문서군의 recall/precision은 보장하지 않는다.
  - 필요 조치: 라벨된 질의셋으로 최소 점수와 top-k를 측정하고 결과를 RAG 또는 integration 로그에 남긴다.

- **[Severity: Medium] [Integration] 원격 MCP·Redis 운영형 E2E 미완료**
  - 영향: 현재 검증은 in-process 문서 MCP와 대표 API 흐름에 한정된다.
  - 필요 조치: 독립 프로세스/원격 MCP 및 Redis/freshness를 연결한 계약 테스트를 실행한다.

- **[Severity: Medium] [Backend/Integration] 운영 계정 저장소 기반 RBAC E2E 미완료**
  - 영향: 현재 인증·권한 검증은 결정적 메모리 저장소와 mock 기반 계약 테스트, 로컬 브라우저 흐름까지 확인됐다.
  - 필요 조치: 운영 계정 DB, HTTPS 세션 쿠키, 원격 MCP·Redis를 연결한 opt-in E2E를 실행한다.

- **[Severity: Medium] [Sales/Purchase/Integration] 차트와 도메인 metadata의 API 계약 통합 미완료**
  - 영향: Sales·Purchase 조회의 안전한 집계 결과는 준비됐지만 `chart_hint`·`metadata`와 그래프 렌더링이 최종 Chat API 계약까지 전달되는지 검증되지 않았다.
  - 필요 조치: `docs/team_share/03_cross_team_requests.md`, `docs/team_share/04_chart_spec.md`에 맞춰 Data MCP envelope와 UI를 통합하고 회귀 테스트를 추가한다.

- **[Severity: Low] [Purchase] `scripts/Create purchase views.py`가 옛 스키마를 전제로 함**
  - 영향: 실수로 재실행하면 새 5테이블 스키마와 컬럼이 안 맞는 뷰가 생성돼 조회가 깨질 수 있다.
  - 필요 조치: 스크립트 삭제 또는 상단에 "사용 중단" 주석 추가, 팀 공지.

## Next Steps

1. **[P0] [Backend/Integration] 정적 재검토 수정 후 Django check와 전체 테스트를 재실행한다.**
2. **[P0] [Backend/Integration] 실제 account DB에 Django migration을 적용하고 계정 감사를 실행한다.**
3. **[P0] [Backend/Integration] `/django-static/*`를 포함한 단일 공개 주소 경로 라우팅과 rollback을 검증한다.**
4. **[P0] [RAG/Integration] 라벨된 문서 질의셋으로 검색 품질과 문서 최소 점수를 검증한다.**
5. **[P0] [Integration] 원격 Document MCP와 Redis를 포함한 운영형 E2E를 실행한다.**
6. **[P1] [Backend/Integration] Sales/Purchase chart metadata와 채팅 그래프 계약을 통합·검증한다.**
7. **[P1] [RAG] 원문 문서 변경 시 등록 스크립트와 대표 RAG API 검증을 함께 수행한다.**
8. **[P2] [Purchase] `scripts/Create purchase views.py` 사용 중단 처리 및 팀 공지.**

## Recent Source Logs

- `docs/progress/integration/2026-08-20.md` — Django·FastAPI 인증 책임 분리 구현과 미검증 범위.
- `docs/progress/integration/2026-08-02.md` Session 3 — RAG 장애 원인 분리, 문서 DB/검색 점수 보정, 실제 API와 전체 pytest 검증.
- `docs/progress/integration/2026-08-02.md` Sessions 1–2 — API/Agent/MCP 경계 및 정본 MCP 경로 정리.
- `docs/progress/integration/2026-08-03.md` Session 2 — 로그인·세션·RBAC 구현, 시드 설정 오류 원인, 실제 브라우저 UI 전환 수정 및 134 passed 검증.
- `docs/progress/sales/2026-08-02.md` — Sales Text2SQL 안전성 강화와 실제 OpenAI·MySQL opt-in 계약 테스트 33 passed.
- `docs/progress/purchase/2026-08-03.md` — Purchase DB·ETL·뷰·계정을 처음부터 구축하고 Text2SQL을 sales 수준으로 완성, 실제 OpenAI·MySQL opt-in 테스트 33 passed + 브라우저 RBAC 확인.

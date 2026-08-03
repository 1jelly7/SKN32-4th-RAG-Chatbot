# Project Progress

> Last updated: 2026-08-03 02:20 KST
> Source logs: `docs/progress/<role>/YYYY-MM-DD.md`

## Current Verified State

- 일반 지식 질의는 근거가 없다는 이유만으로 일괄 거절하지 않으며, 사내·최신성·고위험·인용 요구 질의는 검증 근거가 없을 때 안전 응답을 유지한다.
- 문서 DB 접근 오류는 내부 오류로 뭉개지지 않고 Document MCP의 `QUERY_ERROR`로 분류된다. 지원 등록 절차로 문서 DB 스키마와 등록 문서 경로를 확인했다.
- 로컬 문서 검색 점수에 맞춘 문서 전용 최소 점수 `0.12`를 적용했다. 대표 문서 질의의 실제 Chat API는 HTTP 200, `DOCUMENT`, `SUPPORTED`, source 1개와 비어 있지 않은 답변을 반환했다.
- `skn_3rd` 환경 전체 테스트는 127 passed, 2 skipped이며 `git diff --check`를 통과했다.
- 상세 근거와 변경 범위는 `docs/progress/integration/2026-08-02.md` Session 3에 기록했다.
- 로그인·세션 기반 RBAC가 Chat API와 MCP 데이터 도구 경계에 적용됐으며, 관리자 실제 브라우저 로그인·새로고침 세션 복원·로그아웃 UI 전환을 확인했다.
- `skn_3rd` 환경 전체 테스트는 134 passed, 2 skipped이며 `git diff --check`를 통과했다. 상세 기록은 `docs/progress/integration/2026-08-03.md` Session 2에 있다.
- Sales `query_sales`는 뷰 5개, 조회 전용 계정, SQL 가드와 EXPLAIN 사전검증으로 강화됐고 실제 OpenAI·MySQL opt-in 테스트를 포함한 33개 검증을 통과했다.

## Area Status

| Area | Status | Current State | Evidence / Latest Log | Blocker or Next Decision |
|---|---|---|---|---|
| Backend | Partially verified | 로그인·세션·RBAC를 Chat API와 MCP 데이터 도구 경계에 적용하고 권한별 캐시 분리를 검증했다. | `docs/progress/integration/2026-08-03.md` Session 2 | 운영 계정 DB·Redis·원격 MCP를 함께 연결한 opt-in E2E가 남아 있다. |
| RAG | Partially verified | 문서 DB 등록·로컬 검색·대표 실제 API 흐름이 검증됐다. | `docs/progress/integration/2026-08-02.md` Session 3 | 라벨된 질의셋으로 최소 점수와 top-k 품질을 평가해야 한다. |
| Sales | Partially verified | `query_sales`에 뷰 화이트리스트, SQL 가드, EXPLAIN 사전검증과 1회 재시도를 적용했고 실제 OpenAI·MySQL opt-in 계약 테스트를 통과했다. | `docs/progress/sales/2026-08-02.md` | 원격 MCP transport와 채팅 차트 응답 계약의 end-to-end 검증이 남아 있다. |
| Purchase | Needs verification | 기존 fake 기반 Text2SQL 및 SQL guard 검증만 완료됐다. | `docs/progress/integration/2026-08-02.md` Sessions 1–2 | 실제 purchase DB 계약 테스트가 필요하다. |
| Integration | In progress | 실제 브라우저에서 관리자 로그인 후 UI 전환·세션 복원·로그아웃을 확인하고 전체 테스트를 재검증했다. | `docs/progress/integration/2026-08-03.md` Session 2 | 독립 프로세스/원격 MCP·Redis 및 운영 계정 저장소 E2E가 남아 있다. |

## Active Work

- [ ] `[rag/integration]` 라벨된 사내 문서 질의셋으로 문서 최소 점수 `0.12`와 top-k의 recall/precision을 측정한다.
- [ ] `[integration]` 원격 Document MCP transport와 독립 프로세스 E2E를 실행한다.
- [ ] `[integration]` Redis 및 문서 version/freshness 기반 캐시 무효화를 검증한다.
- [ ] `[purchase]` 실제 DB opt-in 계약 테스트를 실행하고 결과를 영역 로그에 기록한다.
- [ ] `[backend/integration]` Sales가 제공하는 `chart_hint`·`metadata`를 보존하는 Data MCP envelope와 채팅 그래프 렌더링을 통합·검증한다.
- [ ] `[backend/integration]` 운영 계정 저장소·원격 MCP·Redis를 연결한 opt-in RBAC E2E와 HTTPS 세션 쿠키 설정을 검증한다.

## Verified Milestones

- [x] 2026-08-02 일반 지식/검증 필요 질의의 답변 정책을 분리하고, 이전 프롬프트 응답 캐시를 버전 갱신으로 무효화했다.
- [x] 2026-08-02 문서 DB 오류·문서 등록·검색 점수 보정 문제를 단계적으로 분리해 대표 문서 RAG API를 HTTP 200 / `SUPPORTED`로 복구했다.
- [x] 2026-08-02 `skn_3rd` 환경에서 전체 pytest 127 passed, 2 skipped 및 `git diff --check` 통과를 확인했다.
- [x] 2026-08-03 로그인 UI·HttpOnly 세션·역할 기반 접근 제어를 적용하고, 실제 브라우저의 관리자 메인 화면 전환 문제를 수정했다.
- [x] 2026-08-03 `skn_3rd` 환경에서 전체 pytest 134 passed, 2 skipped 및 `git diff --check` 통과를 확인했다.
- [x] 2026-08-02 Sales Text2SQL을 뷰 기반 조회와 SQL 가드로 강화하고, 실제 OpenAI·MySQL opt-in 테스트 33건을 통과했다.

## Key Decisions

| Date | Decision | Rationale | Trade-off / Follow-up | Source |
|---|---|---|---|---|
| 2026-08-02 | 안정적 일반 지식과 검증 근거가 필수인 질의를 분리한다. | 일반 질문의 불필요한 거절을 막으면서 사내·최신성·고위험 정보의 근거 요구를 보존한다. | 질의 분류 규칙은 실제 질의셋으로 계속 보정한다. | Session 3 |
| 2026-08-02 | 문서 검색 점수는 문서 전용 최소 점수 `0.12`로 평가한다. | 로컬 n-gram FAISS 점수 범위가 다른 evidence의 전역 기준과 다르다. | 라벨된 평가 데이터셋으로 임계값을 재조정한다. | Session 3 |
| 2026-08-02 | 문서 DB 외부 오류는 `QUERY_ERROR`로 보존한다. | 사용자에게 내부 세부 정보를 노출하지 않으면서 운영 원인을 구분한다. | 원격 MCP에서도 동일한 envelope 계약을 검증한다. | Session 3 |
| 2026-08-03 | 권한은 UI가 아닌 Chat API와 MCP 데이터 도구 양쪽에서 검증한다. | UI 경로 우회나 직접 MCP 호출에도 역할 범위를 보존한다. | 운영 저장소·원격 MCP를 포함한 E2E가 후속으로 필요하다. | `integration/2026-08-03.md` Session 2 |
| 2026-08-03 | 로그인 오버레이의 `hidden` 상태를 CSS에서 명시적으로 `display: none` 처리한다. | 레이아웃의 `display: grid`가 기본 숨김 동작을 덮어쓰는 실제 UI 장애를 방지한다. | 다른 오버레이에도 hidden 스타일 충돌 여부를 검토한다. | `integration/2026-08-03.md` Session 2 |
| 2026-08-02 | Sales Text2SQL은 원본 테이블 대신 의미 기반 뷰와 화이트리스트로 조회한다. | 도메인 컬럼·집계 정의를 일관되게 유지하고 임의 테이블 접근을 방지한다. | 원격 MCP 환경에서도 동일한 envelope와 권한 경계를 검증한다. | `docs/progress/sales/2026-08-02.md` |

## Blockers and Open Questions

- **[Severity: Medium] [RAG] 문서 최소 점수의 광범위한 품질 검증 미완료**
  - 영향: 대표 질의는 통과했지만 전체 문서군의 recall/precision은 보장하지 않는다.
  - 필요 조치: 라벨된 질의셋으로 최소 점수와 top-k를 측정하고 결과를 RAG 또는 integration 로그에 남긴다.

- **[Severity: Medium] [Integration] 원격 MCP·Redis 운영형 E2E 미완료**
  - 영향: 현재 검증은 in-process 문서 MCP와 대표 API 흐름에 한정된다.
  - 필요 조치: 독립 프로세스/원격 MCP 및 Redis/freshness를 연결한 계약 테스트를 실행한다.

- **[Severity: Medium] [Backend/Integration] 운영 계정 저장소 기반 RBAC E2E 미완료**
  - 영향: 현재 인증·권한 검증은 결정적 메모리 저장소와 mock 기반 계약 테스트, 로컬 브라우저 흐름까지 확인됐다.
  - 필요 조치: 운영 계정 DB, HTTPS 세션 쿠키, 원격 MCP·Redis를 연결한 opt-in E2E를 실행한다.

- **[Severity: Medium] [Sales/Integration] 차트와 도메인 metadata의 API 계약 통합 미완료**
  - 영향: Sales 조회의 안전한 집계 결과는 준비됐지만 `chart_hint`·`metadata`와 그래프 렌더링이 최종 Chat API 계약까지 전달되는지 검증되지 않았다.
  - 필요 조치: `docs/team_share/03_cross_team_requests.md`, `docs/team_share/04_chart_spec.md`에 맞춰 Data MCP envelope와 UI를 통합하고 회귀 테스트를 추가한다.

## Next Steps

1. **[P0] [RAG/Integration] 라벨된 문서 질의셋으로 검색 품질과 문서 최소 점수를 검증한다.**
2. **[P0] [Integration] 원격 Document MCP와 Redis를 포함한 운영형 E2E를 실행한다.**
3. **[P1] [Purchase] 실제 DB opt-in 계약 테스트를 수행한다.**
4. **[P1] [Backend/Integration] Sales chart metadata와 채팅 그래프 계약을 통합·검증한다.**
5. **[P1] [RAG] 원문 문서 변경 시 등록 스크립트와 대표 RAG API 검증을 함께 수행한다.**
6. **[P1] [Backend/Integration] 운영 환경에서 계정 시드 비밀값과 `AUTH_SECRET_KEY`를 비밀 관리 수단으로 제공하고 RBAC E2E를 수행한다.**

## Recent Source Logs

- `docs/progress/integration/2026-08-02.md` Session 3 — RAG 장애 원인 분리, 문서 DB/검색 점수 보정, 실제 API와 전체 pytest 검증.
- `docs/progress/integration/2026-08-02.md` Sessions 1–2 — API/Agent/MCP 경계 및 정본 MCP 경로 정리.
- `docs/progress/integration/2026-08-03.md` Session 2 — 로그인·세션·RBAC 구현, 시드 설정 오류 원인, 실제 브라우저 UI 전환 수정 및 134 passed 검증.
- `docs/progress/sales/2026-08-02.md` — Sales Text2SQL 안전성 강화와 실제 OpenAI·MySQL opt-in 계약 테스트 33 passed.

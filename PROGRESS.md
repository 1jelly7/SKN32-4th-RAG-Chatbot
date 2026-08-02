# Project Progress

> Last updated: 2026-08-02 13:04 KST
> Source logs: `docs/progress/<role>/YYYY-MM-DD.md`

## Current Verified State

- 2026-08-02 통합 변경은 `skn_3rd` 환경에서 전체 `pytest` 120건 통과, 2건 skip 및 `compileall` 통과로 검증되었다. 근거: `docs/progress/integration/2026-08-02.md`, 커밋 `526ae78`.
- 채팅 API의 `evidence_status`와 `tables` 공개 계약, 오류 코드 매핑 및 `BOTH` 근거 수집 순서가 문서와 테스트에 반영되었다. 원격 MCP 환경에서의 동작은 아직 검증되지 않았다.
- 구매 Text2SQL 및 purchase/sales 공통 MCP envelope의 SELECT-only 방어는 단위 테스트(22 passed)와 전체 회귀에 포함되었다. 실제 DB 연결 계약 테스트는 미검증이다.
- 세션별 캐시 격리, evidence 보강 조회/contradiction 처리, UI 문자열 escaping 변경은 fake 기반 계약·회귀 테스트로 확인되었다. Redis, 브라우저 E2E 및 실제 인덱스 freshness는 미검증이다.
- `backend`, `rag`, `sales`, `purchase`의 일별 이력 파일은 현재 제공되지 않아 각 영역의 독립 완료 상태나 미해결 업무는 확인할 수 없다.

## Area Status

| Area | Status | Current State | Evidence / Latest Log | Blocker or Next Decision |
|---|---|---|---|---|
| Backend | Needs verification | 통합 로그에는 API·캐시·오류 계약 변경과 전체 회귀 통과가 기록되어 있으나, backend 전용 일별 이력이 없다. | `docs/progress/integration/2026-08-02.md` (커밋 `526ae78`) | 원격 MCP, Redis, 실제 DB/ETL 통합 검증 및 backend 전용 상태 기록 필요. |
| RAG | Needs verification | 문서 MCP 및 evidence 경계 변경은 통합 로그에 있으나, 수집·인덱스·검색·평가의 독립 검증 기록이 없다. | `docs/progress/integration/2026-08-02.md` | 실제 Document MCP와 인덱스 version/freshness 검증 필요. |
| Sales | Needs verification | sales DB를 주입하는 opt-in 테스트 전제는 교정되었으나 실제 sales DB 테스트는 실행되지 않았다. | `docs/progress/integration/2026-08-02.md` | `RUN_LOCAL_MYSQL_TESTS=1` 실제 DB contract test 필요. |
| Purchase | Needs verification | 구매 Text2SQL·읽기 전용 adapter·SQL guard가 구현되어 회귀에 포함되었으나 실제 purchase DB contract test는 미검증이다. | `docs/progress/integration/2026-08-02.md` | 실제 purchase DB 연결 및 contract test 필요. |
| Integration | In progress | API/Agent/MCP 경계와 문서 정합성 감사 항목 14건은 회귀 테스트로 검증되었다. 원격 transport, 브라우저 E2E, Redis/freshness, 보류 감사 항목은 남아 있다. | `docs/progress/integration/2026-08-02.md`, `526ae78` | 담당자 승인 및 외부 의존 서비스 접근이 필요. |

## Active Work

- [ ] `[integration]` 보류된 감사 항목 1, 2, 4, 8, 10, 14, 21의 처리 우선순위를 담당자 승인 후 확정 — 완료 조건: 승인 기록과 우선순위가 integration 일별 이력에 남음.
- [ ] `[integration]` 원격 MCP transport와 실제 purchase/sales DB contract test 구현·실행 — 완료 조건: 원격 Document/Data MCP 및 실제 DB를 대상으로 한 계약 테스트 결과가 기록됨.
- [ ] `[integration]` 브라우저 E2E로 질문·LLM 답변·표 셀의 HTML 주입 방지와 정상 렌더링 검증 — 완료 조건: 자동화 E2E 실행 결과가 기록됨.
- [ ] `[integration]` Redis 및 실제 index/database freshness 공급자 연결 후 cache invalidation 테스트 추가 — 완료 조건: 실제 공급자 기반 무효화 테스트 결과가 기록됨.

## Verified Milestones

- [x] 2026-08-02 — 승인된 정합성 감사 항목 14건을 API, Agent, MCP, 구매·판매 경계 및 문서에 반영 — 근거: `docs/progress/integration/2026-08-02.md`, 커밋 `526ae78`.
- [x] 2026-08-02 — 전체 회귀 120 passed, 2 skipped 및 `compileall` 통과 — 근거: `docs/progress/integration/2026-08-02.md`.
- [x] 2026-08-02 — Data MCP 단위 테스트 22 passed로 구매 Text2SQL와 SQL guard 회귀 확인 — 근거: `docs/progress/integration/2026-08-02.md`.

## Key Decisions

| Date | Decision | Rationale | Trade-off / Follow-up | Source |
|---|---|---|---|---|
| 2026-08-02 | Agent는 provider를 직접 호출하지 않고 `InProcessMCPPort`를 통해 같은 프로세스의 Tool service를 호출한다. | 원격 transport 도입 전에도 비동기 Tool 계약을 유지하기 위해서다. | 원격 MCP transport·격리·운영 수명주기 검증이 별도로 필요하다. | `docs/progress/integration/2026-08-02.md` |
| 2026-08-02 | 세션 원문 대신 결정적 해시를 cache key material로 사용한다. | 세션별 동일 질문을 격리하면서 원문을 키에 남기지 않기 위해서다. | Redis 기반 실제 무효화 검증이 남아 있다. | `docs/progress/integration/2026-08-02.md` |
| 2026-08-02 | 공식 backend Tool 경계를 `mcp_servers/document_tools/`와 `mcp_servers/data_tools/`로 한정한다. | 현재 문서화된 MCP 계약과 소유권 경계를 명확히 하기 위해서다. | 중복 실험 스켈레톤의 계약 확정 여부는 후속 결정이 필요하다. | `docs/progress/integration/2026-08-02.md` |

## Blockers and Open Questions

- **[Severity: High] [Integration] 보류 감사 항목의 우선순위가 승인 대기 상태**
  - 영향: 항목 1, 2, 4, 8, 10, 14, 21은 승인 없이 진행할 수 없다.
  - 필요한 결정 또는 조치: 담당자가 처리 우선순위와 승인 여부를 확정한다.
  - 담당 또는 의존 대상: 해당 감사 항목 담당자.
  - 근거: `docs/progress/integration/2026-08-02.md`

- **[Severity: High] [Integration] 원격 MCP와 실제 Document/Data MCP 통합이 미검증**
  - 영향: fake 기반 통합 테스트 통과만으로 외부 서비스 연결 완료를 주장할 수 없다.
  - 필요한 결정 또는 조치: 원격 transport를 구현하고 실제 환경 contract test를 실행한다.
  - 담당 또는 의존 대상: integration 및 원격 MCP 서비스 접근 권한.
  - 근거: `docs/progress/integration/2026-08-02.md`

- **[Severity: Medium] [Backend/RAG/Sales/Purchase] 역할별 일별 상태 기록 부재**
  - 영향: 각 영역의 독립 완료·차단·다음 작업을 검증 근거와 함께 판단할 수 없다.
  - 필요한 결정 또는 조치: 최신 작업 및 과거 미해결 항목을 각 역할의 일별 이력에 기록·갱신한다.
  - 담당 또는 의존 대상: 각 역할 담당자.
  - 근거: `docs/progress/` 내 현재 역할별 일별 로그 현황.

## Next Steps

1. **[P0] [Integration] 보류 감사 항목의 승인과 우선순위를 확정한다.**
   - 완료 조건: 항목 1, 2, 4, 8, 10, 14, 21의 승인·우선순위가 일별 이력에 기록된다.
   - 선행 조건 또는 의존성: 담당자 결정.
   - 참조: `docs/progress/integration/2026-08-02.md`
2. **[P0] [Integration] 원격 MCP 및 실제 purchase/sales DB contract test를 실행한다.**
   - 완료 조건: 원격 Document/Data MCP와 실제 DB를 사용하는 테스트 결과 및 실패·skip 사유가 기록된다.
   - 선행 조건 또는 의존성: 원격 MCP URL, 실제 DB 접근 및 테스트 데이터.
   - 참조: `docs/progress/integration/2026-08-02.md`
3. **[P1] [Integration] 브라우저 E2E와 Redis/freshness 기반 cache invalidation을 검증한다.**
   - 완료 조건: UI escaping·정상 렌더링과 실제 공급자 기반 캐시 무효화의 자동화 결과가 기록된다.
   - 선행 조건 또는 의존성: 브라우저 자동화, Redis 및 인덱스/database freshness 공급자.
   - 참조: `docs/progress/integration/2026-08-02.md`
4. **[P1] [Backend/RAG/Sales/Purchase] 각 역할의 최신 일별 이력을 보완한다.**
   - 완료 조건: 각 역할의 현재 상태, 검증 근거, 미검증 항목 및 다음 작업이 해당 역할 로그에 기록된다.
   - 선행 조건 또는 의존성: 각 영역 담당자의 작업 사실 및 증거.
   - 참조: `docs/progress/README.md`

## Recent Source Logs

- `docs/progress/integration/2026-08-02.md` — 감사 항목 14건 반영, 전체 회귀 120 passed 확인 및 외부 통합 미검증 사항 기록.
- `docs/progress/backend/` — 일별 로그 없음; 현재 상태 확인 필요.
- `docs/progress/rag/` — 일별 로그 없음; 현재 상태 확인 필요.
- `docs/progress/sales/` — 일별 로그 없음; 현재 상태 확인 필요.
- `docs/progress/purchase/` — 일별 로그 없음; 현재 상태 확인 필요.

# Project Progress

> Last updated: 2026-08-02 23:40 KST
> Source logs: `docs/progress/<role>/YYYY-MM-DD.md`

## Current Verified State

- 일반 지식 질의는 근거가 없다는 이유만으로 일괄 거절하지 않으며, 사내·최신성·고위험·인용 요구 질의는 검증 근거가 없을 때 안전 응답을 유지한다.
- 문서 DB 접근 오류는 내부 오류로 뭉개지지 않고 Document MCP의 `QUERY_ERROR`로 분류된다. 지원 등록 절차로 문서 DB 스키마와 등록 문서 경로를 확인했다.
- 로컬 문서 검색 점수에 맞춘 문서 전용 최소 점수 `0.12`를 적용했다. 대표 문서 질의의 실제 Chat API는 HTTP 200, `DOCUMENT`, `SUPPORTED`, source 1개와 비어 있지 않은 답변을 반환했다.
- `skn_3rd` 환경 전체 테스트는 127 passed, 2 skipped이며 `git diff --check`를 통과했다.
- 상세 근거와 변경 범위는 `docs/progress/integration/2026-08-02.md` Session 3에 기록했다.

## Area Status

| Area | Status | Current State | Evidence / Latest Log | Blocker or Next Decision |
|---|---|---|---|---|
| Backend | In progress | Chat API·Agent·MCP 오류 경계와 캐시 프롬프트 버전 변경을 회귀 테스트했다. | `docs/progress/integration/2026-08-02.md` Session 3 | Redis와 원격 MCP transport를 포함한 운영형 E2E가 남아 있다. |
| RAG | Partially verified | 문서 DB 등록·로컬 검색·대표 실제 API 흐름이 검증됐다. | `docs/progress/integration/2026-08-02.md` Session 3 | 라벨된 질의셋으로 최소 점수와 top-k 품질을 평가해야 한다. |
| Sales | Needs verification | 기존 fake 기반 계약 검증만 완료됐다. | `docs/progress/integration/2026-08-02.md` Sessions 1–2 | 실제 sales DB opt-in 계약 테스트가 필요하다. |
| Purchase | Needs verification | 기존 fake 기반 Text2SQL 및 SQL guard 검증만 완료됐다. | `docs/progress/integration/2026-08-02.md` Sessions 1–2 | 실제 purchase DB 계약 테스트가 필요하다. |
| Integration | In progress | 대표 in-process 문서 RAG 실환경 경로를 복구하고 전체 테스트를 재검증했다. | `docs/progress/integration/2026-08-02.md` Session 3 | 독립 프로세스/원격 MCP와 Redis/freshness E2E가 남아 있다. |

## Active Work

- [ ] `[rag/integration]` 라벨된 사내 문서 질의셋으로 문서 최소 점수 `0.12`와 top-k의 recall/precision을 측정한다.
- [ ] `[integration]` 원격 Document MCP transport와 독립 프로세스 E2E를 실행한다.
- [ ] `[integration]` Redis 및 문서 version/freshness 기반 캐시 무효화를 검증한다.
- [ ] `[sales/purchase]` 실제 DB opt-in 계약 테스트를 실행하고 결과를 각 영역 로그에 기록한다.

## Verified Milestones

- [x] 2026-08-02 일반 지식/검증 필요 질의의 답변 정책을 분리하고, 이전 프롬프트 응답 캐시를 버전 갱신으로 무효화했다.
- [x] 2026-08-02 문서 DB 오류·문서 등록·검색 점수 보정 문제를 단계적으로 분리해 대표 문서 RAG API를 HTTP 200 / `SUPPORTED`로 복구했다.
- [x] 2026-08-02 `skn_3rd` 환경에서 전체 pytest 127 passed, 2 skipped 및 `git diff --check` 통과를 확인했다.

## Key Decisions

| Date | Decision | Rationale | Trade-off / Follow-up | Source |
|---|---|---|---|---|
| 2026-08-02 | 안정적 일반 지식과 검증 근거가 필수인 질의를 분리한다. | 일반 질문의 불필요한 거절을 막으면서 사내·최신성·고위험 정보의 근거 요구를 보존한다. | 질의 분류 규칙은 실제 질의셋으로 계속 보정한다. | Session 3 |
| 2026-08-02 | 문서 검색 점수는 문서 전용 최소 점수 `0.12`로 평가한다. | 로컬 n-gram FAISS 점수 범위가 다른 evidence의 전역 기준과 다르다. | 라벨된 평가 데이터셋으로 임계값을 재조정한다. | Session 3 |
| 2026-08-02 | 문서 DB 외부 오류는 `QUERY_ERROR`로 보존한다. | 사용자에게 내부 세부 정보를 노출하지 않으면서 운영 원인을 구분한다. | 원격 MCP에서도 동일한 envelope 계약을 검증한다. | Session 3 |

## Blockers and Open Questions

- **[Severity: Medium] [RAG] 문서 최소 점수의 광범위한 품질 검증 미완료**
  - 영향: 대표 질의는 통과했지만 전체 문서군의 recall/precision은 보장하지 않는다.
  - 필요 조치: 라벨된 질의셋으로 최소 점수와 top-k를 측정하고 결과를 RAG 또는 integration 로그에 남긴다.

- **[Severity: Medium] [Integration] 원격 MCP·Redis 운영형 E2E 미완료**
  - 영향: 현재 검증은 in-process 문서 MCP와 대표 API 흐름에 한정된다.
  - 필요 조치: 독립 프로세스/원격 MCP 및 Redis/freshness를 연결한 계약 테스트를 실행한다.

## Next Steps

1. **[P0] [RAG/Integration] 라벨된 문서 질의셋으로 검색 품질과 문서 최소 점수를 검증한다.**
2. **[P0] [Integration] 원격 Document MCP와 Redis를 포함한 운영형 E2E를 실행한다.**
3. **[P1] [Sales/Purchase] 실제 DB opt-in 계약 테스트를 수행한다.**
4. **[P1] [RAG] 원문 문서 변경 시 등록 스크립트와 대표 RAG API 검증을 함께 수행한다.**

## Recent Source Logs

- `docs/progress/integration/2026-08-02.md` Session 3 — RAG 장애 원인 분리, 문서 DB/검색 점수 보정, 실제 API와 전체 pytest 검증.
- `docs/progress/integration/2026-08-02.md` Sessions 1–2 — API/Agent/MCP 경계 및 정본 MCP 경로 정리.

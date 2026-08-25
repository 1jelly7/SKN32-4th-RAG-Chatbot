# 진행 현황 안내

이 파일의 과거 요약은 구조 분리 전 상태에서 갱신이 중단돼 제거했다. 프로젝트 전체의
현재 우선순위와 검증 상태는 저장소 루트의 [PROGRESS.md](../../PROGRESS.md)를 정본으로
사용한다.

Django·FastAPI 구조 분리의 단계별 상태는 다음 문서를 함께 본다.

- [구조 분리 계획과 체크리스트](../django-fastapi-separation-plan.md)
- [2026-08-20 통합 진행 이력](integration/2026-08-20.md)
- [진행 이력 작성 규칙](README.md)

현재 핵심 미검증 항목은 최신 구조 수정 후 전체 테스트, 실제 account DB migration·감사,
동일 origin 경로 라우팅, `/internal/auth/*` 비공개 정책과 rollback 검증이다.

# -*- coding: utf-8 -*-
"""대시보드 월별 추이 데이터 HTTP 경계.

app/api/anomalies.py와 동일한 인증·권한 패턴을 그대로 따른다. KPI·이상거래
목록은 이 파일의 책임이 아니다(팀원 진행 중, docs/team_share/
09_dashboard_anomaly_api_spec.md 참고 - 저장소에 아직 없다면 팀원에게 확인 필요).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.auth.dependencies import CurrentUser
from app.auth.policy import require_database_access
from app.services.monthly_trends_service import MonthlyTrends, get_monthly_trends

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/monthly-trends", response_model=MonthlyTrends)
async def monthly_trends(
    user: CurrentUser,
    year: int = Query(
        default_factory=lambda: datetime.now(timezone.utc).year,
        ge=2000,
        le=2100,
        description="조회할 연도 (기본값: 올해). 데이터가 실제 현재 연도로 채워져"
        " 있지 않은 환경이면 예: ?year=2025 로 덮어써서 확인할 수 있다.",
    ),
) -> MonthlyTrends:
    """지정 연도(기본 올해)의 sales_trend/purchase_trend를 반환한다.

    dashboard.js의 DUMMY_DASHBOARD_DATA와 동일한 필드명(period, value,
    is_anomaly)을 쓰므로, 최종적으로 GET /api/dashboard/anomalies가 완성되면
    이 두 배열을 그대로 그 응답에 끼워 넣기만 하면 된다.

    anomalies 엔드포인트와 동일한 이유로 sales_db/purchase_db 접근 권한을 명시적
    으로 확인한다. 캐싱 없이 매 요청마다 재계산한다.
    """
    try:
        require_database_access(user, "sales_db")
        require_database_access(user, "purchase_db")
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail="매출/구매 데이터에 접근할 권한이 없습니다."
        ) from exc

    return await get_monthly_trends(year)

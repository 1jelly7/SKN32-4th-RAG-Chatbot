"""이상탐지(anomaly) 임시 대시보드 데이터 HTTP 경계.

TEMP: 다른 팀원이 실제 이상탐지 대시보드를 완성하면 이 파일 전체를 지운다
(django_app/web 쪽 TEMP 블록, app/services/anomaly_service.py와 함께 — 1단계
삭제 체크리스트 참고).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.auth.dependencies import CurrentUser
from app.auth.policy import require_database_access
from app.services.anomaly_service import AnomalyRow, get_anomalies

router = APIRouter(tags=["anomalies"])


@router.get("/anomalies", response_model=list[AnomalyRow])
async def list_anomalies(user: CurrentUser) -> list[AnomalyRow]:
    """sales/purchase 이상탐지 결과를 캐싱 없이 매 요청마다 새로 계산해 반환한다.

    # 추가: 계획에는 "CurrentUser 인증"만 명시돼 있었지만, 이 위젯은 sales/purchase
    # 데이터를 함께 보여준다. hr 역할은 document_db만 허용돼 있어서(shared/auth_policy.py)
    # 인증만으로는 막히지 않는다 — 여기서 두 DB 접근 권한을 명시적으로 확인한다.
    """
    try:
        require_database_access(user, "sales_db")
        require_database_access(user, "purchase_db")
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail="이상탐지 데이터에 접근할 권한이 없습니다."
        ) from exc

    return await get_anomalies()

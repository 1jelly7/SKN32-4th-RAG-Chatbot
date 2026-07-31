from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """프로세스가 요청을 수신할 수 있음을 나타내는 최소 헬스 응답을 반환한다.

    외부 MCP, Redis, MySQL의 준비 상태까지 확인할지 여부는 별도 readiness 정책으로
    분리하고, 이 엔드포인트가 민감 설정이나 연결 정보를 노출하지 않게 한다.
    """
    return HealthResponse(status="ok")

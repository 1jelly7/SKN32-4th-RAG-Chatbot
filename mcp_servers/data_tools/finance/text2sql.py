from app.core.security import UserContext
from mcp_servers.data_tools.finance.schema import SchemaResource


async def generate_sql(
    question: str,
    user_context: UserContext,
    schema: SchemaResource,
) -> str:
    """질문, 최소 사용자 범위, 허용 스키마로 SELECT SQL 초안을 생성한다.

    프롬프트는 제공된 테이블/컬럼만 사용하고 단일 SELECT·LIMIT를 요구하며, tenant 등
    권한 필터의 추가가 필요한 구조로 출력시킨다. 생성 결과는 신뢰하지 않고 반드시
    sql_guard.validate_sql을 거친 뒤에만 실행 가능하다.
    """
    ...

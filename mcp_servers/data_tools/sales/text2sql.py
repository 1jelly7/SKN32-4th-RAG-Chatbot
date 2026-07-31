from app.core.security import UserContext
from mcp_servers.data_tools.sales.schema import SchemaResource


async def generate_sql(question: str, user_context: UserContext, schema: SchemaResource) -> str:
    """판매 도메인에 한정된 단일 SELECT 초안을 만든다."""
    ...

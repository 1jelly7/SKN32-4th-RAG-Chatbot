from app.core.security import UserContext
from mcp_servers.data.schema import SchemaResource


async def generate_sql(
    question: str,
    user_context: UserContext,
    schema: SchemaResource,
) -> str:
    ...

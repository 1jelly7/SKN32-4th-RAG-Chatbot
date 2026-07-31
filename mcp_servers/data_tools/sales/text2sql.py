from mcp_servers.data_tools.sales.schema import SchemaResource


async def generate_sql(question: str, schema: SchemaResource) -> str:
    """판매 도메인에 한정된 단일 SELECT 초안을 만든다."""
    ...

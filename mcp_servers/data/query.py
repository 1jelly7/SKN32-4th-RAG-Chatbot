from mcp_servers.data.text2sql import generate_sql
from mcp_servers.data.sql_guard import validate_sql
from mcp_servers.data.mysql import query_readonly
async def query_business_data(question: str, user_context: dict) -> list[dict]:
    sql = await generate_sql(question)
    validate_sql(sql)
    return query_readonly(sql)

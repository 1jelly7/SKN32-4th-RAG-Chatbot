import asyncio

import pytest
from app.mcp.client import MCPClient
from mcp_servers.data_tools.sql_guard import validate_sql


def test_sql_guard_blocks_write():
    with pytest.raises(ValueError): validate_sql('DELETE FROM users')


def test_sql_guard_allows_select():
    assert validate_sql("SELECT id FROM users") == "SELECT id FROM users"


def test_data_query_dispatches_explicit_domain():
    class StubMCPClient(MCPClient):
        async def finance_query(self, question, user_context):
            return [{"domain": "finance"}]

        async def sales_query(self, question, user_context):
            return [{"domain": "sales"}]

    client = StubMCPClient("http://document", "http://data")
    context = {
        "user_id": "user",
        "role": "analyst",
        "tenant_id": "tenant",
        "permissions": [],
    }

    finance = asyncio.run(client.data_query("finance", "재무 현황", context))
    sales = asyncio.run(client.data_query("sales", "판매 현황", context))
    assert finance == [{"domain": "finance"}]
    assert sales == [{"domain": "sales"}]

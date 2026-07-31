import asyncio

from app.mcp.client import MCPClient


def test_data_query_dispatches_explicit_domain():
    class StubMCPClient(MCPClient):
        async def finance_query(self, question):
            return [{"domain": "finance"}]

        async def sales_query(self, question):
            return [{"domain": "sales"}]

    client = StubMCPClient("http://document", "http://data")
    finance = asyncio.run(client.data_query("finance", "재무 현황"))
    sales = asyncio.run(client.data_query("sales", "판매 현황"))
    assert finance == [{"domain": "finance"}]
    assert sales == [{"domain": "sales"}]

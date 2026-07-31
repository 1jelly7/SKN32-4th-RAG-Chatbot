import asyncio

from app.mcp.client import MCPClient


def test_data_query_dispatches_explicit_domain():
    class StubMCPClient(MCPClient):
<<<<<<< HEAD
        async def finance_query(self, question):
            return [{"domain": "finance"}]
=======
        async def purchase_query(self, question):
            return [{"domain": "purchase"}]
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0

        async def sales_query(self, question):
            return [{"domain": "sales"}]

    client = StubMCPClient("http://document", "http://data")
<<<<<<< HEAD
    finance = asyncio.run(client.data_query("finance", "재무 현황"))
    sales = asyncio.run(client.data_query("sales", "판매 현황"))
    assert finance == [{"domain": "finance"}]
=======
    purchase = asyncio.run(client.data_query("purchase", "구매 현황"))
    sales = asyncio.run(client.data_query("sales", "판매 현황"))
    assert purchase == [{"domain": "purchase"}]
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0
    assert sales == [{"domain": "sales"}]

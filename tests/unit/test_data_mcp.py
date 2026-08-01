import asyncio

from app.mcp.client import MCPClient


def test_data_query_dispatches_explicit_domain():
    class StubMCPClient(MCPClient):
        async def purchase_query(self, question):
            return [{"domain": "purchase"}]

        async def sales_query(self, question):
            return [{"domain": "sales"}]

    client = StubMCPClient("http://document", "http://data")
    purchase = asyncio.run(client.data_query("purchase", "구매 현황"))
    sales = asyncio.run(client.data_query("sales", "판매 현황"))
    both = asyncio.run(client.data_query("both", "구매와 판매 현황"))
    assert purchase == [{"domain": "purchase"}]
    assert sales == [{"domain": "sales"}]
    assert both == [{"domain": "purchase"}, {"domain": "sales"}]

"""CoinGeckoTool parsing + three-way cache contract with mocked HTTP."""
import httpx
import pytest

from app.tools.coingecko import CoinGeckoTool

MARKET_JSON = [
    {
        "id": "bitcoin",
        "current_price": 62000.0,
        "market_cap": 1.2e12,
        "total_volume": 3.0e10,
        "price_change_percentage_24h": 1.5,
    }
]
GLOBAL_JSON = {"data": {"market_cap_percentage": {"btc": 52.3, "eth": 17.1}}}
META_JSON = {
    "id": "bitcoin",
    "name": "Bitcoin",
    "symbol": "btc",
    "market_cap_rank": 1,
    "categories": ["Cryptocurrency", "Layer 1"],
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/v3/coins/markets":
        return httpx.Response(200, json=MARKET_JSON)
    if path == "/api/v3/global":
        return httpx.Response(200, json=GLOBAL_JSON)
    if path == "/api/v3/coins/bitcoin":
        return httpx.Response(200, json=META_JSON)
    return httpx.Response(404)


def _tool(handler, **kw) -> CoinGeckoTool:
    return CoinGeckoTool(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), **kw)


async def test_market_parses_fresh():
    tool = _tool(_handler)
    try:
        out = await tool.market("BTCUSDT")
        assert out["price"] == 62000.0 and out["market_cap"] == 1.2e12
        assert out["stale"] is False
    finally:
        await tool._client.aclose()


async def test_dominance_and_meta_shapes():
    tool = _tool(_handler)
    try:
        dom = await tool.dominance()
        assert dom["btc_dominance"] == 52.3 and dom["eth_dominance"] == 17.1
        meta = await tool.meta("BTCUSDT")
        assert meta["name"] == "Bitcoin" and meta["market_cap_rank"] == 1
        assert "Cryptocurrency" in meta["categories"]
    finally:
        await tool._client.aclose()


async def test_stale_fallback():
    state = {"fail": False}

    def flaky(request):
        if state["fail"]:
            raise httpx.ConnectError("down")
        return _handler(request)

    tool = _tool(flaky, ttl=0)
    try:
        fresh = await tool.market("BTCUSDT")
        assert fresh["stale"] is False
        state["fail"] = True
        fallback = await tool.market("BTCUSDT")
        assert fallback["stale"] is True and fallback["price"] == 62000.0
    finally:
        await tool._client.aclose()


async def test_no_snapshot_raises():
    def boom(request):
        raise httpx.ConnectError("down")

    tool = _tool(boom, ttl=0)
    try:
        with pytest.raises(httpx.ConnectError):
            await tool.market("BTCUSDT")
    finally:
        await tool._client.aclose()

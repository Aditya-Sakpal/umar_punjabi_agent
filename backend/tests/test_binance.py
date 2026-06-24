"""BinanceTool parsing + stale fallback with a mocked HTTP layer (httpx.MockTransport)."""
import httpx
import pytest

from app.tools.binance import BinanceTool

PRICE_JSON = {"symbol": "BTCUSDT", "price": "65000.50"}
PREMIUM_JSON = {
    "symbol": "BTCUSDT",
    "lastFundingRate": "0.00012",
    "markPrice": "65010.00",
    "nextFundingTime": 1700000000000,
}
TICKER24_JSON = {
    "symbol": "BTCUSDT",
    "volume": "1234.5",
    "quoteVolume": "80000000.0",
    "priceChangePercent": "2.5",
}
KLINES_JSON = [
    [1700000000000, "64000.0", "65500.0", "63500.0", "65000.5", "100.0", 1700003599999, "x", 1, "y", "z", "0"],
    [1700003600000, "65000.5", "66000.0", "64800.0", "65800.0", "120.0", 1700007199999, "x", 1, "y", "z", "0"],
]


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/v3/ticker/price":
        return httpx.Response(200, json=PRICE_JSON)
    if path == "/fapi/v1/premiumIndex":
        return httpx.Response(200, json=PREMIUM_JSON)
    if path == "/api/v3/ticker/24hr":
        return httpx.Response(200, json=TICKER24_JSON)
    if path == "/api/v3/klines":
        return httpx.Response(200, json=KLINES_JSON)
    return httpx.Response(404)


def _make_tool(handler, **kw) -> BinanceTool:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return BinanceTool(client=client, **kw)


async def test_price_parses_and_is_fresh():
    tool = _make_tool(_handler)
    try:
        out = await tool.price("BTCUSDT")
        assert out["symbol"] == "BTCUSDT"
        assert isinstance(out["price"], float) and out["price"] == 65000.50
        assert out["stale"] is False
    finally:
        await tool._client.aclose()


async def test_funding_parses():
    tool = _make_tool(_handler)
    try:
        out = await tool.funding("BTCUSDT")
        assert out["funding_rate"] == 0.00012
        assert isinstance(out["mark_price"], float)
        assert out["stale"] is False
    finally:
        await tool._client.aclose()


async def test_volume_shape():
    tool = _make_tool(_handler)
    try:
        out = await tool.volume("BTCUSDT")
        assert set(out) >= {"symbol", "volume", "quote_volume", "price_change_pct", "stale"}
        assert out["volume"] == 1234.5 and out["quote_volume"] == 80000000.0
    finally:
        await tool._client.aclose()


async def test_ohlcv_shape():
    tool = _make_tool(_handler)
    try:
        out = await tool.ohlcv("BTCUSDT", "1h", limit=2)
        assert out["symbol"] == "BTCUSDT" and out["interval"] == "1h"
        assert len(out["candles"]) == 2
        c = out["candles"][0]
        assert set(c) == {"open_time", "open", "high", "low", "close", "volume", "close_time"}
        assert c["close"] == 65000.5 and isinstance(c["open_time"], int)
        assert out["stale"] is False
    finally:
        await tool._client.aclose()


async def test_stale_fallback_through_binance():
    state = {"fail": False}

    def flaky(request: httpx.Request) -> httpx.Response:
        if state["fail"]:
            raise httpx.ConnectError("boom")
        return _handler(request)

    # ttl=0 so the second call re-hits the (now-failing) transport
    tool = _make_tool(flaky, snapshot_ttl=0)
    try:
        fresh = await tool.price("BTCUSDT")
        assert fresh["stale"] is False and fresh["price"] == 65000.5

        state["fail"] = True
        fallback = await tool.price("BTCUSDT")
        assert fallback["stale"] is True
        assert fallback["price"] == 65000.5  # last-good value preserved
    finally:
        await tool._client.aclose()


async def test_testnet_order_missing_keys_returns_error_not_raise():
    tool = _make_tool(_handler, api_key="", api_secret="")
    try:
        res = await tool.testnet_order("BTCUSDT", "BUY", 0.001)
        assert res["ok"] is False
        assert res["ack"] is None
        assert "not configured" in res["error"]
    finally:
        await tool._client.aclose()

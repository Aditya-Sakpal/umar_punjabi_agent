"""OnChainTool: mock (no-network) path + real-path three-way cache contract."""
import httpx
import pytest

from app.tools.onchain import OnChainTool


def _raise_on_any(request: httpx.Request) -> httpx.Response:
    raise AssertionError("network call attempted in mock mode!")


async def test_mock_makes_no_network_call_and_is_deterministic():
    # transport raises on ANY request → proves the mock path does no network I/O
    tool = OnChainTool(
        client=httpx.AsyncClient(transport=httpx.MockTransport(_raise_on_any)),
        mock=True,
    )
    try:
        out1 = await tool.metric("BTCUSDT", "exchange_netflow")
        assert out1["mock"] is True
        assert isinstance(out1["value"], float)
        assert out1["trend"] in {"inflow", "outflow", "neutral"}
        assert out1["stale"] is False
        assert -5000.0 <= out1["value"] <= 5000.0

        # deterministic for the same (symbol, metric)
        tool2 = OnChainTool(
            client=httpx.AsyncClient(transport=httpx.MockTransport(_raise_on_any)),
            mock=True,
        )
        out2 = await tool2.metric("BTCUSDT", "exchange_netflow")
        await tool2._client.aclose()
        assert out2["value"] == out1["value"] and out2["trend"] == out1["trend"]
    finally:
        await tool._client.aclose()


GLASSNODE_JSON = [{"t": 1700000000, "v": 1234.5}]


def _real_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=GLASSNODE_JSON)


async def test_real_path_fresh_caches():
    tool = OnChainTool(
        client=httpx.AsyncClient(transport=httpx.MockTransport(_real_handler)),
        mock=False,
        api_key="k",
    )
    try:
        out = await tool.metric("BTCUSDT", "exchange_netflow")
        assert out["mock"] is False and out["value"] == 1234.5
        assert out["stale"] is False
    finally:
        await tool._client.aclose()


async def test_real_path_stale_then_no_snapshot_raises():
    state = {"fail": False}

    def flaky(request):
        if state["fail"]:
            raise httpx.ConnectError("provider down")
        return _real_handler(request)

    tool = OnChainTool(
        client=httpx.AsyncClient(transport=httpx.MockTransport(flaky)),
        mock=False,
        api_key="k",
        ttl=0,
    )
    try:
        fresh = await tool.metric("BTCUSDT", "exchange_netflow")
        assert fresh["stale"] is False
        state["fail"] = True
        fallback = await tool.metric("BTCUSDT", "exchange_netflow")
        assert fallback["stale"] is True and fallback["value"] == 1234.5
    finally:
        await tool._client.aclose()

    # fresh tool, no prior snapshot, provider down → raises
    down = OnChainTool(
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("down")))),
        mock=False,
        api_key="k",
        ttl=0,
    )
    try:
        with pytest.raises(httpx.ConnectError):
            await down.metric("ETHUSDT", "exchange_netflow")
    finally:
        await down._client.aclose()

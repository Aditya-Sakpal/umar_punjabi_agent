"""NewsTool RSS parsing + three-way cache contract with mocked HTTP."""
import httpx
import pytest

from app.tools.news import NewsTool

RSS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Test Feed</title>
  <item>
    <title>Bitcoin rallies past resistance</title>
    <link>https://example.com/btc</link>
    <description>BTC moves higher on strong volume.</description>
    <pubDate>Mon, 23 Jun 2025 10:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Some unrelated equities story</title>
    <link>https://example.com/x</link>
    <description>Stocks did a thing.</description>
    <pubDate>Mon, 23 Jun 2025 09:00:00 GMT</pubDate>
  </item>
</channel></rss>"""


def _rss_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=RSS_XML)


def _tool(handler, **kw) -> NewsTool:
    # api_key="" → RSS-only path
    return NewsTool(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), api_key="", **kw)


async def test_rss_only_filters_by_symbol_and_caches():
    tool = _tool(_rss_handler)
    try:
        out = await tool.headlines("BTCUSDT", limit=5)
        titles = [h["title"] for h in out["headlines"]]
        assert any("Bitcoin" in t for t in titles)
        assert all("equities" not in t for t in titles)  # filtered out
        h = out["headlines"][0]
        assert set(h) == {"title", "source", "ts", "url", "summary"}
        assert out["sources_used"] == {"rss": True, "newsapi": False}
        assert out["stale"] is False
    finally:
        await tool._client.aclose()


async def test_stale_fallback_when_fetcher_raises(monkeypatch):
    tool = _tool(_rss_handler, ttl=0)
    try:
        fresh = await tool.headlines("BTCUSDT", limit=5)
        assert fresh["stale"] is False and fresh["headlines"]

        async def boom(*_a, **_k):
            raise RuntimeError("rss layer down")

        monkeypatch.setattr(tool, "_fetch_rss", boom)
        fallback = await tool.headlines("BTCUSDT", limit=5)
        assert fallback["stale"] is True and fallback["headlines"]
    finally:
        await tool._client.aclose()


async def test_no_snapshot_raises(monkeypatch):
    tool = _tool(_rss_handler, ttl=0)
    try:
        async def boom(*_a, **_k):
            raise RuntimeError("rss layer down")

        monkeypatch.setattr(tool, "_fetch_rss", boom)
        with pytest.raises(RuntimeError, match="rss layer down"):
            await tool.headlines("BTCUSDT", limit=5)
    finally:
        await tool._client.aclose()

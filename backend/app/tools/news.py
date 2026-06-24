"""News tool — merges curated crypto RSS feeds with one News API source.

headlines(symbol, limit) returns [{title, source, ts, url, summary}], cached via
CachedFetchTool (TTL ~10 min) and carrying the ``stale`` flag. RSS alone works when
NEWS_API_KEY is absent. Feeds are downloaded async with httpx and parsed with feedparser
(robust across RSS/Atom + messy date formats); News API adds a JSON source.
"""
import datetime as dt

import feedparser
import httpx

from app.config import settings
from app.tools.base import CachedFetchTool

DEFAULT_TTL = 600.0  # ~10 min

# A couple of curated general crypto feeds; we filter by symbol keywords below.
RSS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
]

# Keep symbol→keyword resolution small for the demo universe.
SYMBOL_KEYWORDS = {
    "BTCUSDT": ["bitcoin", "btc"],
    "ETHUSDT": ["ethereum", "eth", "ether"],
    "SOLUSDT": ["solana", "sol"],
}


def _keywords(symbol: str) -> list[str]:
    return SYMBOL_KEYWORDS.get(symbol.upper(), [symbol.replace("USDT", "").lower()])


def _matches(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(k in low for k in keywords)


def _entry_ts(entry) -> str:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return dt.datetime(*parsed[:6], tzinfo=dt.timezone.utc).isoformat()
    return dt.datetime.now(dt.timezone.utc).isoformat()


class NewsTool(CachedFetchTool):
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        api_key: str | None = None,
        ttl: float = DEFAULT_TTL,
    ) -> None:
        super().__init__()
        self._client = client or httpx.AsyncClient(
            timeout=10.0, follow_redirects=True, headers={"User-Agent": "trading-demo/0.1"}
        )
        self._owns_client = client is None
        self._api_key = api_key if api_key is not None else settings.news_api_key
        self._ttl = ttl

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _fetch_rss(self, keywords: list[str]) -> list[dict]:
        items: list[dict] = []
        for source, url in RSS_FEEDS:
            try:
                r = await self._client.get(url)
                r.raise_for_status()
                feed = feedparser.parse(r.content)
            except Exception:
                continue  # one dead feed must not sink the rest
            for e in feed.entries:
                title = e.get("title", "")
                summary = e.get("summary", "") or e.get("description", "")
                if not title or not _matches(f"{title} {summary}", keywords):
                    continue
                items.append(
                    {
                        "title": title,
                        "source": source,
                        "ts": _entry_ts(e),
                        "url": e.get("link", ""),
                        "summary": summary[:280],
                    }
                )
        return items

    async def _fetch_newsapi(self, keywords: list[str], limit: int) -> list[dict]:
        if not self._api_key:
            return []
        r = await self._client.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": keywords[0],
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": limit,
                "apiKey": self._api_key,
            },
        )
        r.raise_for_status()
        out = []
        for a in r.json().get("articles", []):
            out.append(
                {
                    "title": a.get("title", ""),
                    "source": (a.get("source") or {}).get("name", "NewsAPI"),
                    "ts": a.get("publishedAt", dt.datetime.now(dt.timezone.utc).isoformat()),
                    "url": a.get("url", ""),
                    "summary": (a.get("description") or "")[:280],
                }
            )
        return out

    async def headlines(self, symbol: str, limit: int = 5) -> dict:
        keywords = _keywords(symbol)

        async def fetcher() -> dict:
            rss_items = await self._fetch_rss(keywords)
            api_items: list[dict] = []
            api_used = False
            if self._api_key:
                try:
                    api_items = await self._fetch_newsapi(keywords, limit)
                    api_used = True
                except Exception:
                    api_items = []  # API failure must not sink RSS results
            merged = rss_items + api_items

            # dedupe by title, newest first
            seen: set[str] = set()
            unique: list[dict] = []
            for item in sorted(merged, key=lambda x: x["ts"], reverse=True):
                key = item["title"].strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    unique.append(item)

            return {
                "symbol": symbol,
                "headlines": unique[:limit],
                "sources_used": {"rss": True, "newsapi": api_used},
            }

        return await self.fetch(f"headlines:{symbol}:{limit}", fetcher, self._ttl)

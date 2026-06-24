"""CoinGecko tool — thin async client over the free public API.

market / dominance / meta, all cached via CachedFetchTool (TTL ~60s) and carrying
the ``stale`` flag. Uses COINGECKO_API_KEY (demo-tier header) when present, otherwise
hits the keyless free endpoints.
"""
import httpx

from app.config import settings
from app.tools.base import CachedFetchTool

CG_BASE = "https://api.coingecko.com/api/v3"
DEFAULT_TTL = 60.0

# Small static map for the demo universe — no dynamic resolver (per the blueprint).
SYMBOL_TO_ID = {
    "BTCUSDT": "bitcoin",
    "ETHUSDT": "ethereum",
    "SOLUSDT": "solana",
}


def coingecko_id(symbol: str) -> str:
    try:
        return SYMBOL_TO_ID[symbol.upper()]
    except KeyError:
        raise KeyError(f"no CoinGecko id mapped for symbol {symbol!r}")


class CoinGeckoTool(CachedFetchTool):
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        api_key: str | None = None,
        ttl: float = DEFAULT_TTL,
    ) -> None:
        super().__init__()
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = client is None
        self._api_key = api_key if api_key is not None else settings.coingecko_api_key
        self._ttl = ttl

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _headers(self) -> dict:
        return {"x-cg-demo-api-key": self._api_key} if self._api_key else {}

    async def market(self, symbol: str) -> dict:
        cid = coingecko_id(symbol)

        async def fetcher() -> dict:
            r = await self._client.get(
                f"{CG_BASE}/coins/markets",
                params={"vs_currency": "usd", "ids": cid},
                headers=self._headers(),
            )
            r.raise_for_status()
            d = r.json()[0]
            return {
                "symbol": symbol,
                "id": d["id"],
                "price": float(d["current_price"]),
                "market_cap": float(d["market_cap"]),
                "total_volume": float(d["total_volume"]),
                "price_change_pct_24h": (
                    float(d["price_change_percentage_24h"])
                    if d.get("price_change_percentage_24h") is not None
                    else None
                ),
            }

        return await self.fetch(f"market:{cid}", fetcher, self._ttl)

    async def dominance(self) -> dict:
        async def fetcher() -> dict:
            r = await self._client.get(f"{CG_BASE}/global", headers=self._headers())
            r.raise_for_status()
            mcp = r.json()["data"]["market_cap_percentage"]
            return {
                "btc_dominance": float(mcp.get("btc", 0.0)),
                "eth_dominance": float(mcp.get("eth", 0.0)),
            }

        return await self.fetch("dominance", fetcher, self._ttl)

    async def meta(self, symbol: str) -> dict:
        cid = coingecko_id(symbol)

        async def fetcher() -> dict:
            r = await self._client.get(
                f"{CG_BASE}/coins/{cid}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "false",
                    "community_data": "false",
                    "developer_data": "false",
                },
                headers=self._headers(),
            )
            r.raise_for_status()
            d = r.json()
            return {
                "symbol": symbol,
                "id": d["id"],
                "name": d["name"],
                "asset_symbol": d["symbol"].upper(),
                "market_cap_rank": d.get("market_cap_rank"),
                "categories": [c for c in (d.get("categories") or []) if c][:5],
            }

        return await self.fetch(f"meta:{cid}", fetcher, self._ttl)

"""Binance tool — thin async client over public REST + Spot Testnet for orders.

Read methods (price/ohlcv/funding/volume) go through :class:`CachedFetchTool`, so
each result carries a ``stale`` flag and a dead API degrades to last-good data.
``testnet_order`` is best-effort and never raises into the caller.

No third-party Binance SDK — just httpx, per the blueprint's "thin async clients".
"""
import hashlib
import hmac
import time
import urllib.parse

import httpx

from app.config import settings
from app.tools.base import CachedFetchTool

SPOT_BASE = "https://api.binance.com"
FUTURES_BASE = "https://fapi.binance.com"  # funding rate is a futures concept
TESTNET_BASE = "https://testnet.binance.vision"

# REST snapshot TTL (seconds) per the blueprint's 5–10s guidance.
DEFAULT_SNAPSHOT_TTL = 8.0


class BinanceTool(CachedFetchTool):
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        snapshot_ttl: float = DEFAULT_SNAPSHOT_TTL,
    ) -> None:
        super().__init__()
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = client is None
        self._api_key = api_key if api_key is not None else settings.binance_testnet_api_key
        self._api_secret = (
            api_secret if api_secret is not None else settings.binance_testnet_api_secret
        )
        self._ttl = snapshot_ttl

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # --- cached read endpoints (public REST) ---

    async def price(self, symbol: str) -> dict:
        async def fetcher() -> dict:
            r = await self._client.get(
                f"{SPOT_BASE}/api/v3/ticker/price", params={"symbol": symbol}
            )
            r.raise_for_status()
            d = r.json()
            return {"symbol": d["symbol"], "price": float(d["price"])}

        return await self.fetch(f"price:{symbol}", fetcher, self._ttl)

    async def funding(self, symbol: str) -> dict:
        async def fetcher() -> dict:
            r = await self._client.get(
                f"{FUTURES_BASE}/fapi/v1/premiumIndex", params={"symbol": symbol}
            )
            r.raise_for_status()
            d = r.json()
            return {
                "symbol": d["symbol"],
                "funding_rate": float(d["lastFundingRate"]),
                "mark_price": float(d["markPrice"]),
                "next_funding_time": int(d["nextFundingTime"]),
            }

        return await self.fetch(f"funding:{symbol}", fetcher, self._ttl)

    async def volume(self, symbol: str) -> dict:
        async def fetcher() -> dict:
            r = await self._client.get(
                f"{SPOT_BASE}/api/v3/ticker/24hr", params={"symbol": symbol}
            )
            r.raise_for_status()
            d = r.json()
            return {
                "symbol": d["symbol"],
                "volume": float(d["volume"]),
                "quote_volume": float(d["quoteVolume"]),
                "price_change_pct": float(d["priceChangePercent"]),
            }

        return await self.fetch(f"volume:{symbol}", fetcher, self._ttl)

    async def ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100) -> dict:
        async def fetcher() -> dict:
            r = await self._client.get(
                f"{SPOT_BASE}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
            )
            r.raise_for_status()
            rows = r.json()
            candles = [
                {
                    "open_time": int(c[0]),
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5]),
                    "close_time": int(c[6]),
                }
                for c in rows
            ]
            return {"symbol": symbol, "interval": interval, "candles": candles}

        return await self.fetch(f"ohlcv:{symbol}:{interval}", fetcher, self._ttl)

    # --- order endpoint (Spot Testnet, signed, NOT cached, best-effort) ---

    async def testnet_order(self, symbol: str, side: str, qty: float) -> dict:
        """Fire a MARKET order on Binance Spot Testnet. Best-effort: any failure
        (missing keys, network, API rejection) is captured and returned, never raised."""
        try:
            if not self._api_key or not self._api_secret:
                return {"ok": False, "ack": None, "error": "testnet keys not configured"}

            params = {
                "symbol": symbol,
                "side": side.upper(),
                "type": "MARKET",
                "quantity": qty,
                "timestamp": int(time.time() * 1000),
                "recvWindow": 5000,
            }
            query = urllib.parse.urlencode(params)
            signature = hmac.new(
                self._api_secret.encode(), query.encode(), hashlib.sha256
            ).hexdigest()
            url = f"{TESTNET_BASE}/api/v3/order?{query}&signature={signature}"
            r = await self._client.post(url, headers={"X-MBX-APIKEY": self._api_key})
            r.raise_for_status()
            return {"ok": True, "ack": r.json(), "error": None}
        except Exception as e:
            return {"ok": False, "ack": None, "error": f"{type(e).__name__}: {e}"}

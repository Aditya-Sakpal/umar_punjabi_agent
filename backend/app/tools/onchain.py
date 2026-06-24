"""OnChain tool — one metric, mockable behind the MOCK_ONCHAIN flag.

metric(symbol, name) returns {value, trend, ...} cached via CachedFetchTool and
carrying the ``stale`` flag. When ``mock`` is on (default from settings.mock_onchain),
the fetcher synthesizes a deterministic, sane-magnitude value and performs NO network
I/O. When off, it calls a real provider (Glassnode-style stub) and degrades to
stale/raise on failure like every other read tool.
"""
import hashlib

import httpx

from app.config import settings
from app.tools.base import CachedFetchTool

DEFAULT_TTL = 600.0  # ~10 min
# Real provider (stub) — works only with a paid key; absent today, so it degrades.
GLASSNODE_BASE = "https://api.glassnode.com/v1/metrics"


def _synthetic(symbol: str, name: str) -> dict:
    """Deterministic synthetic on-chain reading (no network)."""
    seed = int(hashlib.sha256(f"{symbol}:{name}".encode()).hexdigest(), 16)
    # netflow-style value in roughly [-5000, 5000] (e.g. coins moving on/off exchanges)
    value = round(((seed % 100_000) / 100_000 * 2 - 1) * 5000, 2)
    if value < -500:
        trend = "outflow"      # leaving exchanges → bullish supply squeeze
    elif value > 500:
        trend = "inflow"       # arriving on exchanges → potential sell pressure
    else:
        trend = "neutral"
    return {"symbol": symbol, "metric": name, "value": value, "trend": trend, "mock": True}


class OnChainTool(CachedFetchTool):
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        mock: bool | None = None,
        api_key: str = "",
        ttl: float = DEFAULT_TTL,
    ) -> None:
        super().__init__()
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = client is None
        self._mock = settings.mock_onchain if mock is None else mock
        self._api_key = api_key
        self._ttl = ttl

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def metric(self, symbol: str, name: str) -> dict:
        async def fetcher() -> dict:
            if self._mock:
                return _synthetic(symbol, name)
            # Real path: attempt the provider; failures propagate to base → stale/raise.
            r = await self._client.get(
                f"{GLASSNODE_BASE}/{name}",
                params={"a": symbol.replace("USDT", ""), "api_key": self._api_key},
            )
            r.raise_for_status()
            data = r.json()
            last = data[-1]
            return {
                "symbol": symbol,
                "metric": name,
                "value": float(last["v"]),
                "trend": "rising" if float(last["v"]) >= 0 else "falling",
                "mock": False,
            }

        return await self.fetch(f"onchain:{symbol}:{name}", fetcher, self._ttl)

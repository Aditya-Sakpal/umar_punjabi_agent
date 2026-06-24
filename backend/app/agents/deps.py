"""Dependency bundle injected into graph nodes — tools + paper engine."""
from __future__ import annotations

from dataclasses import dataclass

from app.db.session import async_session_factory
from app.services.embeddings import SentenceTransformerEmbedder
from app.services.memory import MemoryRecallService
from app.services.paper_engine import PaperEngine
from app.tools.binance import BinanceTool
from app.tools.coingecko import CoinGeckoTool
from app.tools.memory import MemoryTool
from app.tools.news import NewsTool
from app.tools.onchain import OnChainTool


@dataclass
class NodeDeps:
    """Small deps object passed to every ``make_node(deps)`` factory."""

    binance: BinanceTool
    coingecko: CoinGeckoTool
    news: NewsTool
    onchain: OnChainTool
    paper_engine: PaperEngine
    memory: MemoryTool

    async def aclose(self) -> None:
        await self.binance.aclose()
        await self.coingecko.aclose()
        await self.news.aclose()
        await self.onchain.aclose()


async def build_node_deps() -> NodeDeps:
    """Construct a live deps bundle (shared httpx clients inside each tool)."""
    binance = BinanceTool()
    memory_service = MemoryRecallService(async_session_factory, SentenceTransformerEmbedder())
    return NodeDeps(
        binance=binance,
        coingecko=CoinGeckoTool(),
        news=NewsTool(),
        onchain=OnChainTool(),
        paper_engine=PaperEngine(binance),
        memory=MemoryTool(memory_service),
    )

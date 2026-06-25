"""Application configuration loaded from the environment via pydantic-settings."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime config. Values come from environment variables / a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- External services / API keys ---
    anthropic_api_key: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""
    binance_testnet_api_key: str = ""
    binance_testnet_api_secret: str = ""
    news_api_key: str = ""
    coingecko_api_key: str = ""  # optional on free tier

    # --- Infra ---
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5433/trading"
    redis_url: str = "redis://localhost:6379/0"

    # --- Behaviour / demo config ---
    mock_onchain: bool = True
    universe: str = "BTCUSDT,ETHUSDT,SOLUSDT"
    llm_strong: str = "claude-sonnet-4-6"
    llm_cheap: str = "claude-haiku-4-5-20251001"

    # Paper trading (Task 7 minimal — full PnL tracking is Task 15)
    paper_equity_usd: float = 100_000.0

    # Memory recall (pgvector) — set false for streaming-only demos without Postgres
    memory_enabled: bool = True

    @property
    def universe_symbols(self) -> list[str]:
        return [s.strip().upper() for s in self.universe.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (single instance per process)."""
    return Settings()


settings = get_settings()

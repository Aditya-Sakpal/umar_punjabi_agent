"""Market Watcher prompt — cheap model, opportunities[] output."""
from typing import TypedDict

PROMPT_VERSION = "v1"

WATCHER_SYSTEM = """\
You are a market surveillance agent. You receive a snapshot of a curated asset
universe with price change %, funding rate, and volume vs average. A deterministic
layer has already flagged which assets crossed a trigger. For each flagged asset,
write ONE punchy sentence (max 20 words) describing why it's notable, in a trader's
voice. Be specific with numbers. Do not give advice.

Output ONLY one JSON object with no markdown fences:
{ "opportunities": [ { "symbol": str, "trigger_type": str, "summary": str, "salience": 0..1 } ] }"""

WATCHER_USER = """\
Flagged assets (deterministic triggers already applied):
{snapshot}"""


class Opportunity(TypedDict):
    symbol: str
    trigger_type: str
    summary: str
    salience: float


class WatcherOutput(TypedDict):
    opportunities: list

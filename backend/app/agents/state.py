from typing import TypedDict, Annotated, Literal
from operator import add

class Evidence(TypedDict):
    source: str            # "binance" | "coingecko" | "news:<src>" | "onchain:<metric>"
    claim: str
    value: str | float | None
    ts: str

class Signal(TypedDict):
    direction: Literal["BUY", "SELL", "HOLD"]
    confidence: float      # 0..1
    thesis: str
    horizon: Literal["intraday", "swing"]

class RiskAssessment(TypedDict):
    concerns: list[str]
    adjusted_confidence: float
    suggested_size_pct: float
    stop_loss_pct: float
    veto: bool

class Decision(TypedDict):
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float
    size_pct: float
    stop_loss_pct: float
    rationale: str

class SimilarMemory(TypedDict):
    id: str
    symbol: str
    summary: str
    similarity: float
    metadata: dict
    created_at: str

class AgentState(TypedDict, total=False):
    run_id: str
    symbol: str
    trigger: Literal["user", "watcher"]
    revision_count: int
    status: str
    errors: Annotated[list[str], add]
    research_brief: str
    evidence: Annotated[list[Evidence], add]   # reducer: nodes append
    similar_memories: list[SimilarMemory]
    signal: Signal
    risk: RiskAssessment
    decision: Decision
    sim_order: dict

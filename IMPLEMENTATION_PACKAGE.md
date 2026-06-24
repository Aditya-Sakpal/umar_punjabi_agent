# Trading Intelligence Demo — Claude Code Implementation Package

**Audience:** Claude Code (executor).
**Author role:** Technical Lead.
**Goal:** Build, from scratch, a multi-agent trading-intelligence demo that shows autonomous agent collaboration, live streamed reasoning, real-time market data, trade simulation, and full observability.
**Optimize for:** founder wow-factor, visible autonomy, real-time reasoning, fast implementation. **Not** for regulatory/production-scale concerns.

**Stack:** React + TypeScript + Tailwind (FE) · FastAPI + Python 3.11 + async SQLAlchemy + PostgreSQL + Redis (BE) · LangGraph + Anthropic Claude + LangFuse (AI) · Binance + Binance Testnet + CoinGecko + News API (external) · pgvector + sentence-transformers `all-MiniLM-L6-v2` (memory).

**Architecture in one paragraph:** A deterministic *Market Watcher* scans a curated universe on a scheduler and emits "opportunity" cards. On a user click (or opportunity click), a LangGraph deep-chain runs **Research → Signal → Risk → Committee → Execute**. Reasoning tokens stream live to the browser over WebSocket, attributed per-agent. The *Risk* agent adversarially challenges the *Signal*; the *Committee* arbitrates into a final decision. A deterministic *PaperEngine* simulates the trade at the live Binance price (Testnet is a best-effort shadow). Every run is a LangFuse trace and a durable decision-audit record.

---

## 1. Repository Structure

```
trading-demo/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app + lifespan (compile graph, start scheduler, init clients)
│   │   ├── config.py               # pydantic-settings; all env/config
│   │   ├── core/
│   │   │   ├── events.py           # WSEvent envelope schema — single source of truth for streaming
│   │   │   └── logging.py
│   │   ├── api/
│   │   │   ├── deps.py             # FastAPI dependencies (db session, services)
│   │   │   └── routes/
│   │   │       ├── analyze.py      # POST /analyze -> {run_id}; starts a deep-chain run
│   │   │       ├── opportunities.py# GET /opportunities -> watcher feed
│   │   │       ├── portfolio.py    # GET /portfolio -> positions + PnL
│   │   │       ├── runs.py         # GET /runs/{run_id} -> decision audit (trace view)
│   │   │       └── ws.py           # WS /ws/{run_id} -> stream a run's events
│   │   ├── agents/
│   │   │   ├── state.py            # AgentState + typed dicts (Evidence, Signal, RiskAssessment, Decision)
│   │   │   ├── graph.py            # build_graph(), routing functions, compiled-graph factory
│   │   │   ├── nodes/
│   │   │   │   ├── research.py
│   │   │   │   ├── signal.py
│   │   │   │   ├── risk.py
│   │   │   │   ├── committee.py
│   │   │   │   ├── execute.py      # deterministic, no LLM
│   │   │   │   └── watcher.py      # used by scheduler, not in deep graph
│   │   │   ├── prompts/            # one module per agent; prompts are versioned constants
│   │   │   │   ├── research.py
│   │   │   │   ├── signal.py
│   │   │   │   ├── risk.py
│   │   │   │   ├── committee.py
│   │   │   │   └── watcher.py
│   │   │   └── llm.py              # Claude client factory; tagged streaming helpers
│   │   ├── tools/
│   │   │   ├── base.py             # cached-fetch base class (last-good-snapshot fallback)
│   │   │   ├── binance.py          # market data (REST/WS) + testnet order
│   │   │   ├── coingecko.py
│   │   │   ├── news.py             # RSS + News API
│   │   │   ├── onchain.py          # 1 metric, mockable behind flag
│   │   │   ├── memory.py           # pgvector recall + write
│   │   │   └── portfolio.py        # reads PaperEngine state
│   │   ├── services/
│   │   │   ├── orchestrator.py     # runs graph via astream_events; translates -> WSEvent; publishes
│   │   │   ├── event_bus.py        # per-run async pub/sub (Redis pub/sub backend)
│   │   │   ├── paper_engine.py     # deterministic fills, positions, realized/unrealized PnL
│   │   │   ├── translator.py       # LangGraph event -> WSEvent mapping
│   │   │   └── price_stream.py     # Binance WS -> Redis; powers live mark-to-market
│   │   ├── scheduler/
│   │   │   └── watcher_job.py      # AsyncIOScheduler: scan universe, eval triggers, push opportunities
│   │   ├── observability/
│   │   │   └── langfuse.py         # callback-handler factory + decision-audit persistence helper
│   │   └── db/
│   │       ├── session.py          # async engine + session factory
│   │       ├── models.py           # SQLAlchemy models (MVP tables only)
│   │       └── repositories.py     # thin data-access helpers (keep nodes clean)
│   ├── alembic/                    # migrations (incl. pgvector extension + vector column)
│   ├── tests/
│   ├── pyproject.toml
│   ├── .env.example
│   └── docker-compose.yml          # postgres(+pgvector), redis
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                 # layout + routing
│   │   ├── api/
│   │   │   ├── client.ts           # REST helpers
│   │   │   └── ws.ts               # WebSocket client + reconnect
│   │   ├── store/
│   │   │   ├── runStore.ts         # reducer over WSEvents (per-run reasoning state)
│   │   │   └── portfolioStore.ts
│   │   ├── types/
│   │   │   └── events.ts           # WSEvent types — MIRROR of backend core/events.py
│   │   ├── pages/
│   │   │   └── WarRoom.tsx
│   │   └── components/
│   │       ├── OpportunityFeed.tsx
│   │       ├── AgentPanel.tsx      # status chip + streaming token buffer
│   │       ├── EvidenceChips.tsx
│   │       ├── DecisionCard.tsx
│   │       ├── PortfolioPanel.tsx
│   │       └── TraceView.tsx
│   ├── index.html
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── package.json
└── README.md
```

**Folder responsibilities:**
- `agents/` — all LangGraph logic. `state.py` owns the typed contract; `nodes/` are pure async functions `(state) -> partial state`; `prompts/` keeps prompts versioned and out of code; `graph.py` wires nodes + routing.
- `tools/` — thin async API clients. Every external tool extends `base.py` to get caching + last-good-snapshot fallback for free. Nodes call tools; tools never call nodes.
- `services/` — orchestration glue: `orchestrator` drives a run and emits events; `event_bus` decouples producer (graph) from consumers (WS clients); `paper_engine` is the trade source of truth.
- `scheduler/` — the ambient autonomy layer (Market Watcher).
- `observability/` — LangFuse wiring + decision-audit writes.
- `db/` — async SQLAlchemy + pgvector; `repositories.py` keeps SQL out of nodes.
- `core/events.py` ↔ `frontend/src/types/events.ts` — **the streaming contract. These two must stay in sync.**

---

## 2. Backend Implementation Plan

**App composition (`main.py` lifespan):** create async DB engine, Redis client, Binance/CoinGecko/News clients, compile the LangGraph once, start `price_stream` and `AsyncIOScheduler`. Tear down cleanly on shutdown.

**Routers:**
- `POST /analyze {symbol, trigger?}` → creates `run_id`, kicks off `orchestrator.run(run_id, symbol)` as a background task, returns `{run_id}` immediately.
- `WS /ws/{run_id}` → subscribes the socket to the run's event-bus channel, forwards `WSEvent`s as JSON until `done`.
- `GET /opportunities` → current watcher feed from Redis.
- `GET /portfolio` → positions + PnL from PaperEngine.
- `GET /runs/{run_id}` → decision-audit record (powers Trace View).

**Communication flow:**
```
client --POST /analyze--> analyze router --> orchestrator.run() (bg task)
orchestrator --> graph.astream_events() --> translator --> event_bus.publish(run_id, WSEvent)
client --WS /ws/{run_id}--> ws router --subscribe--> event_bus --> socket.send_json(WSEvent)
scheduler --> watcher_job --> redis(opportunity feed) --> GET /opportunities
price_stream(Binance WS) --> redis(prices) --> paper_engine(mark-to-market) --> GET /portfolio
```

**Dependencies (`deps.py`):** `get_db` (async session per request), `get_paper_engine`, `get_event_bus`, `get_settings`. Services are singletons created at startup and stored on `app.state`.

**Schemas (Pydantic) vs Models (SQLAlchemy):** Pydantic schemas live next to routers for request/response; SQLAlchemy models in `db/models.py`. Never return ORM objects directly — map to Pydantic.

---

## 3. LangGraph Implementation

### 3.1 `agents/state.py`

```python
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

class AgentState(TypedDict, total=False):
    run_id: str
    symbol: str
    trigger: Literal["user", "watcher"]
    revision_count: int
    status: str
    errors: Annotated[list[str], add]
    research_brief: str
    evidence: Annotated[list[Evidence], add]   # reducer: nodes append
    signal: Signal
    risk: RiskAssessment
    decision: Decision
    sim_order: dict
```

### 3.2 `agents/graph.py`

```python
from langgraph.graph import StateGraph, START, END
from app.agents.state import AgentState
from app.agents.nodes import research, signal, risk, committee, execute

def route_after_research(s: AgentState) -> str:
    thin = len(s.get("evidence", [])) < 3
    if thin and s.get("revision_count", 0) < 1:
        return "research"          # bounded one-time loop (demo drama)
    return "signal"

def route_after_committee(s: AgentState) -> str:
    return "execute" if s.get("decision", {}).get("action") in ("BUY", "SELL") else "end"

def build_graph(deps) -> "CompiledGraph":
    g = StateGraph(AgentState)
    g.add_node("research",  research.make_node(deps))
    g.add_node("signal",    signal.make_node(deps))
    g.add_node("risk",      risk.make_node(deps))
    g.add_node("committee", committee.make_node(deps))
    g.add_node("execute",   execute.make_node(deps))   # deterministic
    g.add_edge(START, "research")
    g.add_conditional_edges("research", route_after_research,
                            {"signal": "signal", "research": "research"})
    g.add_edge("signal", "risk")
    g.add_edge("risk", "committee")
    g.add_conditional_edges("committee", route_after_committee,
                            {"execute": "execute", "end": END})
    g.add_edge("execute", END)
    return g.compile()
```

### 3.3 Node skeleton (`agents/nodes/risk.py` shown — others identical shape)

```python
from app.agents.llm import structured_llm
from app.agents.prompts.risk import RISK_SYSTEM, RISK_USER
from app.agents.state import AgentState, RiskAssessment

def make_node(deps):
    async def risk_node(state: AgentState) -> dict:
        try:
            funding = await deps.binance.funding(state["symbol"])      # tool call -> on_tool_end evidence
            user = RISK_USER.format(
                signal=state["signal"], evidence=state["evidence"], funding=funding,
            )
            result: RiskAssessment = await structured_llm(
                system=RISK_SYSTEM, user=user, schema=RiskAssessment,
                tags=["agent:risk"],                                   # <-- token attribution
            )
            return {"risk": result, "status": "risk_done",
                    "evidence": [{"source": "binance", "claim": "funding rate",
                                  "value": funding, "ts": _now()}]}
        except Exception as e:
            return {"errors": [f"risk: {e}"], "status": "degraded:risk",
                    "risk": _conservative_default()}
    return risk_node
```

`execute.py` is deterministic: read `decision`, call `paper_engine.simulate()`, return `sim_order`. No LLM.

### 3.4 Streaming integration
Run via `graph.astream_events(state, version="v2", config=cfg)` inside `orchestrator`. `cfg` carries `run_id` metadata, the LangFuse callback, and the `deepchain` tag. Each node's LLM is tagged `agent:<name>` so token deltas are attributable (see Part 7 streaming).

### 3.5 Diagrams

```mermaid
flowchart TD
    START([START]) --> R[Research]
    R -->|evidence thin & revision<1| R
    R -->|enough| S[Signal]
    S --> K[Risk]
    K --> C[Committee]
    C -->|HOLD/veto| E1([END])
    C -->|BUY/SELL| X[Execute · deterministic]
    X --> E2([END])
```
```mermaid
flowchart LR
    SCH[APScheduler] --> W[Watcher] --> T{Trigger?}
    T -->|no| W
    T -->|yes| F[(Redis feed)] --> UI[War Room]
    UI -->|click| O[Orchestrator → deep graph]
```

---

## 4. Agent Prompts

All reasoning agents emit **structured JSON** matching their TypedDict, plus stream natural-language reasoning. Pattern: system prompt sets role + rules + output schema; the model is told to *think out loud, then end with a single JSON block*. The streamed prose is the demo; the JSON is parsed for state.

> Implementation note: use Claude tool-use / JSON mode for the final structured object; stream the reasoning text before it. Keep prompts as versioned constants in `prompts/`.

### Market Watcher (cheap model)
```
SYSTEM:
You are a market surveillance agent. You receive a snapshot of a curated asset
universe with price change %, funding rate, and volume vs average. A deterministic
layer has already flagged which assets crossed a trigger. For each flagged asset,
write ONE punchy sentence (max 20 words) describing why it's notable, in a trader's
voice. Be specific with numbers. Do not give advice. Output JSON:
{ "opportunities": [ { "symbol": str, "trigger_type": str, "summary": str, "salience": 0..1 } ] }
```

### Research Agent (strong model)
```
SYSTEM:
You are a crypto market research analyst. Synthesize the provided data (price action,
news headlines, on-chain metric) into a tight brief for a trading desk.
RULES:
- Ground every claim in the supplied data. Never invent numbers, prices, or headlines.
- Cite the source of each material claim inline (e.g., "funding 0.012% [binance]").
- 4-6 sentences. Note conflicting signals explicitly.
- Think out loud first, then end with ONE JSON block:
{ "research_brief": str, "key_points": [str], "data_quality": "good"|"partial"|"thin" }

USER:
Symbol: {symbol}   Trigger: {trigger}
Price/OHLCV/funding: {market}
Headlines: {news}
On-chain ({metric}): {onchain}
Prior similar setups (memory): {memory}
```

### Signal Agent (strong model)
```
SYSTEM:
You are a directional signal analyst. Using ONLY the research brief and evidence,
form a thesis. Be decisive but calibrated — confidence reflects genuine uncertainty.
RULES:
- Do not fetch new data; reason over what's given.
- Confidence is a real probability, not bravado. A clean setup might be 0.65, not 0.95.
- State the single strongest bull point and the single strongest bear point.
- Think out loud, then ONE JSON block:
{ "direction": "BUY"|"SELL"|"HOLD", "confidence": 0..1, "thesis": str, "horizon": "intraday"|"swing" }

USER:
Research brief: {research_brief}
Evidence: {evidence}
```

### Risk Agent (strong model) — *the highest-value prompt; make it adversarial and specific*
```
SYSTEM:
You are a skeptical risk manager reviewing a colleague's trade signal. Your JOB is to
challenge it, not agree. Find the concrete reasons this could be wrong or dangerous.
RULES:
- Be SPECIFIC and grounded: cite funding rate, volatility, crowding, liquidity, stale data,
  or conflicting evidence. No generic "markets are risky" filler.
- If the signal is crowded (e.g., elevated funding on a long), say so and trim size.
- Adjust confidence DOWN when warranted. Recommend a position size (% of equity) and a
  stop-loss %. Set veto=true only if the trade is clearly unsound.
- You must produce at least one concrete, data-grounded concern.
- Think out loud (this is shown live — make the pushback visible and pointed), then ONE JSON:
{ "concerns": [str], "adjusted_confidence": 0..1, "suggested_size_pct": float,
  "stop_loss_pct": float, "veto": bool }

USER:
Proposed signal: {signal}
Evidence: {evidence}
Funding rate: {funding}   Recent volatility: {vol}
Current portfolio exposure: {portfolio}
```

### Investment Committee (strong model)
```
SYSTEM:
You are the investment committee chair. The Signal analyst is bullish/bearish; the Risk
manager has pushed back. Weigh both and issue ONE final decision with a clear, plain-English
rationale a non-expert founder can follow. Acknowledge the disagreement and how you resolved it.
RULES:
- Respect the Risk manager's veto and size/stop guidance.
- Final confidence and size should reflect the reconciliation, not just the Signal.
- Rationale: 2-3 sentences, plain English, reference the key evidence.
- Think out loud, then ONE JSON:
{ "action": "BUY"|"SELL"|"HOLD", "confidence": 0..1, "size_pct": float,
  "stop_loss_pct": float, "rationale": str }

USER:
Signal: {signal}
Risk assessment: {risk}
Evidence: {evidence}
```

---

## 5. Tool Implementations

**Base pattern (`tools/base.py`):** `async fetch(key, fetcher, ttl)` → return fresh on success and cache it; on failure return last-good snapshot tagged `stale=True`; if no snapshot, raise. All tools inherit this. **A dead API degrades to stale data, never a hang.**

| Tool | Methods | Returns | Source | Rate limits | Caching |
|---|---|---|---|---|---|
| **BinanceTool** | `price(sym)`, `ohlcv(sym,interval)`, `funding(sym)`, `volume(sym)`, `testnet_order(sym,side,qty)` | floats / `[candle]` / order ack | Binance public REST + WS; Testnet for orders | generous (public) | price via WS→Redis; REST snapshots TTL 5–10s; last-good kept; orders uncached |
| **CoinGeckoTool** | `market(sym)`, `dominance()`, `meta(sym)` | `{mcap, vol, dominance,...}` | CoinGecko free | ~30/min | TTL 60s |
| **NewsTool** | `headlines(sym, limit)` | `[{title, source, ts, url, summary}]` | curated RSS + News API | tier-dependent | TTL 5–15 min; pre-warm snapshot for demo |
| **OnChainTool** | `metric(sym, name)` | `{value, trend}` | Glassnode/CryptoQuant (1 metric) | tight free | TTL 5–15 min; **`MOCK_ONCHAIN` flag** returns realistic synthetic value |
| **MemoryTool** | `recall(text, k)`, `remember(obs)` | `[{text, ts, sim}]` | pgvector + local MiniLM embeddings | n/a | DB-backed |
| **PortfolioTool** | `snapshot()` | `{positions, equity, pnl, exposure}` | PaperEngine | n/a | in-memory + DB |

---

## 6. Database Design (MVP tables only)

```python
# db/models.py
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy import String, Float, JSON, DateTime, func
from pgvector.sqlalchemy import Vector
import uuid, datetime as dt

class Base(DeclarativeBase): ...

class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str]
    trigger: Mapped[str]
    status: Mapped[str] = mapped_column(default="running")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class DecisionLog(Base):            # the audit record powering Trace View
    __tablename__ = "decision_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(index=True)
    symbol: Mapped[str]
    evidence: Mapped[list] = mapped_column(JSON)
    signal: Mapped[dict] = mapped_column(JSON)
    risk: Mapped[dict] = mapped_column(JSON)
    decision: Mapped[dict] = mapped_column(JSON)
    model_versions: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Position(Base):
    __tablename__ = "positions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(index=True)
    qty: Mapped[float]
    avg_entry: Mapped[float]
    realized_pnl: Mapped[float] = mapped_column(default=0.0)
    is_open: Mapped[bool] = mapped_column(default=True)

class Fill(Base):
    __tablename__ = "fills"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(index=True)
    symbol: Mapped[str]; side: Mapped[str]; qty: Mapped[float]; price: Mapped[float]
    fee: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Observation(Base):            # semantic market memory
    __tablename__ = "observations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str]
    text: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(384))   # MiniLM dim
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**pgvector:** Alembic migration runs `CREATE EXTENSION IF NOT EXISTS vector;` then creates the `observations.embedding` column + an ivfflat index. `MemoryTool.recall` does `ORDER BY embedding <-> :q LIMIT k`. Embeddings from local `all-MiniLM-L6-v2` (384-dim).

**Migrations:** Alembic, two revisions — (1) base tables, (2) vector extension + column + index.

---

## 7. Streaming System

### 7.1 Event schema (`core/events.py`) — backend source of truth
```python
from typing import TypedDict, Literal
class WSEvent(TypedDict):
    run_id: str
    seq: int
    type: Literal["agent_status","token","evidence","signal_ready","risk_ready",
                  "decision_ready","order_filled","error","done"]
    payload: dict
```
Mirror exactly in `frontend/src/types/events.ts`.

### 7.2 Event bus (`services/event_bus.py`)
Redis pub/sub keyed by `run:{run_id}`. `publish(run_id, event)` and `async subscribe(run_id)` (async generator). A monotonic `seq` per run (Redis `INCR`) guarantees ordering.

### 7.3 Translator (`services/translator.py`) — LangGraph event → WSEvent
| LangGraph event | WSEvent |
|---|---|
| `on_chain_start` (node) | `agent_status` {agent, state: thinking/challenging/deciding} |
| `on_chat_model_stream` (tag `agent:x`) | `token` {agent, delta} |
| `on_tool_end` (news/market) | `evidence` {source, claim, value} |
| node output has `signal`/`risk`/`decision` | `*_ready` {payload} |
| execute output | `order_filled` {symbol, side, qty, price, pnl} |
| exception | `error` {agent, message} |
| graph end | `done` |

Map node name → status verb: research/signal→"thinking", risk→"challenging", committee→"deciding".

### 7.4 Orchestrator loop
```python
async def run(run_id, symbol, trigger="user"):
    state = {"run_id": run_id, "symbol": symbol, "trigger": trigger}
    cfg = {"metadata": {"run_id": run_id}, "tags": ["deepchain"],
           "callbacks": [langfuse_handler(run_id, symbol, trigger)]}
    async for ev in graph.astream_events(state, version="v2", config=cfg):
        out = translate(ev, run_id)         # -> WSEvent | None
        if out: await event_bus.publish(run_id, out)
    await persist_decision_log(run_id)       # audit
    await event_bus.publish(run_id, {"run_id": run_id, "type": "done", "payload": {}})
```

### 7.5 WS router
```python
@router.websocket("/ws/{run_id}")
async def ws(websocket: WebSocket, run_id: str):
    await websocket.accept()
    async for event in event_bus.subscribe(run_id):
        await websocket.send_json(event)
        if event["type"] == "done": break
```

### 7.6 Frontend consumption
`runStore.ts` reduces the ordered event stream: `agent_status`→set panel chip; `token`→append to that agent's buffer; `evidence`→push a chip into Research; `*_ready`→render structured card; `order_filled`→animate portfolio. Sort/apply by `seq`. `ws.ts` handles connect/reconnect with backoff.

---

## 8. Frontend Architecture

**Pages:** `WarRoom` (single-page demo surface).

**Component hierarchy:**
```
App
└── WarRoom
    ├── OpportunityFeed         # GET /opportunities, poll; click -> POST /analyze -> open WS
    ├── ReasoningGrid
    │   ├── AgentPanel(research)   # chip + streaming tokens + EvidenceChips
    │   ├── AgentPanel(signal)
    │   ├── AgentPanel(risk)       # distinct accent color (sell the disagreement)
    │   └── AgentPanel(committee)
    ├── DecisionCard            # final action, confidence, size, stop, rationale, citations
    ├── PortfolioPanel          # positions + live mark-to-market PnL (poll /portfolio)
    └── TraceView (modal)       # GET /runs/{run_id}; node tree + evidence + model versions
```

**State management:** lightweight (Zustand or Context + reducer). `runStore` holds `{ agents: {name: {status, tokens, evidence}}, signal, risk, decision, order }`. `portfolioStore` polls. No heavy framework needed.

**WebSocket integration:** on analyze, `POST /analyze` → get `run_id` → open `WS /ws/{run_id}` → dispatch each event into `runStore`. Close on `done`.

**Tailwind:** status chips (gray=idle, amber=thinking, red=challenging, blue=deciding, green=done); typewriter feel via streaming append; keep it dark "trading terminal" aesthetic.

---

## 9. Implementation Roadmap

**Phase 1 — Spine (Days 1–3).**
Files: `config.py`, `db/*`, `tools/{base,binance,coingecko,news}.py`, `agents/{state,graph,llm}.py`, `agents/nodes/*`, `agents/prompts/*`, `services/paper_engine.py`, `api/routes/analyze.py`.
Output: `POST /analyze` runs the full graph and returns a `Decision` (no streaming/UI).
Testing: unit-test tools with mocked HTTP + cache-fallback; one integration test asserting a run produces a valid `Decision`; snapshot-test each prompt's JSON parses to its TypedDict.

**Phase 2 — Streaming + War Room (Days 4–7).** ← *the wow*
Files: `core/events.py`, `services/{event_bus,translator,orchestrator}.py`, `api/routes/ws.py`, all `frontend/*` (WarRoom, AgentPanel, DecisionCard, stores, ws client).
Output: founder sees Research→Signal→Risk→Committee stream live with per-agent attribution + decision card.
Testing: translator unit tests (LangGraph event fixtures → WSEvent); WS e2e with a scripted run; verify token attribution per agent; verify no-dead-air via cache fallback.

**Phase 3 — Autonomy + Memory + Trade-sim polish (Days 8–10).**
Files: `scheduler/watcher_job.py`, `agents/nodes/watcher.py`, `services/price_stream.py`, `tools/{memory,portfolio,onchain}.py`, `api/routes/{opportunities,portfolio}.py`, `OpportunityFeed.tsx`, `PortfolioPanel.tsx`, Alembic vector migration.
Output: watcher auto-surfaces opportunities; live mark-to-market PnL; pgvector recall; Testnet shadow order.
Testing: watcher trigger logic unit tests (deterministic); PaperEngine PnL math tests; memory recall returns nearest neighbors; mock-onchain flag verified.

**Phase 4 — Observability + resilience + rehearsal (Days 11–14).**
Files: `observability/langfuse.py`, `api/routes/runs.py`, `TraceView.tsx`, fallback snapshots, README + demo script.
Output: every run traced in LangFuse; Trace View screen; all dead-air paths eliminated; rehearsed 5-min storyline.
Testing: assert decision-audit row written per run; chaos-test (kill each API → degraded, not crash); full dry-run rehearsal checklist.

---

## 10. Claude Code Execution Package

Tasks are ordered by dependency; each is small, independently executable, and testable.

**Task 1 — Scaffold & infra**
Objective: monorepo skeleton + docker-compose (postgres+pgvector, redis) + `pyproject`, `.env.example`, FastAPI hello-world with lifespan stub.
Files: `backend/pyproject.toml`, `backend/.env.example`, `backend/docker-compose.yml`, `backend/app/main.py`, `backend/app/config.py`.
Acceptance: `docker compose up` brings up PG+Redis; `GET /health` returns 200; settings load from env.

**Task 2 — DB models + migrations**
Objective: SQLAlchemy models (Part 6) + async session + Alembic with pgvector extension migration.
Files: `db/session.py`, `db/models.py`, `alembic/*`.
Acceptance: `alembic upgrade head` creates all tables + `vector` extension + `observations.embedding`; a smoke insert/select on each table passes.

**Task 3 — Tool base + Binance tool**
Objective: cached-fetch base with last-good-snapshot fallback; Binance price/ohlcv/funding/volume + testnet order.
Files: `tools/base.py`, `tools/binance.py`.
Acceptance: unit tests with mocked HTTP: fresh fetch caches; simulated failure returns `stale=True`; funding/price parse correctly.

**Task 4 — CoinGecko + News + OnChain tools**
Objective: remaining read tools; OnChain behind `MOCK_ONCHAIN`.
Files: `tools/coingecko.py`, `tools/news.py`, `tools/onchain.py`.
Acceptance: each returns its schema; News merges RSS+API; mock flag yields realistic synthetic on-chain value; all degrade to stale on failure.

**Task 5 — LLM client + AgentState**
Objective: Claude client factory with tagged streaming + structured-output helper; typed state.
Files: `agents/llm.py`, `agents/state.py`.
Acceptance: `structured_llm(schema=...)` returns a dict matching the TypedDict; streaming helper emits deltas carrying the `agent:*` tag.

**Task 6 — Agent prompts**
Objective: the five prompts (Part 4) as versioned constants.
Files: `agents/prompts/*.py`.
Acceptance: each prompt's instructed JSON shape parses to its TypedDict on a sample input; Risk prompt always yields ≥1 concrete concern on a sample.

**Task 7 — Nodes (research, signal, risk, committee, execute)**
Objective: implement all nodes; execute is deterministic via PaperEngine stub.
Files: `agents/nodes/*.py`, `services/paper_engine.py` (minimal).
Acceptance: each node returns only its owned keys; failure path returns `errors` + degraded status, never raises.

**Task 8 — Graph + routing**
Objective: assemble graph with bounded research loop + committee gate (Part 3).
Files: `agents/graph.py`.
Acceptance: graph compiles; a mocked run reaches `execute` on BUY and `END` on HOLD; research loop fires at most once.

**Task 9 — /analyze (non-streaming)**
Objective: route that runs the graph to completion and returns the `Decision`.
Files: `api/routes/analyze.py`, `api/deps.py`.
Acceptance: `POST /analyze {symbol:"BTCUSDT"}` returns a valid `Decision` JSON; **Phase 1 done.**

**Task 10 — Event schema + event bus**
Objective: `WSEvent` + Redis pub/sub bus with monotonic `seq`.
Files: `core/events.py`, `services/event_bus.py`.
Acceptance: publish→subscribe round-trips ordered events; `seq` strictly increases per run.

**Task 11 — Translator**
Objective: map LangGraph `astream_events` → `WSEvent` (Part 7.3).
Files: `services/translator.py`.
Acceptance: fixture LangGraph events produce expected WSEvents; tokens carry correct agent; tool-end → evidence.

**Task 12 — Orchestrator + WS route**
Objective: run graph via `astream_events`, publish events; WS forwards them; persist decision log.
Files: `services/orchestrator.py`, `api/routes/ws.py`, `observability/langfuse.py` (handler stub ok).
Acceptance: WS client receives ordered stream ending in `done`; a `DecisionLog` row is written.

**Task 13 — Frontend scaffold + types + ws client**
Objective: Vite React+TS+Tailwind; `events.ts` mirrors backend; ws client w/ reconnect; stores.
Files: `frontend/*` base, `src/types/events.ts`, `src/api/ws.ts`, `src/store/runStore.ts`.
Acceptance: app builds; connecting to a live `run_id` populates the store from real events.

**Task 14 — War Room UI (AgentPanels + DecisionCard)**
Objective: reasoning grid with per-agent streaming, evidence chips, decision card; Risk panel accented.
Files: `pages/WarRoom.tsx`, `components/{AgentPanel,EvidenceChips,DecisionCard}.tsx`.
Acceptance: on analyze, four panels stream live with correct attribution; decision card renders; **Phase 2 done.**

**Task 15 — Price stream + PaperEngine PnL**
Objective: Binance WS → Redis prices; PaperEngine fills at live price + slippage/fee; realized/unrealized PnL.
Files: `services/price_stream.py`, `services/paper_engine.py` (complete), `tools/portfolio.py`.
Acceptance: simulate BUY→SELL yields correct realized PnL; open position marks live; Testnet shadow fired but never awaited as dependency.

**Task 16 — Portfolio route + panel**
Objective: `GET /portfolio` + live-ticking panel.
Files: `api/routes/portfolio.py`, `components/PortfolioPanel.tsx`, `store/portfolioStore.ts`.
Acceptance: panel shows positions + PnL updating as price moves.

**Task 17 — Market Watcher + scheduler + opportunity feed**
Objective: AsyncIOScheduler scans universe, deterministic triggers, cheap-LLM summaries → Redis feed; `GET /opportunities`; `OpportunityFeed` UI; click → analyze.
Files: `scheduler/watcher_job.py`, `agents/nodes/watcher.py`, `api/routes/opportunities.py`, `components/OpportunityFeed.tsx`.
Acceptance: with a forced trigger, an opportunity card appears within one scan; clicking it starts a deep run; **Phase 3 autonomy demoable.**

**Task 18 — Memory (pgvector recall)**
Objective: local MiniLM embeddings; `MemoryTool.recall/remember`; wire recall into Research, write observation after Committee.
Files: `tools/memory.py`, embedding util.
Acceptance: after seeding observations, recall returns nearest neighbors; Research brief references a prior setup when relevant; **Phase 3 done.**

**Task 19 — LangFuse traces + decision audit + Trace View**
Objective: real LangFuse callback (trace=run, spans=nodes/tools, generations=LLM); `GET /runs/{run_id}`; Trace View modal.
Files: `observability/langfuse.py` (complete), `api/routes/runs.py`, `components/TraceView.tsx`.
Acceptance: each run shows a node/tool/token span tree in LangFuse; Trace View renders evidence + agent outputs + model versions for a run.

**Task 20 — Resilience pass + demo rehearsal kit**
Objective: pre-warm caches; kill-API chaos checks; README with run instructions + 5-min demo script + dead-air checklist.
Files: fallback snapshot loaders, `README.md`, `DEMO_SCRIPT.md`.
Acceptance: killing each external API mid-run degrades gracefully (stale data, no crash, no spinner-of-death); full dry run completes the storyline; **Phase 4 done.**

---

### Build order summary
Tasks 1–9 = Phase 1 (spine) · 10–14 = Phase 2 (streaming + UI, the wow) · 15–18 = Phase 3 (autonomy/memory/sim) · 19–20 = Phase 4 (observability + resilience).

### The two non-negotiables (where most demos fail)
1. **Per-agent token attribution** (Tasks 5, 11, 14) — without the `agent:*` tag flowing end-to-end, four agents look like one chatbot.
2. **The Risk Agent's adversarial prompt** (Task 6) — the disagreement-and-resolution beat is the whole demo; it must produce specific, data-grounded pushback, not generic hedging.

### Env vars (`.env.example`)
```
ANTHROPIC_API_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=
BINANCE_TESTNET_API_KEY=
BINANCE_TESTNET_API_SECRET=
NEWS_API_KEY=
COINGECKO_API_KEY=            # optional on free tier
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/trading
REDIS_URL=redis://localhost:6379/0
MOCK_ONCHAIN=true
UNIVERSE=BTCUSDT,ETHUSDT,SOLUSDT
LLM_STRONG=claude-sonnet-4-6
LLM_CHEAP=claude-haiku-4-5-20251001
```

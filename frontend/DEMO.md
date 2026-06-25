# War Room — Founder Demo Script

## Prerequisites

1. **Backend** (terminal 1):
   ```bash
   cd backend
   docker compose up -d
   uv run alembic upgrade head
   uv run uvicorn app.main:app --reload --port 8000
   ```

2. **Frontend** (terminal 2):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. Open **http://localhost:5173**

## Demo flow (5 minutes)

1. **Intro** — "This is the War Room. One screen, live multi-agent debate."

2. **Select asset** — Choose `BTCUSDT` (or ETH/SOL).

3. **Click Analyze** — Point out:
   - Run status flips to **Live**
   - Research panel starts **Thinking...** with streaming tokens
   - Evidence chips appear (Binance funding, price, etc.)
   - Market snapshot updates from evidence

4. **Signal agent** — Thesis streams token-by-token.

5. **Risk agent** (orange accent) — **Challenging...** — adversarial reasoning visible.

6. **Committee** — **Deciding...** then Final Recommendation card:
   ```
   BUY · 55% confidence
   Reasoning: ...
   ```

7. **Portfolio** — If BUY/SELL, simulated fill appears in Paper Portfolio.

8. **Second run** — Change symbol, run again to show multiple concurrent-capable UX (reset between runs).

## What to highlight

- Agents are **attributed** (per-panel streaming)
- Risk **disagrees** visibly (orange panel)
- Decision is **separate** from raw tokens (structured card)
- Backend is **real** LangGraph + WebSocket, not mocked UI

## Troubleshooting

| Issue | Fix |
|-------|-----|
| WS connection failed | Ensure backend on :8000, Redis up |
| No tokens | Set `ANTHROPIC_API_KEY` in `backend/.env` |
| CORS errors | Backend includes localhost:5173 CORS |
| Empty evidence | Binance/network; graph degrades gracefully |

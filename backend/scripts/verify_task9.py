"""Live verification for Task 9 — POST /analyze.

Run:  uv run python scripts/verify_task9.py
Requires ANTHROPIC_API_KEY (live graph run on /analyze).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient

from app.agents.graph import graph_info
from app.config import settings
from app.main import create_app


def _section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def main() -> int:
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return 1
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    info = graph_info()
    print("graph_info:", json.dumps(info, indent=2)[:800], "...")

    app = create_app()
    with TestClient(app) as client:
        _section("INVALID SYMBOL (expected 422)")
        bad = client.post("/analyze", json={"symbol": "DOGEUSDT"})
        print("status:", bad.status_code)
        print(json.dumps(bad.json(), indent=2))

        _section("LIVE POST /analyze — BTCUSDT")
        live = client.post("/analyze", json={"symbol": "BTCUSDT"})
        print("status:", live.status_code)
        body = live.json()
        print(json.dumps(body, indent=2))

        _section("OPENAPI")
        oa = client.get("/openapi.json").json()
        print("/analyze present:", "/analyze" in oa.get("paths", {}))
        print("response model:", oa["paths"]["/analyze"]["post"]["responses"]["200"])

        _section("CURL EXAMPLE")
        print(
            'curl -s -X POST http://localhost:8000/analyze \\\n'
            '  -H "Content-Type: application/json" \\\n'
            '  -d \'{"symbol": "BTCUSDT"}\' | jq'
        )

    if bad.status_code != 422:
        return 1
    if live.status_code != 200:
        return 1
    if "decision" not in body or "run_id" not in body:
        return 1
    action = body["decision"]["action"]
    if action in ("BUY", "SELL"):
        if not body.get("sim_order", {}).get("filled"):
            print("FAIL: BUY/SELL without filled sim_order")
            return 1
    elif action == "HOLD":
        if body.get("sim_order"):
            print("FAIL: HOLD should not include sim_order")
            return 1

    print("\nALL TASK 9 ACCEPTANCE CRITERIA PASSED")
    print("(BUY/HOLD routing also covered by tests/test_analyze.py with mocked runner)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

const DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"];

export function apiBase(): string {
  const env = import.meta.env.VITE_API_URL?.trim();
  if (env) return env.replace(/\/$/, "");
  return "/api";
}

export function wsBase(): string {
  const env = import.meta.env.VITE_API_URL?.trim();
  if (env) {
    const url = new URL(env);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return url.origin;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
}

export function universeSymbols(): string[] {
  return DEFAULT_SYMBOLS;
}

export async function startStreamRun(symbol: string): Promise<{ run_id: string }> {
  const res = await fetch(`${apiBase()}/analyze/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.message ?? `Analyze failed (${res.status})`);
  }
  return res.json();
}

export function runWebSocketUrl(runId: string): string {
  if (import.meta.env.DEV && !import.meta.env.VITE_API_URL?.trim()) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/ws/runs/${runId}`;
  }
  const base = wsBase();
  return `${base}/ws/runs/${runId}`;
}

import { describe, expect, it, vi } from "vitest";
import { connectRunWebSocket } from "../api/ws";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    this.onclose?.();
  }

  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}

describe("connectRunWebSocket", () => {
  it("forwards parsed events and closes on done", () => {
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    const events: unknown[] = [];
    let closeReason = "";

    connectRunWebSocket({
      runId: "abc",
      onEvent: (e) => events.push(e),
      onClose: (r) => {
        closeReason = r;
      },
    });

    const ws = MockWebSocket.instances.at(-1)!;
    expect(ws.url).toContain("/ws/runs/abc");

    ws.emit({ run_id: "abc", seq: 1, type: "token", payload: { agent: "research", delta: "Hi" } });
    ws.emit({ run_id: "abc", seq: 2, type: "done", payload: { status: "completed" } });

    expect(events).toHaveLength(2);
    expect(closeReason).toBe("done");
    vi.unstubAllGlobals();
  });
});

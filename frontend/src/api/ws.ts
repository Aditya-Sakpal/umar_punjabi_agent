import type { WSEvent } from "../types/events";
import { runWebSocketUrl } from "./client";

export type WsCloseReason = "done" | "error" | "manual";

export interface RunWebSocketOptions {
  runId: string;
  onEvent: (event: WSEvent) => void;
  onClose?: (reason: WsCloseReason) => void;
  onError?: (error: Event) => void;
}

export function connectRunWebSocket({
  runId,
  onEvent,
  onClose,
  onError,
}: RunWebSocketOptions): WebSocket {
  const url = runWebSocketUrl(runId);
  const ws = new WebSocket(url);
  let settled = false;

  const finish = (reason: WsCloseReason) => {
    if (settled) return;
    settled = true;
    onClose?.(reason);
  };

  ws.onmessage = (msg) => {
    try {
      const event = JSON.parse(msg.data as string) as WSEvent;
      onEvent(event);
      if (event.type === "done") {
        const status = event.payload?.status;
        finish(status === "failed" ? "error" : "done");
        ws.close();
      }
    } catch {
      onError?.(new Event("parse_error"));
    }
  };

  ws.onerror = (ev) => onError?.(ev);
  ws.onclose = () => finish("manual");

  return ws;
}

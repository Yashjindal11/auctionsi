export type Json = Record<string, unknown>;

const KEY_STORAGE = "auctionsi-api-key";

export function apiKey(): string {
  return localStorage.getItem(KEY_STORAGE) ?? "";
}

export function setApiKey(value: string): void {
  if (value) localStorage.setItem(KEY_STORAGE, value);
  else localStorage.removeItem(KEY_STORAGE);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

export async function api<T = Json>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  const key = apiKey();
  if (key) headers.set("X-API-Key", key);
  const res = await fetch(`/api${path}`, { ...init, headers });
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : await res.text();
  if (!res.ok) throw new ApiError(res.status, (body as Json)?.detail ?? body);
  return body as T;
}

export const post = <T = Json>(path: string, data: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(data) });

export const remove = (path: string) => api<string>(path, { method: "DELETE" });

export type StreamState = "connecting" | "live" | "reconnecting" | "unauthorized" | "closed";

type SocketLike = Pick<WebSocket, "send" | "close"> & {
  onopen: ((ev: Event) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
};

export const AUTH_FAILED = 4401;
const MAX_BACKOFF_MS = 30_000;

/** Live market events with reconnects (exponential backoff). The API key is sent as
 * the first message, never in the URL. Returns a function that stops the stream. */
export function subscribeEvents(
  onEvent: (event: Json) => void,
  onState: (state: StreamState) => void,
  open: (url: string) => SocketLike = (url) => new WebSocket(url),
  schedule: (fn: () => void, ms: number) => unknown = (fn, ms) => setTimeout(fn, ms),
): () => void {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}/api/events`;
  let socket: SocketLike | null = null;
  let attempt = 0;
  let stopped = false;

  const connect = () => {
    onState(attempt === 0 ? "connecting" : "reconnecting");
    const ws = open(url);
    socket = ws;
    ws.onopen = () => {
      const key = apiKey();
      if (key) ws.send(JSON.stringify({ type: "auth", key }));
      attempt = 0;
      onState("live");
    };
    ws.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(String(msg.data)) as Json);
      } catch {
        // A malformed frame is skipped; the stream itself stays usable.
      }
    };
    ws.onclose = (ev) => {
      if (stopped) return;
      if (ev.code === AUTH_FAILED) {
        onState("unauthorized");
        return;
      }
      attempt += 1;
      onState("reconnecting");
      schedule(() => !stopped && connect(), Math.min(MAX_BACKOFF_MS, 500 * 2 ** attempt));
    };
  };

  connect();
  return () => {
    stopped = true;
    socket?.close();
    onState("closed");
  };
}

export function fmt(value: unknown, digits = 4): string {
  if (value === null || value === undefined) return "–";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return String(value);
    if (value === 0) return "0";
    if (Number.isInteger(value)) return value.toLocaleString();
    return Number(value.toPrecision(digits)).toLocaleString(undefined, { maximumFractionDigits: 6 });
  }
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

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

export function eventsSocket(): WebSocket {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const key = apiKey();
  const query = key ? `?key=${encodeURIComponent(key)}` : "";
  return new WebSocket(`${proto}://${location.host}/api/events${query}`);
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

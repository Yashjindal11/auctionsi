import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, apiKey, AUTH_FAILED, fmt, post, remove, setApiKey, subscribeEvents, type StreamState } from "../src/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("fmt", () => {
  it.each([
    [null, "–"],
    [undefined, "–"],
    [0, "0"],
    [-0, "0"],
    [1234, "1,234"],
    [0.123456789, "0.1235"],
    [Number.POSITIVE_INFINITY, "Infinity"],
    [true, "yes"],
    [false, "no"],
    ["text", "text"],
  ])("formats %s as %s", (value, expected) => {
    expect(fmt(value)).toBe(expected);
  });

  it("respects the significant-digit argument", () => {
    expect(fmt(3.14159, 2)).toBe("3.1");
  });
});

describe("api key storage", () => {
  it("stores and clears the key", () => {
    setApiKey("k1");
    expect(apiKey()).toBe("k1");
    setApiKey("");
    expect(apiKey()).toBe("");
    expect(localStorage.getItem("auctionsi-api-key")).toBeNull();
  });
});

describe("api", () => {
  it("sends the key and JSON body, and parses JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    setApiKey("secret");
    expect(await post("/tasks", { task_type: "x" })).toEqual({ ok: 1 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/tasks");
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"task_type":"x"}');
    expect(init.headers.get("X-API-Key")).toBe("secret");
    expect(init.headers.get("Content-Type")).toBe("application/json");
  });

  it("omits the key header when no key is set", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);
    await api("/agents");
    expect(fetchMock.mock.calls[0][1].headers.has("X-API-Key")).toBe(false);
    expect(fetchMock.mock.calls[0][1].headers.has("Content-Type")).toBe(false);
  });

  it("raises ApiError with the server detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "agent x is not registered" }, 404)));
    const err = await api("/agents/x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(404);
    expect((err as ApiError).message).toBe("agent x is not registered");
  });

  it("serialises structured error details", async () => {
    const detail = { rejected: [{ code: "duplicate_bid" }] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail }, 422)));
    const err = (await api("/auctions/a/bids").catch((e: unknown) => e)) as ApiError;
    expect(err.detail).toEqual(detail);
    expect(err.message).toContain("duplicate_bid");
  });

  it("handles empty 204 responses for DELETE", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await remove("/agents/a")).toBe("");
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
  });
});

class FakeSocket {
  static all: FakeSocket[] = [];
  sent: string[] = [];
  closed = false;
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  constructor(public url: string) {
    FakeSocket.all.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.closed = true;
  }
  open() {
    this.onopen?.(new Event("open"));
  }
  message(data: string) {
    this.onmessage?.(new MessageEvent("message", { data }));
  }
  drop(code = 1006) {
    this.onclose?.(new CloseEvent("close", { code }));
  }
}

function stream() {
  FakeSocket.all = [];
  const events: unknown[] = [];
  const states: StreamState[] = [];
  const timers: { fn: () => void; ms: number }[] = [];
  const stop = subscribeEvents(
    (e) => events.push(e),
    (s) => states.push(s),
    (url) => new FakeSocket(url),
    (fn, ms) => timers.push({ fn, ms }),
  );
  return { events, states, timers, stop };
}

describe("subscribeEvents", () => {
  it("connects without a key in the URL and authenticates by first message", () => {
    setApiKey("s3cret");
    const { states } = stream();
    const ws = FakeSocket.all[0];
    expect(ws.url).toBe(`ws://${location.host}/api/events`);
    ws.open();
    expect(JSON.parse(ws.sent[0])).toEqual({ type: "auth", key: "s3cret" });
    expect(states).toEqual(["connecting", "live"]);
  });

  it("sends nothing on open without a key", () => {
    stream();
    FakeSocket.all[0].open();
    expect(FakeSocket.all[0].sent).toEqual([]);
  });

  it("delivers parsed events and skips malformed frames", () => {
    const { events } = stream();
    const ws = FakeSocket.all[0];
    ws.open();
    ws.message('{"seq":1,"type":"TaskCreated"}');
    ws.message("not json");
    ws.message('{"seq":2,"type":"AuctionOpened"}');
    expect(events).toEqual([
      { seq: 1, type: "TaskCreated" },
      { seq: 2, type: "AuctionOpened" },
    ]);
  });

  it("reconnects with exponential backoff and resets after a successful open", () => {
    const { timers, states } = stream();
    FakeSocket.all[0].drop();
    expect(timers.map((t) => t.ms)).toEqual([1000]);
    timers[0].fn();
    FakeSocket.all[1].drop();
    expect(timers.map((t) => t.ms)).toEqual([1000, 2000]);
    timers[1].fn();
    FakeSocket.all[2].open();
    FakeSocket.all[2].drop();
    expect(timers[2].ms).toBe(1000);
    expect(states).toContain("reconnecting");
  });

  it("caps the backoff at 30 seconds", () => {
    const { timers } = stream();
    for (let i = 0; i < 10; i++) {
      FakeSocket.all[i].drop();
      timers[i].fn();
    }
    expect(Math.max(...timers.map((t) => t.ms))).toBe(30_000);
  });

  it("stops on an authentication failure instead of retrying", () => {
    const { timers, states } = stream();
    FakeSocket.all[0].drop(AUTH_FAILED);
    expect(timers).toEqual([]);
    expect(states.at(-1)).toBe("unauthorized");
  });

  it("stop() closes the socket and cancels pending reconnects", () => {
    const { timers, states, stop } = stream();
    FakeSocket.all[0].drop();
    stop();
    expect(FakeSocket.all[0].closed).toBe(true);
    timers[0].fn();
    expect(FakeSocket.all).toHaveLength(1);
    expect(states.at(-1)).toBe("closed");
  });
});

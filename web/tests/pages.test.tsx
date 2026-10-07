import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { AgentDetail, Agents } from "../src/pages/Agents";
import { Live, Simulate } from "../src/pages/Research";

type Route = (init: RequestInit) => unknown;

function mockApi(routes: Record<string, Route | unknown>) {
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const key = `${init.method ?? "GET"} ${url}`;
    if (!(key in routes)) return new Response(JSON.stringify({ detail: `no route ${key}` }), { status: 404, headers: { "content-type": "application/json" } });
    const route = routes[key];
    const body = typeof route === "function" ? (route as Route)(init) : route;
    if (body instanceof Response) return body;
    return new Response(JSON.stringify(body), { headers: { "content-type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const AGENT = { agent_id: "agent-a", kind: "simulated", capabilities: [{ name: "sql" }], max_concurrent_tasks: 1, available: true };

beforeEach(() => {
  location.hash = "";
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("App routing", () => {
  it("renders the page for the hash and marks the active nav link", async () => {
    mockApi({ "GET /api/agents": [AGENT] });
    location.hash = "#/agents";
    render(<App />);
    expect(await screen.findByText("agent-a")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Agents" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Overview" }).hasAttribute("aria-current")).toBe(false);
  });

  it("stores the API key typed in the header", () => {
    mockApi({ "GET /api/status": { detail: "x" }, "GET /api/auctions?limit=10": [] });
    render(<App />);
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "k" } });
    expect(localStorage.getItem("auctionsi-api-key")).toBe("k");
  });
});

describe("Agents", () => {
  it("navigates to an agent on row click", async () => {
    mockApi({ "GET /api/agents": [AGENT] });
    const go = vi.fn();
    render(<Agents go={go} />);
    fireEvent.click(await screen.findByText("agent-a"));
    expect(go).toHaveBeenCalledWith("/agents/agent-a");
  });

  it("reports invalid JSON without calling the API", async () => {
    const fetchMock = mockApi({ "GET /api/agents": [] });
    render(<Agents go={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Agent spec (JSON)"), { target: { value: "{nope" } });
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    expect(await screen.findByText("The spec is not valid JSON.")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("registers an agent and reloads the list", async () => {
    let registered = false;
    mockApi({
      "GET /api/agents": () => (registered ? [AGENT] : []),
      "POST /api/agents": () => {
        registered = true;
        return AGENT;
      },
    });
    render(<Agents go={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    expect(await screen.findByText("agent-a")).toBeTruthy();
  });

  it("shows the server's validation error", async () => {
    mockApi({
      "GET /api/agents": [],
      "POST /api/agents": () => new Response(JSON.stringify({ detail: "unknown agent kind 'rpc'" }), { status: 422, headers: { "content-type": "application/json" } }),
    });
    render(<Agents go={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    expect(await screen.findByText("unknown agent kind 'rpc'")).toBeTruthy();
  });
});

describe("AgentDetail", () => {
  const detail = {
    agent: { ...AGENT, version: "1", metadata: {} },
    reputation: { overall: { observations: 3, success_rate: 1 }, by_task_type: { sql: { observations: 3, success_rate: 1 } } },
    bids: [{ auction_id: "auction-1", price: 0.4 }],
    fulfilled_contracts: 3,
  };

  it("shows reputation and bid history", async () => {
    mockApi({ "GET /api/agents/agent-a": detail });
    render(<AgentDetail id="agent-a" go={vi.fn()} />);
    expect(await screen.findByText("Bid history (1) · 3 contracts fulfilled")).toBeTruthy();
    expect(screen.getByText("auction-1")).toBeTruthy();
  });

  it("removes the agent after confirmation", async () => {
    const fetchMock = mockApi({
      "GET /api/agents/agent-a": detail,
      "DELETE /api/agents/agent-a": () => new Response(null, { status: 204 }),
    });
    vi.stubGlobal("confirm", () => true);
    const go = vi.fn();
    render(<AgentDetail id="agent-a" go={go} />);
    fireEvent.click(await screen.findByRole("button", { name: "Remove agent" }));
    await waitFor(() => expect(go).toHaveBeenCalledWith("/agents"));
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(true);
  });

  it("does nothing when removal is not confirmed", async () => {
    const fetchMock = mockApi({ "GET /api/agents/agent-a": detail });
    vi.stubGlobal("confirm", () => false);
    render(<AgentDetail id="agent-a" go={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Remove agent" }));
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
  });

  it("shows a load error", async () => {
    mockApi({});
    render(<AgentDetail id="ghost" go={vi.fn()} />);
    expect(await screen.findByText("no route GET /api/agents/ghost")).toBeTruthy();
  });
});

describe("Simulate", () => {
  const plugins = { mechanisms: ["first_price_reverse", "forward"], policies: ["lowest_price"], strategies: ["cost_plus"] };

  it("validates the task count before calling the API", async () => {
    const fetchMock = mockApi({ "GET /api/plugins": plugins });
    render(<Simulate />);
    fireEvent.change(screen.getByLabelText("Tasks"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    expect(await screen.findByText(/Tasks must be a whole number/)).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/simulate")).toBe(false);
  });

  it("hides mechanisms that need special tasks", async () => {
    mockApi({ "GET /api/plugins": plugins });
    render(<Simulate />);
    expect(await screen.findByRole("option", { name: "first_price_reverse" })).toBeTruthy();
    expect(screen.queryByRole("option", { name: "forward" })).toBeNull();
  });

  it("runs a simulation and shows metrics", async () => {
    mockApi({
      "GET /api/plugins": plugins,
      "POST /api/simulate": {
        metrics: { completion_rate: 0.9, total_cost: 2, average_quality: 0.8, hhi: 0.1, opportunity_rate: 0.5 },
        performance: { auctions_per_second: 1234.4 },
        market_share: [{ agent_id: "agent-1", wins: 3 }],
        winning_prices: [0.1, 0.2],
        quality_vs_cost: [{ cost: 0.1, quality: 0.9 }],
        hhi_over_time: [0.2, 0.1],
      },
    });
    render(<Simulate />);
    fireEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    expect(await screen.findByText("All metrics")).toBeTruthy();
    expect(screen.getByText("1,234")).toBeTruthy();
    expect(screen.getByRole("img", { name: "market share" })).toBeTruthy();
  });
});

describe("Live", () => {
  class FakeSocket {
    static last: FakeSocket;
    onopen: (() => void) | null = null;
    onclose: ((ev: { code: number }) => void) | null = null;
    onmessage: ((ev: { data: string }) => void) | null = null;
    constructor() {
      FakeSocket.last = this;
    }
    send() {}
    close() {}
  }

  it("streams events, pauses, and reports auth failure", async () => {
    vi.stubGlobal("WebSocket", FakeSocket);
    const go = vi.fn();
    render(<Live go={go} />);
    const ws = FakeSocket.last;
    ws.onopen?.();
    expect(await screen.findByText("Live events · live")).toBeTruthy();
    ws.onmessage?.({ data: '{"seq":1,"type":"TaskCreated","auction_id":"auction-9","agent_id":null}' });
    fireEvent.click(await screen.findByText("TaskCreated"));
    expect(go).toHaveBeenCalledWith("/auctions/auction-9");

    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    ws.onmessage?.({ data: '{"seq":2,"type":"AuctionOpened","auction_id":null,"agent_id":null}' });
    expect(screen.queryByText("AuctionOpened")).toBeNull();
    expect(screen.getByRole("button", { name: "Resume" })).toBeTruthy();

    ws.onclose?.({ code: 4401 });
    expect(await screen.findByText(/API key was rejected/)).toBeTruthy();
  });
});

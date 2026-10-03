import { useEffect, useRef, useState } from "react";
import { eventsSocket, fmt, post } from "../api";
import { BarChart, Histogram, Line, Scatter } from "../charts";
import { useApi } from "../hooks";
import { Button, Card, ErrorNote, Field, inputCls, Stat, Table } from "../ui";

type EventRow = { seq: number; type: string; timestamp: number; auction_id: string | null; agent_id: string | null };

export function Live({ go }: { go: (to: string) => void }) {
  const [events, setEvents] = useState<EventRow[]>([]);
  const [state, setState] = useState("connecting");
  const paused = useRef(false);
  const [isPaused, setPaused] = useState(false);
  useEffect(() => {
    const ws = eventsSocket();
    ws.onopen = () => setState("live");
    ws.onclose = () => setState("disconnected");
    ws.onmessage = (msg) => {
      if (paused.current) return;
      setEvents((prev) => [JSON.parse(msg.data) as EventRow, ...prev].slice(0, 300));
    };
    return () => ws.close();
  }, []);
  return (
    <Card
      title={`Live events · ${state}`}
      actions={
        <Button variant="plain" onClick={() => { paused.current = !paused.current; setPaused(paused.current); }}>
          {isPaused ? "Resume" : "Pause"}
        </Button>
      }
    >
      <p className="mb-3 text-xs text-stone-500">Events stream here as auctions run (submit a task from the overview or the API).</p>
      <Table
        rows={events}
        onRow={(r) => r.auction_id && go(`/auctions/${r.auction_id}`)}
        columns={[
          { key: "seq", label: "#", align: "right" },
          { key: "type", label: "Event" },
          { key: "auction_id", label: "Auction", render: (r) => <span className="font-mono text-xs">{r.auction_id ?? ""}</span> },
          { key: "agent_id", label: "Agent", render: (r) => <span className="font-mono text-xs">{r.agent_id ?? ""}</span> },
        ]}
        empty="Waiting for events…"
      />
    </Card>
  );
}

type Plugins = { mechanisms: string[]; policies: string[]; strategies: string[] };
type SimResult = {
  metrics: Record<string, number | null>;
  performance: Record<string, number>;
  market_share: { agent_id: string; wins: number }[];
  winning_prices: number[];
  quality_vs_cost: { cost: number; quality: number }[];
  hhi_over_time: number[];
};

const RUN_SIZES = [10, 100, 1000];

export function Simulate() {
  const plugins = useApi<Plugins>("/plugins");
  const [form, setForm] = useState({ agents: 100, tasks: 1000, seed: 42, mechanism: "first_price_reverse", policy: "lowest_price", strategy: "cost_plus" });
  const [result, setResult] = useState<SimResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await post<SimResult>("/simulate", form));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const select = (key: "mechanism" | "policy" | "strategy", options: string[] = []) => (
    <select className={inputCls} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })}>
      {options.map((o) => <option key={o}>{o}</option>)}
    </select>
  );
  const m = result?.metrics;
  return (
    <div className="space-y-5">
      <Card title="Simulate a market">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
          <Field label="Agents">
            <select className={inputCls} value={form.agents} onChange={(e) => setForm({ ...form, agents: Number(e.target.value) })}>
              {RUN_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </Field>
          <Field label="Tasks"><input className={inputCls} type="number" min={1} max={20000} value={form.tasks} onChange={(e) => setForm({ ...form, tasks: Number(e.target.value) })} /></Field>
          <Field label="Seed"><input className={inputCls} type="number" value={form.seed} onChange={(e) => setForm({ ...form, seed: Number(e.target.value) })} /></Field>
          <Field label="Mechanism">{select("mechanism", plugins.data?.mechanisms.filter((n) => !["forward", "bundle_reverse", "capacity"].includes(n)))}</Field>
          <Field label="Policy">{select("policy", plugins.data?.policies)}</Field>
          <Field label="Bidder strategy">{select("strategy", plugins.data?.strategies)}</Field>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button onClick={run} disabled={busy}>{busy ? "Simulating…" : "Run simulation"}</Button>
          <span className="text-xs text-stone-500">Synthetic agents and tasks; same seed, same result. Nothing is saved.</span>
        </div>
        <div className="mt-3"><ErrorNote error={error} /></div>
      </Card>
      {m && result && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
            <Stat label="Completion" value={m.completion_rate} />
            <Stat label="Total cost" value={m.total_cost} />
            <Stat label="Avg quality" value={m.average_quality} />
            <Stat label="HHI" value={m.hhi} hint="concentration of wins" />
            <Stat label="Agent utilisation" value={m.opportunity_rate} hint="share of agents that won" />
            <Stat label="Auctions / s" value={Math.round(result.performance.auctions_per_second)} />
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card title="Market share (top 20 by wins)">
              <BarChart label="market share" data={result.market_share.map((r) => ({ label: r.agent_id, value: r.wins }))} />
            </Card>
            <Card title="Winning prices">
              <Histogram label="winning prices" values={result.winning_prices} />
            </Card>
            <Card title="Quality vs buyer cost">
              <Scatter label="quality vs cost" points={result.quality_vs_cost.map((p) => ({ x: p.cost, y: p.quality }))} />
            </Card>
            <Card title="Concentration over time (HHI)">
              <Line label="hhi over time" values={result.hhi_over_time} />
            </Card>
          </div>
          <Card title="All metrics">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm md:grid-cols-3">
              {Object.entries(m).map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-stone-100 py-0.5">
                  <dt className="text-stone-500">{k}</dt>
                  <dd className="num">{fmt(v)}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </>
      )}
    </div>
  );
}

type CalRow = Record<string, unknown> & { agent_id: string };
type Bin = Record<string, unknown> & { claimed_from: number; claimed_to: number };

export function Calibration({ go }: { go: (to: string) => void }) {
  const { data, error } = useApi<{ agents: CalRow[]; bins: Bin[] }>("/calibration");
  return (
    <div className="space-y-5">
      <ErrorNote error={error} />
      <Card title="Claimed vs delivered, per agent">
        <p className="mb-2 text-xs text-stone-500">Positive bias means an agent promises more quality than it delivers.</p>
        <Table
          rows={data?.agents ?? []}
          onRow={(r) => go(`/agents/${r.agent_id}`)}
          columns={[
            { key: "agent_id", label: "Agent", render: (r) => <span className="font-mono text-xs">{r.agent_id}</span> },
            { key: "observations", label: "n", align: "right" },
            { key: "success_rate", label: "Success", align: "right" },
            { key: "claimed_quality", label: "Claimed q", align: "right" },
            { key: "delivered_quality", label: "Delivered q", align: "right" },
            { key: "quality_bias", label: "Bias", align: "right" },
            { key: "latency_relative_error", label: "Latency error", align: "right" },
          ]}
          empty="No completed contracts yet."
        />
      </Card>
      <Card title="Delivered quality by claimed quality">
        <Table
          rows={(data?.bins ?? []).map((b) => ({ ...b, range: `${fmt(b.claimed_from)}–${fmt(b.claimed_to)}` }))}
          columns={[
            { key: "range", label: "Claimed" },
            { key: "count", label: "n", align: "right" },
            { key: "mean_claimed", label: "Mean claimed", align: "right" },
            { key: "mean_delivered", label: "Mean delivered", align: "right" },
          ]}
        />
      </Card>
    </div>
  );
}

export function Experiments() {
  const { data, error } = useApi<{ experiment_id: string; name: string; saved_at: number }[]>("/experiments");
  return (
    <Card title="Experiments">
      <ErrorNote error={error} />
      <p className="mb-2 text-xs text-stone-500">
        Saved with <span className="font-mono">auctionsi experiment run CONFIG --save-db</span>. Full reports are written next to the results.
      </p>
      <Table
        rows={(data ?? []).map((e) => ({ ...e, saved: new Date(e.saved_at * 1000).toLocaleString() }))}
        columns={[
          { key: "experiment_id", label: "Experiment" },
          { key: "name", label: "Name" },
          { key: "saved", label: "Saved" },
        ]}
        empty="No experiments saved to this database."
      />
    </Card>
  );
}

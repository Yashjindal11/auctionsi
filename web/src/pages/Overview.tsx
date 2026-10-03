import { useState } from "react";
import { post, type Json } from "../api";
import { useApi } from "../hooks";
import { Button, Card, ErrorNote, Field, inputCls, Stat, StatusBadge, Table } from "../ui";

type Status = {
  counts: Record<string, number>;
  auctions_by_status: Record<string, number>;
  total_buyer_cost: number;
  agents_registered: number;
  counters: Record<string, number>;
  mechanism: { name: string };
  policy: { name: string };
};

type AuctionRow = { auction_id: string; task_id: string; status: string; mechanism: string };

export function Overview({ go }: { go: (to: string) => void }) {
  const status = useApi<Status>("/status");
  const auctions = useApi<AuctionRow[]>("/auctions?limit=10");
  const s = status.data;
  return (
    <div className="space-y-5">
      <ErrorNote error={status.error} />
      {s && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat label="Agents" value={s.agents_registered} />
            <Stat label="Tasks" value={s.counts.tasks} />
            <Stat label="Auctions" value={s.counts.auctions} />
            <Stat label="Settled" value={s.auctions_by_status.settled ?? 0} />
            <Stat label="Buyer cost" value={s.total_buyer_cost} />
          </div>
          <p className="text-sm text-stone-600">
            Mechanism <span className="font-mono">{s.mechanism.name}</span>, selection policy{" "}
            <span className="font-mono">{s.policy.name}</span>.
          </p>
        </>
      )}
      <div className="grid gap-5 lg:grid-cols-2">
        <SubmitTask onDone={(id) => go(`/auctions/${id}`)} />
        <Card title="Recent auctions">
          <Table
            rows={auctions.data ?? []}
            onRow={(r) => go(`/auctions/${r.auction_id}`)}
            columns={[
              { key: "auction_id", label: "Auction", render: (r) => <span className="font-mono text-xs">{r.auction_id}</span> },
              { key: "task_id", label: "Task" },
              { key: "mechanism", label: "Mechanism" },
              { key: "status", label: "Status", render: (r) => <StatusBadge status={r.status} /> },
            ]}
            empty="No auctions yet. Register agents, then submit a task."
          />
        </Card>
      </div>
    </div>
  );
}

function SubmitTask({ onDone }: { onDone: (auctionId: string) => void }) {
  const [form, setForm] = useState({ task_type: "data_analysis", budget: "0.1", deadline: "60", min_quality: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  const num = (v: string) => (v.trim() === "" ? null : Number(v));
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await post<Json>("/tasks", {
        task_type: form.task_type,
        budget: num(form.budget),
        deadline: num(form.deadline),
        min_quality: num(form.min_quality),
      });
      onDone(String(res.auction_id));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Submit a task">
      <form onSubmit={submit} className="grid grid-cols-2 gap-3">
        <Field label="Task type"><input className={inputCls} value={form.task_type} onChange={set("task_type")} /></Field>
        <Field label="Budget"><input className={inputCls} value={form.budget} onChange={set("budget")} inputMode="decimal" /></Field>
        <Field label="Deadline (s)"><input className={inputCls} value={form.deadline} onChange={set("deadline")} inputMode="decimal" /></Field>
        <Field label="Min quality"><input className={inputCls} value={form.min_quality} onChange={set("min_quality")} placeholder="optional" /></Field>
        <div className="col-span-2 flex items-center gap-3">
          <Button type="submit" disabled={busy}>{busy ? "Running auction…" : "Run auction"}</Button>
          <span className="text-xs text-stone-500">Runs the full lifecycle with the registered agents.</span>
        </div>
        <div className="col-span-2"><ErrorNote error={error} /></div>
      </form>
    </Card>
  );
}

import { useState } from "react";
import { api, fmt, post, type Json } from "../api";
import { ContributionBars } from "../charts";
import { useApi } from "../hooks";
import { Button, Card, ErrorNote, StatusBadge, Table } from "../ui";

type AuctionRow = { auction_id: string; task_id: string; status: string; mechanism: string; parent_auction_id: string | null };

const STATUSES = ["", "settled", "failed", "no_bids", "cancelled", "bid_collection"];

export function Auctions({ go }: { go: (to: string) => void }) {
  const [status, setStatus] = useState("");
  const auctions = useApi<AuctionRow[]>(`/auctions${status ? `?status=${status}` : ""}`);
  return (
    <Card
      title="Auctions"
      actions={
        <select className="rounded border border-stone-300 px-2 py-1 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s || "all statuses"}</option>
          ))}
        </select>
      }
    >
      <ErrorNote error={auctions.error} />
      <Table
        rows={auctions.data ?? []}
        onRow={(r) => go(`/auctions/${r.auction_id}`)}
        columns={[
          { key: "auction_id", label: "Auction", render: (r) => <span className="font-mono text-xs">{r.auction_id}</span> },
          { key: "task_id", label: "Task" },
          { key: "mechanism", label: "Mechanism" },
          { key: "status", label: "Status", render: (r) => <StatusBadge status={r.status} /> },
          { key: "parent_auction_id", label: "Re-opened from" },
        ]}
      />
    </Card>
  );
}

type Bid = Json & { agent_id: string; price: number };
type Scored = { agent_id: string; price: number; score: number; contributions: Record<string, number>; effective_cost: number | null; details: Json };
type Award = { agent_id: string; payment: number; payment_rule: string; quantity?: number | null };
type Check = { name: string; passed: boolean; score: number; detail: string };
type ContractOutcome = {
  contract: Json & { contract_id: string; agent_id: string; attempt: number; agreed_price: number; payment_price: number; status: string };
  execution: Json & { success: boolean; latency: number; error: string | null };
  verification: { passed: boolean; quality_score: number; verifier: string; checks: Check[] };
  settlement: Json & { payment: number; penalty: number; bonus: number; refund: number; buyer_cost: number; reason: string; unit: string };
};
type AuctionDetailData = {
  auction_id: string;
  status: string;
  mechanism: string;
  task: Json & { task_id: string; task_type: string };
  participants: string[];
  excluded?: Record<string, string[]>;
  bids: Bid[];
  rejected: { agent_id: string; reasons: { code: string; message: string }[] }[];
  outcome?: { ranking: Scored[]; awards: Award[]; notes: string[] } | null;
  contracts?: ContractOutcome[];
  child_auction_id?: string | null;
  trace: string[];
};

export function AuctionDetail({ id, go }: { id: string; go: (to: string) => void }) {
  const { data, error, reload } = useApi<AuctionDetailData>(`/auctions/${id}`);
  const [replay, setReplay] = useState<Json | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <p className="text-sm text-stone-500">Loading…</p>;
  const t = data.task;
  const open = data.status === "bid_collection";
  async function act(path: string) {
    try {
      await post(path, {});
      reload();
    } catch (err) {
      setActionError((err as Error).message);
    }
  }
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-mono text-lg font-semibold">{data.auction_id}</h1>
          <p className="text-sm text-stone-600">
            {data.mechanism} · task <span className="font-mono">{t.task_id}</span> ({t.task_type}) · budget {fmt(t.budget)} · deadline{" "}
            {fmt(t.deadline)}s · min quality {fmt(t.min_quality)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={data.status} />
          {open && <Button onClick={() => act(`/auctions/${id}/close`)}>Close &amp; award</Button>}
          {open && <Button variant="plain" onClick={() => act(`/auctions/${id}/cancel`)}>Cancel</Button>}
          {!open && (
            <Button variant="plain" onClick={() => api<Json>(`/auctions/${id}/replay`).then(setReplay, (e: Error) => setActionError(e.message))}>
              Replay decision
            </Button>
          )}
        </div>
      </div>
      <ErrorNote error={actionError} />
      {replay && (
        <p className={`rounded border px-3 py-2 text-sm ${replay.matches ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}>
          {replay.matches
            ? "Replay re-derived the same winners and payments from the recorded bids and reputation snapshot."
            : `Replay mismatch: ${JSON.stringify(replay.differences ?? replay.notes)}`}
        </p>
      )}
      {data.child_auction_id && (
        <p className="text-sm">
          Re-opened as{" "}
          <button className="font-mono text-accent underline" onClick={() => go(`/auctions/${data.child_auction_id}`)}>{data.child_auction_id}</button>
        </p>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={`Participants (${data.participants.length})`}>
          <p className="font-mono text-xs leading-6">{data.participants.join(", ") || "none"}</p>
          {data.excluded && Object.keys(data.excluded).length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-stone-600">
              {Object.entries(data.excluded).map(([a, r]) => (
                <li key={a}><span className="font-mono">{a}</span>: {r.join("; ")}</li>
              ))}
            </ul>
          )}
        </Card>
        <Card title={`Rejected bids (${data.rejected.length})`}>
          {data.rejected.length ? (
            <ul className="space-y-1 text-xs">
              {data.rejected.map((r, i) => (
                <li key={i}><span className="font-mono">{r.agent_id}</span>: {r.reasons.map((x) => `${x.code} – ${x.message}`).join("; ")}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-stone-500">None.</p>
          )}
        </Card>
      </div>

      <Card title={`Bids (${data.bids.length})`}>
        <Table
          rows={data.bids}
          onRow={(r) => go(`/agents/${r.agent_id}`)}
          columns={[
            { key: "agent_id", label: "Agent", render: (r) => <span className="font-mono text-xs">{r.agent_id}</span> },
            { key: "price", label: "Price", align: "right" },
            { key: "estimated_latency", label: "Latency", align: "right" },
            { key: "estimated_quality", label: "Quality (claimed)", align: "right" },
            { key: "confidence", label: "Confidence", align: "right" },
            { key: "revision", label: "Revision", align: "right" },
          ]}
        />
      </Card>

      {data.outcome && data.outcome.ranking.length > 0 && (
        <Card title="Why the winner won">
          <div className="mb-3 space-y-1 text-sm">
            {data.outcome.awards.map((a) => (
              <p key={a.agent_id}>
                <span className="font-mono font-semibold">{a.agent_id}</span> paid {fmt(a.payment)}
                {a.quantity != null && <> for {fmt(a.quantity)} units</>} — {a.payment_rule}
              </p>
            ))}
            {data.outcome.notes.map((n) => (
              <p key={n} className="text-xs text-stone-500">{n}</p>
            ))}
          </div>
          <ol className="space-y-3">
            {data.outcome.ranking.map((s, i) => (
              <li key={s.agent_id} className="rounded border border-stone-100 p-2">
                <div className="mb-1 flex justify-between text-sm">
                  <span>
                    {i + 1}. <span className="font-mono">{s.agent_id}</span> · price {fmt(s.price)}
                    {s.effective_cost != null && <> · effective cost {fmt(s.effective_cost)}</>}
                  </span>
                  <span className="num font-semibold">score {fmt(s.score)}</span>
                </div>
                <ContributionBars contributions={s.contributions} />
              </li>
            ))}
          </ol>
        </Card>
      )}

      {(data.contracts ?? []).map((c) => (
        <Card key={c.contract.contract_id} title={`Contract ${c.contract.contract_id} · ${c.contract.agent_id} · attempt ${c.contract.attempt}`}>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="text-sm">
              <h3 className="mb-1 text-xs font-semibold uppercase text-stone-500">Execution</h3>
              <p>{c.execution.success ? "Delivered" : `Failed: ${c.execution.error}`}</p>
              <p className="num text-stone-600">latency {fmt(c.execution.latency)}s</p>
              <p className="num text-stone-600">agreed {fmt(c.contract.agreed_price)} · payment price {fmt(c.contract.payment_price)}</p>
            </div>
            <div className="text-sm">
              <h3 className="mb-1 text-xs font-semibold uppercase text-stone-500">Verification ({c.verification.verifier})</h3>
              <p>{c.verification.passed ? "Passed" : "Failed"} · quality {fmt(c.verification.quality_score)}</p>
              <ul className="mt-1 space-y-0.5 text-xs">
                {c.verification.checks.map((ch) => (
                  <li key={ch.name} className={ch.passed ? "text-stone-600" : "text-red-700"}>
                    {ch.passed ? "✓" : "✗"} {ch.name} {ch.detail && `– ${ch.detail}`}
                  </li>
                ))}
              </ul>
            </div>
            <div className="text-sm">
              <h3 className="mb-1 text-xs font-semibold uppercase text-stone-500">Settlement</h3>
              <p className="num">payment {fmt(c.settlement.payment)} · penalty {fmt(c.settlement.penalty)} · bonus {fmt(c.settlement.bonus)}</p>
              <p className="num">buyer cost {fmt(c.settlement.buyer_cost)} {c.settlement.unit}</p>
              <p className="text-xs text-stone-500">{c.settlement.reason}</p>
            </div>
          </div>
        </Card>
      ))}

      <Card title="Trace">
        <pre className="overflow-x-auto font-mono text-xs leading-5 text-stone-700">{data.trace.join("\n")}</pre>
      </Card>
    </div>
  );
}

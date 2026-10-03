import { useState } from "react";
import { fmt, post } from "../api";
import { useApi } from "../hooks";
import { Button, Card, ErrorNote, Table } from "../ui";

type AgentRow = {
  agent_id: string;
  kind: string;
  capabilities: { name: string }[];
  max_concurrent_tasks: number;
  available: boolean;
  endpoint?: string;
};

export function Agents({ go }: { go: (to: string) => void }) {
  const agents = useApi<AgentRow[]>("/agents");
  return (
    <div className="space-y-5">
      <ErrorNote error={agents.error} />
      <Card title={`Agents (${agents.data?.length ?? 0})`}>
        <Table
          rows={agents.data ?? []}
          onRow={(r) => go(`/agents/${r.agent_id}`)}
          columns={[
            { key: "agent_id", label: "Agent", render: (r) => <span className="font-mono text-xs">{r.agent_id}</span> },
            { key: "kind", label: "Kind" },
            { key: "capabilities", label: "Capabilities", render: (r) => r.capabilities.map((c) => c.name).join(", ") },
            { key: "max_concurrent_tasks", label: "Capacity", align: "right" },
            { key: "available", label: "Available" },
          ]}
          empty="No agents registered."
        />
      </Card>
      <RegisterAgent onDone={agents.reload} />
    </div>
  );
}

const EXAMPLE = JSON.stringify(
  {
    kind: "simulated",
    agent_id: "agent-new",
    capabilities: ["data_analysis"],
    cost_model: { fixed_cost: 0.03 },
    quality: 0.85,
    reliability: 0.95,
    strategy: "cost_plus",
  },
  null,
  2,
);

function RegisterAgent({ onDone }: { onDone: () => void }) {
  const [text, setText] = useState(EXAMPLE);
  const [error, setError] = useState<string | null>(null);
  async function submit() {
    try {
      await post("/agents", JSON.parse(text));
      setError(null);
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <Card title="Register an agent">
      <p className="mb-2 text-xs text-stone-500">
        A simulated agent spec, or <span className="font-mono">{"{kind: \"http\", agent_id, base_url, capabilities}"}</span> for a remote agent.
      </p>
      <textarea className="h-48 w-full rounded border border-stone-300 p-2 font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="mt-2 flex items-center gap-3">
        <Button onClick={submit}>Register</Button>
        <ErrorNote error={error} />
      </div>
    </Card>
  );
}

type Profile = Record<string, number | null> | null;
type AgentDetailData = {
  agent: AgentRow & { version: string; metadata: Record<string, unknown> };
  reputation: { overall: Profile; by_task_type: Record<string, Profile> };
  bids: { auction_id: string; price: number }[];
  fulfilled_contracts: number;
};

const PROFILE_FIELDS: [string, string][] = [
  ["observations", "Tasks"],
  ["success_rate", "Success rate"],
  ["avg_quality", "Average quality"],
  ["on_time_rate", "On-time rate"],
  ["quality_estimate_bias", "Quality claim bias"],
  ["quality_estimate_error", "Quality claim error"],
  ["latency_estimate_error", "Latency claim error"],
  ["violations", "Violations"],
];

export function AgentDetail({ id, go }: { id: string; go: (to: string) => void }) {
  const { data, error } = useApi<AgentDetailData>(`/agents/${id}`);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <p className="text-sm text-stone-500">Loading…</p>;
  const { agent, reputation } = data;
  const types = Object.entries(reputation.by_task_type);
  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-mono text-lg font-semibold">{agent.agent_id}</h1>
        <p className="text-sm text-stone-600">
          {agent.kind} · capabilities {agent.capabilities.map((c) => c.name).join(", ")} · capacity {agent.max_concurrent_tasks}
          {agent.endpoint && <> · <span className="font-mono">{agent.endpoint}</span></>}
        </p>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Reputation (all task types)">
          {reputation.overall ? (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              {PROFILE_FIELDS.map(([k, label]) => (
                <div key={k} className="contents">
                  <dt className="text-stone-500">{label}</dt>
                  <dd className="num text-right">{fmt(reputation.overall?.[k])}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-stone-500">No completed work yet.</p>
          )}
        </Card>
        <Card title="By task type">
          <Table
            rows={types.map(([t, p]) => ({ task_type: t, ...(p ?? {}) }))}
            columns={[
              { key: "task_type", label: "Task type" },
              { key: "observations", label: "Tasks", align: "right" },
              { key: "success_rate", label: "Success", align: "right" },
              { key: "avg_quality", label: "Quality", align: "right" },
            ]}
            empty="No task-specific history."
          />
        </Card>
      </div>
      <Card title={`Bid history (${data.bids.length}) · ${data.fulfilled_contracts} contracts fulfilled`}>
        <Table
          rows={data.bids}
          onRow={(r) => go(`/auctions/${r.auction_id}`)}
          columns={[
            { key: "auction_id", label: "Auction", render: (r) => <span className="font-mono text-xs">{r.auction_id}</span> },
            { key: "price", label: "Price", align: "right" },
          ]}
          empty="No bids recorded."
        />
      </Card>
    </div>
  );
}

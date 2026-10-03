import { fmt } from "./api";

type Point = { x: number; y: number };

const W = 520;
const H = 200;
const PAD = { l: 44, r: 12, t: 10, b: 28 };

function scale(values: number[], lo: number, hi: number) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return (v: number) => lo + ((v - min) / span) * (hi - lo);
}

function Axis({ yMin, yMax }: { yMin: number; yMax: number }) {
  return (
    <g className="text-[10px]" fill="#78716c">
      <line x1={PAD.l} x2={PAD.l} y1={PAD.t} y2={H - PAD.b} stroke="#d6d3d1" />
      <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} stroke="#d6d3d1" />
      <text x={PAD.l - 4} y={PAD.t + 8} textAnchor="end">{fmt(yMax, 3)}</text>
      <text x={PAD.l - 4} y={H - PAD.b} textAnchor="end">{fmt(yMin, 3)}</text>
    </g>
  );
}

export function BarChart({ data, label }: { data: { label: string; value: number }[]; label: string }) {
  if (!data.length) return <p className="text-sm text-stone-500">No data.</p>;
  const max = Math.max(...data.map((d) => d.value), 0);
  const bw = (W - PAD.l - PAD.r) / data.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={label}>
      <Axis yMin={0} yMax={max} />
      {data.map((d, i) => {
        const h = max ? ((H - PAD.t - PAD.b) * d.value) / max : 0;
        return (
          <g key={d.label}>
            <rect x={PAD.l + i * bw + 2} y={H - PAD.b - h} width={Math.max(bw - 4, 1)} height={h} fill="#0f766e">
              <title>{`${d.label}: ${fmt(d.value)}`}</title>
            </rect>
            {data.length <= 12 && (
              <text x={PAD.l + i * bw + bw / 2} y={H - 10} textAnchor="middle" fontSize="9" fill="#78716c">
                {d.label.length > 10 ? d.label.slice(-8) : d.label}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export function Histogram({ values, bins = 20, label }: { values: number[]; bins?: number; label: string }) {
  if (!values.length) return <p className="text-sm text-stone-500">No data.</p>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = (max - min) / bins || 1;
  const counts = Array.from({ length: bins }, () => 0);
  for (const v of values) counts[Math.min(bins - 1, Math.floor((v - min) / width))]++;
  return (
    <BarChart
      label={label}
      data={counts.map((c, i) => ({ label: fmt(min + i * width, 2), value: c }))}
    />
  );
}

export function Scatter({ points, label }: { points: Point[]; label: string }) {
  if (!points.length) return <p className="text-sm text-stone-500">No data.</p>;
  const sx = scale(points.map((p) => p.x), PAD.l + 4, W - PAD.r);
  const sy = scale(points.map((p) => p.y), H - PAD.b - 4, PAD.t);
  const ys = points.map((p) => p.y);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={label}>
      <Axis yMin={Math.min(...ys)} yMax={Math.max(...ys)} />
      {points.map((p, i) => (
        <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r={2.2} fill="#0f766e" fillOpacity={0.55} />
      ))}
    </svg>
  );
}

export function Line({ values, label }: { values: number[]; label: string }) {
  if (values.length < 2) return <p className="text-sm text-stone-500">Not enough data.</p>;
  const sx = scale(values.map((_, i) => i), PAD.l, W - PAD.r);
  const sy = scale(values, H - PAD.b, PAD.t);
  const d = values.map((v, i) => `${i ? "L" : "M"}${sx(i)},${sy(v)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={label}>
      <Axis yMin={Math.min(...values)} yMax={Math.max(...values)} />
      <path d={d} fill="none" stroke="#0f766e" strokeWidth={1.8} />
    </svg>
  );
}

export function ContributionBars({ contributions }: { contributions: Record<string, number> }) {
  const entries = Object.entries(contributions);
  const max = Math.max(...entries.map(([, v]) => Math.abs(v)), 1e-12);
  return (
    <div className="space-y-1">
      {entries.map(([name, v]) => (
        <div key={name} className="flex items-center gap-2 text-xs">
          <span className="w-28 shrink-0 text-stone-500">{name}</span>
          <div className="relative h-3 flex-1 rounded bg-stone-100">
            <div
              className={`absolute top-0 h-3 rounded ${v >= 0 ? "bg-accent" : "bg-stone-400"}`}
              style={{ width: `${(Math.abs(v) / max) * 100}%` }}
            />
          </div>
          <span className="num w-20 text-right">{v > 0 ? "+" : ""}{fmt(v)}</span>
        </div>
      ))}
    </div>
  );
}

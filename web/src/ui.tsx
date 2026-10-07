import type { ReactNode } from "react";
import { fmt } from "./api";

export function Card({ title, children, actions }: { title?: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="rounded-lg border border-stone-200 bg-white">
      {(title || actions) && (
        <header className="flex items-center justify-between border-b border-stone-100 px-4 py-2.5">
          <h2 className="text-sm font-semibold text-stone-700">{title}</h2>
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: unknown; hint?: string }) {
  return (
    <div className="rounded-lg border border-stone-200 bg-white px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-stone-500">{label}</div>
      <div className="num mt-1 text-xl font-semibold">{fmt(value)}</div>
      {hint && <div className="mt-0.5 text-xs text-stone-500">{hint}</div>}
    </div>
  );
}

export type Column<T> = { key: string; label: string; render?: (row: T) => ReactNode; align?: "right" };

export function Table<T extends Record<string, unknown>>({
  rows,
  columns,
  onRow,
  empty = "Nothing yet.",
}: {
  rows: T[];
  columns: Column<T>[];
  onRow?: (row: T) => void;
  empty?: string;
}) {
  if (!rows.length) return <p className="text-sm text-stone-500">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wide text-stone-500">
            {columns.map((c) => (
              <th key={c.key} className={`px-2 py-2 font-medium ${c.align === "right" ? "text-right" : ""}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              onClick={onRow ? () => onRow(row) : undefined}
              onKeyDown={
                onRow
                  ? (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onRow(row);
                      }
                    }
                  : undefined
              }
              tabIndex={onRow ? 0 : undefined}
              className={`border-b border-stone-100 last:border-0 ${onRow ? "cursor-pointer hover:bg-stone-50 focus:bg-stone-50 focus:outline-none" : ""}`}
            >
              {columns.map((c) => (
                <td key={c.key} className={`px-2 py-1.5 ${c.align === "right" ? "num text-right" : ""}`}>
                  {c.render ? c.render(row) : fmt(row[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  settled: "bg-emerald-50 text-emerald-800 border-emerald-200",
  failed: "bg-red-50 text-red-800 border-red-200",
  no_bids: "bg-amber-50 text-amber-800 border-amber-200",
  cancelled: "bg-stone-100 text-stone-700 border-stone-200",
};

export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] ?? "bg-sky-50 text-sky-800 border-sky-200";
  return <span className={`rounded border px-1.5 py-0.5 text-xs font-medium ${cls}`}>{status}</span>;
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>;
}

export function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  disabled,
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "plain";
  disabled?: boolean;
}) {
  const cls =
    variant === "primary"
      ? "bg-accent text-white hover:opacity-90"
      : "border border-stone-300 bg-white text-stone-700 hover:bg-stone-50";
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`rounded px-3 py-1.5 text-sm font-medium disabled:opacity-50 ${cls}`}>
      {children}
    </button>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-stone-600">
      {label}
      {children}
    </label>
  );
}

export const inputCls = "rounded border border-stone-300 bg-white px-2 py-1.5 text-sm text-stone-900 focus:border-accent focus:outline-none";

import { useState } from "react";
import { apiKey, setApiKey } from "./api";
import { useRoute } from "./hooks";
import { AgentDetail, Agents } from "./pages/Agents";
import { AuctionDetail, Auctions } from "./pages/Auctions";
import { Overview } from "./pages/Overview";
import { Calibration, Experiments, Live, Simulate } from "./pages/Research";

const NAV: [string, string][] = [
  ["/", "Overview"],
  ["/agents", "Agents"],
  ["/auctions", "Auctions"],
  ["/live", "Live"],
  ["/simulate", "Simulate"],
  ["/calibration", "Calibration"],
  ["/experiments", "Experiments"],
];

export function App() {
  const [path, go] = useRoute();
  const [key, setKey] = useState(apiKey());
  const [, section, id] = path.split("/");
  let page;
  if (section === "agents" && id) page = <AgentDetail key={id} id={id} go={go} />;
  else if (section === "agents") page = <Agents go={go} />;
  else if (section === "auctions" && id) page = <AuctionDetail key={id} id={id} go={go} />;
  else if (section === "auctions") page = <Auctions go={go} />;
  else if (section === "live") page = <Live go={go} />;
  else if (section === "simulate") page = <Simulate />;
  else if (section === "calibration") page = <Calibration go={go} />;
  else if (section === "experiments") page = <Experiments />;
  else page = <Overview go={go} />;
  return (
    <div className="min-h-screen">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <a href="#/" className="text-base font-semibold tracking-tight">AuctionSI</a>
          <nav className="flex flex-wrap gap-1 text-sm">
            {NAV.map(([to, label]) => {
              const active = to === "/" ? path === "/" : path.startsWith(to);
              return (
                <a
                  key={to}
                  href={`#${to}`}
                  aria-current={active ? "page" : undefined}
                  className={`rounded px-2 py-1 ${active ? "bg-accent-soft font-medium text-accent" : "text-stone-600 hover:text-stone-900"}`}
                >
                  {label}
                </a>
              );
            })}
          </nav>
          <input
            className="ml-auto w-40 rounded border border-stone-300 px-2 py-1 text-xs"
            type="password"
            aria-label="API key"
            autoComplete="off"
            placeholder="API key (if set)"
            value={key}
            onChange={(e) => { setKey(e.target.value); setApiKey(e.target.value); }}
          />
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{page}</main>
    </div>
  );
}

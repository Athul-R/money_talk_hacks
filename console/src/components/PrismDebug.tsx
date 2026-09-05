/**
 * PRISM debug — the agent's Observe → Improve → Prove trail, built from the
 * same event log we already send as traces + a trajectory.
 */

import { ExternalLink, X } from "lucide-react";
import type { EventRow } from "../lib/types";
import { neutralCopy } from "../lib/format";

const PRISM_URL = "https://prism.blockconvey.com/traces";

export function PrismDebug({
  events, prismOn, onClose,
}: {
  events: EventRow[];
  prismOn: boolean;
  onClose: () => void;
}) {
  const traces = events.filter((e) =>
    ["web_context", "explanation_ready", "run_complete", "axis_selected", "memory_recalled"].includes(e.kind));

  return (
    <aside className="clay-panel flex min-h-0 w-full max-w-[380px] flex-col rounded-[28px] p-5">
      <header className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">PRISM debug</p>
          <p className="mt-0.5 text-[12px] text-muted-foreground">
            {prismOn ? "Traces + trajectory posted to the project." : "Keys off — showing the local trail we would send."}
          </p>
        </div>
        <button type="button" onClick={onClose} className="clay-pill grid h-8 w-8 place-items-center rounded-full">
          <X className="h-3.5 w-3.5" />
        </button>
      </header>
      <ol className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
        {traces.map((e) => (
          <li key={e.id} className="clay-row rounded-2xl px-3.5 py-2.5">
            <div className="text-[10px] font-bold uppercase tracking-wide" style={{ color: "var(--ring-memory)" }}>
              {e.kind.replace("_", " ")}
            </div>
            <div className="mt-0.5 text-[12px] font-semibold">{neutralCopy(e.payload.title)}</div>
            <div className="truncate text-[11px] text-muted-foreground">{neutralCopy(e.payload.detail)}</div>
          </li>
        ))}
      </ol>
      <a href={PRISM_URL} target="_blank" rel="noreferrer"
         className="clay-pill mt-3 flex items-center justify-center gap-2 rounded-full px-4 py-2 text-[12px] font-semibold"
         style={{ color: "var(--ring-memory)" }}>
        Open PRISM traces <ExternalLink className="h-3.5 w-3.5" />
      </a>
    </aside>
  );
}

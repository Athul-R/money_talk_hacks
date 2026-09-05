/**
 * Right column: the audited event stream, replayed beat by beat. Clicking a row
 * jumps the story to that beat and highlights the node that produced it.
 */

import {
  Activity, Boxes, Brain, Check, FileText, Share2, SlidersHorizontal, XCircle, ZoomIn,
} from "lucide-react";
import type { EventRow } from "../lib/types";
import { hhmmss, TAG_TONE } from "../lib/format";

const ICON: Record<string, typeof Check> = {
  router: Share2, z: Activity, drivers: SlidersHorizontal, cluster: Boxes,
  drill: ZoomIn, memory: Brain, explain: FileText, capped: XCircle, ok: Check,
};

export function EventLog({ events, upto, onPick }: {
  events: EventRow[];
  upto: number;
  onPick: (ev: EventRow) => void;
}) {
  const visible = events.filter((e) => e.payload.beat <= upto).reverse();
  return (
    <section className="clay-panel flex min-h-0 flex-col rounded-[28px] p-5">
      <header className="mb-4 flex shrink-0 items-center justify-between gap-4">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Events
        </h2>
        <span className="text-[11px] font-medium text-muted-foreground tabular">
          {visible.length} / {events.length}
        </span>
      </header>
      <ol className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
        {visible.map((e) => {
          const tag = e.payload.tag ?? "router";
          const Icon = ICON[tag] ?? Share2;
          const tone = TAG_TONE[tag] ?? "var(--ring-engine)";
          return (
            <li key={e.id}>
              <button
                type="button"
                onClick={() => onPick(e)}
                className="clay-row animate-row-in flex w-full items-center gap-3 rounded-2xl px-3.5 py-3 text-left"
              >
                <span
                  className="grid h-8 w-8 shrink-0 place-items-center rounded-xl"
                  style={{ background: `color-mix(in oklab, ${tone} 16%, transparent)` }}
                >
                  <Icon className="h-4 w-4" style={{ color: tone }} strokeWidth={2.4} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12.5px] font-semibold text-foreground">
                    {e.payload.title}
                  </span>
                  <span className="block truncate text-[11px] text-muted-foreground">
                    {e.payload.detail}
                  </span>
                </span>
                <span className="tabular shrink-0 font-mono text-[10.5px] text-muted-foreground">
                  {hhmmss(e.at)}
                </span>
              </button>
            </li>
          );
        })}
        {visible.length === 0 && (
          <li className="py-8 text-center text-[12.5px] text-muted-foreground">
            Press play — the engine's audit trail streams here.
          </li>
        )}
      </ol>
    </section>
  );
}

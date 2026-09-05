/**
 * Executive summary — the page leadership sees first. From here they open
 * the closer (how the agent got here) or the PRISM debug trail.
 */

import { Brain, FileText, Network, ScanSearch } from "lucide-react";
import { companyLabel, datasetLabel, fm, pct, share } from "../lib/format";
import type { RunBundle } from "../lib/types";

export function Summary({
  bundle, playing, beat, maxBeat, prismOn, onCloser, onPrism, onMemo,
}: {
  bundle: RunBundle;
  playing: boolean;
  beat: number;
  maxBeat: number;
  prismOn: boolean;
  onCloser: () => void;
  onPrism: () => void;
  onMemo: () => void;
}) {
  const top = bundle.branches.filter((b) => b.depth === 0);
  const done = !playing && beat >= maxBeat;
  const headline = bundle.run.summary_md.split("\n").find((l) => l.trim()) ?? "";

  return (
    <section className="clay-panel mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col overflow-y-auto rounded-[32px] px-8 py-8">
      <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
        {done ? "Executive summary" : "Composing the leadership summary…"}
      </p>
      <h2 className="wordmark mt-2 text-[26px] font-bold tracking-tight">
        {bundle.run.metric} · {bundle.run.period_a} → {bundle.run.period_b}
      </h2>
      <p className="mt-1 text-[13px] text-muted-foreground">
        {companyLabel(bundle.run.company)} · {datasetLabel(bundle.run.dataset)} ·{" "}
        {done ? `${Math.round(bundle.run.explained_share * 100)}% of the move explained`
              : `step ${beat}/${maxBeat}`}
      </p>

      {!done && (
        <div className="mt-4 h-1.5 overflow-hidden rounded-full"
             style={{ background: "color-mix(in oklab, var(--foreground) 8%, transparent)" }}>
          <div className="h-full rounded-full transition-all"
               style={{ width: `${(beat / Math.max(maxBeat, 1)) * 100}%`, background: "var(--ring-active)" }} />
        </div>
      )}

      <p className="mt-6 max-w-3xl text-[15px] leading-relaxed text-foreground/90">
        {done ? headline.replace(/^#+\s*/, "") : "The engine is reconciling the books, ranking the router, and walking the z-bridge. The memo appears when the last claim is tagged."}
      </p>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {top.slice(0, 4).map((b) => (
          <div key={b.id} className="clay-card rounded-[20px] px-4 py-3.5">
            <div className="text-[12.5px] font-semibold">{b.name}</div>
            <div className="tabular mt-1 text-[18px] font-bold"
                 style={{ color: b.state === "capped" ? "var(--ring-down)" : "var(--ring-up)" }}>
              {fm(b.delta_abs)}
            </div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              {pct(b.delta_pct)} · {share(b.share)} of Δ
              {b.state === "capped" ? " · below floor" : ""}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 flex flex-wrap gap-2">
        <button type="button" onClick={onCloser}
                className="clay-pill flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-semibold"
                style={{ color: "var(--ring-engine)" }}>
          <ScanSearch className="h-4 w-4" strokeWidth={2.3} />
          Open the closer — how the agent got here
        </button>
        <button type="button" onClick={onMemo}
                className="clay-pill flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-semibold">
          <FileText className="h-4 w-4" style={{ color: "var(--ring-engine)" }} />
          leadership memo
        </button>
        <button type="button" onClick={onPrism}
                className="clay-pill flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-semibold"
                style={{ color: "var(--ring-memory)" }}>
          <Brain className="h-4 w-4" />
          PRISM debug {prismOn ? "· live" : ""}
        </button>
        <a href="#architecture" className="clay-pill flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-semibold">
          <Network className="h-4 w-4" style={{ color: "var(--ring-engine)" }} />
          methodology
        </a>
      </div>
    </section>
  );
}

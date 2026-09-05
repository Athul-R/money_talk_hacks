/**
 * Architecture board — same clay language as the story graph, but the
 * pipeline itself: Observe → Improve → Prove, plus the engine walk.
 */

import { X } from "lucide-react";

const STEPS = [
  {
    n: "01",
    title: "Load the books",
    tone: "var(--ring-metric)",
    body: "data/given CSVs (SEC · product · geo · user) or an upload. User-segment rows become the transaction grain. Control totals must reconcile before a run starts.",
  },
  {
    n: "02",
    title: "Rank the move",
    tone: "var(--ring-engine)",
    body: "Variance router scores every axis. Lanes are ranked by |Δ$|, never % growth. Graph only grows — a lane is assigned once.",
  },
  {
    n: "03",
    title: "Measure + attribute",
    tone: "var(--ring-active)",
    body: "z-score vs the trailing band. Price / volume / mix / customer bridge. Search uses the clicks × CPC identity; residual is shown, not hidden.",
  },
  {
    n: "04",
    title: "Drill to the floor",
    tone: "var(--ring-drill)",
    body: "Product → user segment → account. Stop at 5% share, 80% explained, or depth 4. Small lanes cap. LLM never does this math.",
  },
  {
    n: "05",
    title: "Narrate + remember",
    tone: "var(--ring-memory)",
    body: "Engine emits evidence JSON. Narrator only rephrases, tagged reported_fact / calculated / commentary / inference. Memory compiles at write, read as plain rows next run.",
  },
  {
    n: "06",
    title: "Observe → Improve → Prove",
    tone: "var(--ring-up)",
    body: "prismtrace-sdk sends one LLM trace per narration and one trajectory per finished run. Missing PRISM keys = no-op; the demo still plays.",
  },
];

export function Architecture({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-[oklch(0.23_0.02_270/0.28)] px-5 py-8 backdrop-blur-[2px]">
      <div className="clay-panel relative flex max-h-[92vh] w-full max-w-[1180px] flex-col overflow-hidden rounded-[32px] p-6">
        <header className="mb-5 flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Delta Ledger · pipeline
            </p>
            <h2 className="wordmark mt-1 text-[22px] font-bold tracking-tight">
              How a run becomes a story
            </h2>
            <p className="mt-1 max-w-2xl text-[12.5px] leading-relaxed text-muted-foreground">
              Deterministic engine first. The graph on the main screen is this
              walk, folded into beats. Mock mode replays a baked walk; live mode
              runs the same walk on <code>data/given</code> (or whatever you upload).
            </p>
          </div>
          <button type="button" onClick={onClose}
                  className="clay-pill grid h-10 w-10 place-items-center rounded-full">
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          <div className="grid gap-3 md:grid-cols-3">
            {STEPS.map((s) => (
              <article key={s.n} className="clay-card rounded-[22px] px-4 py-4">
                <div className="mb-2 flex items-center gap-2">
                  <span className="tabular text-[11px] font-bold" style={{ color: s.tone }}>{s.n}</span>
                  <h3 className="text-[13.5px] font-semibold">{s.title}</h3>
                </div>
                <p className="text-[12px] leading-relaxed text-muted-foreground">{s.body}</p>
              </article>
            ))}
          </div>

          <div className="mt-5 overflow-x-auto rounded-[22px] clay-canvas px-4 py-5">
            <p className="mb-3 text-[10.5px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
              one run, left to right
            </p>
            <div className="flex min-w-[860px] items-stretch gap-2 text-[11px]">
              {[
                ["CSV", "data/given"],
                ["Reconcile", "Σ txn = reported"],
                ["Router", "rank |Δ$|"],
                ["z / bridge", "Search = clicks×CPC"],
                ["Drill", "Cloud → enterprise → US"],
                ["Narrate", "tags only"],
                ["Memory", "compile at write"],
                ["PRISM", "trace + trajectory"],
              ].map(([title, sub], i, arr) => (
                <div key={title} className="flex flex-1 items-center gap-2">
                  <div className="clay-puck flex-1 rounded-2xl px-3 py-2.5 text-center">
                    <div className="font-semibold">{title}</div>
                    <div className="mt-0.5 text-[10px] text-muted-foreground">{sub}</div>
                  </div>
                  {i < arr.length - 1 && (
                    <span className="shrink-0 text-muted-foreground">→</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          <p className="mt-4 text-[11.5px] leading-relaxed text-muted-foreground">
            Hard rules: the LLM never computes; absolute dollars rank branches;
            the graph only grows; memory is compiled at write and read as rows.
            Two demo paths share this picture — <b>mock</b> (Auric fixtures,
            baked beats) and <b>live</b> (Alphabet given CSVs through FastAPI).
          </p>
        </div>
      </div>
    </div>
  );
}

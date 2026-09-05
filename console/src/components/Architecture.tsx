/**
 * Architecture board — same clay language as the story graph, but the
 * pipeline itself: Observe → Improve → Prove, plus the engine walk.
 */

import { X } from "lucide-react";

const STEPS = [
  {
    n: "01",
    title: "Reconcile",
    tone: "var(--ring-metric)",
    body: "Do the books add up? Σ user-segment / txn rows must equal reported SEC totals (0.5% tolerance) before any analysis starts. The Σ puck on the left.",
  },
  {
    n: "02",
    title: "Router",
    tone: "var(--ring-engine)",
    body: "Who owns the move? Scores every axis and ranks lanes by |Δ$| — never % growth. Cloud at +$11B beats a tiny line at +200%. The teal split puck.",
  },
  {
    n: "03",
    title: "Z-bridge",
    tone: "var(--ring-active)",
    body: "Is this unusual vs this lane's own history? z-score against the trailing growth band. |z| ≥ 2 gets the gold flag. The first pip on every lane.",
  },
  {
    n: "04",
    title: "$ bridge + drill",
    tone: "var(--ring-drill)",
    body: "Split the Δ into price / volume / mix / customer, then drill Cloud → enterprise → US until 80% is explained or a lane falls below 5%.",
  },
  {
    n: "05",
    title: "Narrate + remember",
    tone: "var(--ring-memory)",
    body: "Engine emits evidence JSON. Narrator only rephrases, tagged reported_fact / calculated / commentary / inference. Memory compiles at write.",
  },
  {
    n: "06",
    title: "PRISM prove",
    tone: "var(--ring-up)",
    body: "Every narration is a PRISM trace; the finished run is a trajectory. Open PRISM debug in the closer to walk the agent's decisions.",
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
              walk, folded into live steps. Every uploaded ledger follows the
              same evidence path from control totals to executive explanation.
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
            Leaders use the high-level lineage; analysts can open every audit
            step from the same append-only event ledger.
          </p>
        </div>
      </div>
    </div>
  );
}

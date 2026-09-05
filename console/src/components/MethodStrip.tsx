/** One-line glossary so the closer is easy to narrate live. */

const STEPS = [
  { k: "Reconcile", t: "Do the books add up? Σ txn = reported totals.", c: "var(--ring-metric)" },
  { k: "Router", t: "Who owns the move? Ranked by |Δ$|, never %.", c: "var(--ring-engine)" },
  { k: "Z-bridge", t: "Is it unusual vs this lane's own history?", c: "var(--ring-active)" },
  { k: "$ bridge", t: "Price · volume · mix · customer split the Δ.", c: "var(--ring-up)" },
  { k: "Drill", t: "Cloud → enterprise → US until 80% explained.", c: "var(--ring-drill)" },
  { k: "Reconciled", t: "Memo + tagged claims. LLM never did the math.", c: "var(--ring-memory)" },
];

export function MethodStrip() {
  return (
    <ol className="flex shrink-0 gap-2 overflow-x-auto pb-0.5">
      {STEPS.map((s) => (
        <li key={s.k} className="clay-chip flex min-w-[150px] flex-1 flex-col rounded-2xl px-3 py-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.1em]" style={{ color: s.c }}>{s.k}</span>
          <span className="mt-0.5 text-[10.5px] leading-snug text-muted-foreground">{s.t}</span>
        </li>
      ))}
    </ol>
  );
}

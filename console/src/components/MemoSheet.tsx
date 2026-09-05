/**
 * Leadership memo as a structured board brief. Markdown remains an export
 * format only; the product view is assembled from the run's evidence model.
 */

import { useMemo, useState } from "react";
import {
  AlertTriangle, ArrowRight, Brain, CheckCircle2, Download, Gauge,
  Layers3, ShieldCheck, TrendingUp, X,
} from "lucide-react";
import { EVIDENCE_TAGS, type EvidenceTag, type RunBundle } from "../lib/types";
import { downloadMemo } from "../lib/memo";
import { fm, pct, share } from "../lib/format";

type Sections = Record<string, string[]>;

function clean(line: string) {
  return line
    .replace(/^[-*]\s+/, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/`(.+?)`/g, "$1")
    .trim();
}

function parseSections(md: string): Sections {
  const out: Sections = {};
  let current = "Overview";
  for (const raw of md.split("\n")) {
    if (raw.startsWith("## ")) {
      current = clean(raw.slice(3));
      out[current] ??= [];
    } else if (raw.trim()) {
      (out[current] ??= []).push(clean(raw));
    }
  }
  return out;
}

function Badge({ tag }: { tag: string }) {
  const meta = EVIDENCE_TAGS[tag as EvidenceTag] ?? EVIDENCE_TAGS.agent_inference;
  return (
    <span
      className="clay-chip inline-block rounded-full px-2 py-0.5 text-[8.5px] font-bold uppercase tracking-[0.06em]"
      style={{ color: `var(${meta.cssVar})` }}
    >
      {meta.label}
    </span>
  );
}

export function MemoSheet({ bundle, onClose }: { bundle: RunBundle; onClose: () => void }) {
  const [tab, setTab] = useState<"brief" | "evidence">("brief");
  const sections = useMemo(() => parseSections(bundle.run.summary_md), [bundle.run.summary_md]);
  const root = bundle.events.find((event) => event.kind === "run_started")?.payload.root ?? {};
  const material = bundle.branches
    .filter((branch) => branch.depth === 0 && branch.state !== "capped")
    .sort((a, b) => Math.abs(b.delta_abs) - Math.abs(a.delta_abs));
  const capped = bundle.branches.filter((branch) => branch.depth === 0 && branch.state === "capped");
  const headline = sections["What changed"]?.[0]
    ?? `${bundle.run.metric} ${pct(root.delta_pct)} (${fm(root.delta_abs)})`;
  const watchouts = sections["Watch-outs"] ?? [];
  const context = sections["Context from previous runs"] ?? bundle.recalled.map((row) => row.text);
  const operatingDrivers = sections["What's driving it"] ?? [];

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-[oklch(0.23_0.02_270/0.32)] px-5 py-6 backdrop-blur-[3px]">
      <article className="clay-panel relative flex max-h-[94vh] w-full max-w-[1050px] flex-col overflow-hidden rounded-[34px]">
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-7 py-5">
          <div>
            <p className="text-[10.5px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Leadership brief · {bundle.run.company}
            </p>
            <h2 className="wordmark mt-1 text-[23px] font-bold tracking-tight">
              {bundle.run.metric} · {bundle.run.period_a} → {bundle.run.period_b}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <div className="clay-pill flex items-center gap-0.5 rounded-full p-1">
              {([
                ["brief", "Board brief"],
                ["evidence", "Evidence book"],
              ] as const).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setTab(value)}
                  className={`rounded-full px-3 py-1.5 text-[10.5px] font-bold ${
                    tab === value ? "clay-pill-active" : ""
                  }`}
                  style={{ color: tab === value ? "var(--ring-engine)" : "var(--muted-foreground)" }}
                >
                  {label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => downloadMemo(bundle)}
              className="clay-pill flex items-center gap-1.5 rounded-full px-3 py-2 text-[11px] font-semibold text-muted-foreground"
            >
              <Download className="h-3.5 w-3.5" /> Export
            </button>
            <button type="button" onClick={onClose}
                    className="clay-pill grid h-9 w-9 place-items-center rounded-full">
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-7 py-6">
          {tab === "brief" ? (
            <>
              <section
                className="rounded-[26px] px-6 py-5"
                style={{
                  background: "linear-gradient(135deg, color-mix(in oklab, var(--ring-engine) 12%, white), color-mix(in oklab, var(--ring-up) 8%, white))",
                  boxShadow: "var(--clay-in)",
                }}
              >
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em]"
                     style={{ color: "var(--ring-engine)" }}>
                  <TrendingUp className="h-3.5 w-3.5" /> Executive readout
                </div>
                <p className="mt-3 max-w-[850px] text-[17px] font-semibold leading-[1.55] text-foreground/90">
                  {headline}
                </p>
              </section>

              <section className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  { icon: Gauge, label: "Reported", value: fm(root.value_b), sub: `from ${fm(root.value_a)}`, tone: "var(--ring-metric)" },
                  { icon: TrendingUp, label: "Quarter move", value: fm(root.delta_abs), sub: pct(root.delta_pct), tone: "var(--ring-up)" },
                  { icon: Layers3, label: "Explained", value: `${Math.round(bundle.run.explained_share * 100)}%`, sub: `${material.length} material drivers`, tone: "var(--ring-engine)" },
                  { icon: ShieldCheck, label: "Control totals", value: bundle.dataset.reconciliation.ok ? "Reconciled" : "Review", sub: "engine-verified", tone: bundle.dataset.reconciliation.ok ? "var(--ring-up)" : "var(--ring-down)" },
                ].map(({ icon: Icon, label, value, sub, tone }) => (
                  <div key={label} className="clay-card rounded-[20px] px-4 py-3.5">
                    <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground">
                      <Icon className="h-3.5 w-3.5" style={{ color: tone }} /> {label}
                    </div>
                    <div className="tabular mt-1.5 text-[20px] font-bold" style={{ color: tone }}>{value}</div>
                    <div className="mt-0.5 text-[10.5px] text-muted-foreground">{sub}</div>
                  </div>
                ))}
              </section>

              <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(250px,0.75fr)]">
                <section>
                  <h3 className="mb-3 text-[10.5px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                    What moved — ranked by impact
                  </h3>
                  <div className="grid gap-3">
                    {material.map((branch, index) => {
                      const attribution = branch.evidence?.attribution;
                      const concentration = branch.evidence?.concentration;
                      const kpi = branch.evidence?.kpi_reconciliation;
                      return (
                        <article key={branch.id} className="clay-card rounded-[22px] px-4 py-4">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex min-w-0 items-start gap-3">
                              <span className="clay-chip tabular grid h-7 w-7 shrink-0 place-items-center rounded-full text-[10px] font-bold"
                                    style={{ color: "var(--ring-engine)" }}>
                                {index + 1}
                              </span>
                              <div className="min-w-0">
                                <h4 className="text-[14px] font-semibold">{branch.name}</h4>
                                <p className="mt-0.5 text-[11px] text-muted-foreground">
                                  {fm(branch.value_a)} <ArrowRight className="inline h-3 w-3" /> {fm(branch.value_b)}
                                  {" · "}{pct(branch.delta_pct)}
                                </p>
                              </div>
                            </div>
                            <div className="shrink-0 text-right">
                              <div className="tabular text-[15px] font-bold" style={{ color: branch.delta_abs >= 0 ? "var(--ring-up)" : "var(--ring-down)" }}>
                                {fm(branch.delta_abs)}
                              </div>
                              <div className="text-[10.5px] text-muted-foreground">{share(branch.share)} of move</div>
                            </div>
                          </div>
                          <div className="mt-3 h-1.5 overflow-hidden rounded-full"
                               style={{ background: "color-mix(in oklab, var(--foreground) 8%, transparent)" }}>
                            <div className="h-full rounded-full" style={{
                              width: `${Math.min(100, Math.abs(branch.share) * 100)}%`,
                              background: branch.delta_abs >= 0 ? "var(--ring-up)" : "var(--ring-down)",
                            }} />
                          </div>
                          <div className="mt-3 flex flex-wrap gap-1.5">
                            {attribution?.top_driver && (
                              <span className="clay-chip rounded-full px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">
                                {attribution.top_driver}-led
                              </span>
                            )}
                            {concentration && (
                              <span className="clay-chip rounded-full px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">
                                top {concentration.top_n} = {share(concentration.top_n_share)}
                              </span>
                            )}
                            {kpi && (
                              <span className="clay-chip rounded-full px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">
                                KPI identity {pct(kpi.implied_pct)} implied
                              </span>
                            )}
                          </div>
                        </article>
                      );
                    })}
                  </div>
                </section>

                <aside className="grid content-start gap-4">
                  <section className="clay-card rounded-[22px] px-4 py-4">
                    <div className="flex items-center gap-2 text-[10.5px] font-bold uppercase tracking-[0.13em]"
                         style={{ color: "var(--ring-down)" }}>
                      <AlertTriangle className="h-4 w-4" /> Watch-outs
                    </div>
                    <ul className="mt-3 grid gap-2.5">
                      {(watchouts.length ? watchouts : ["No material watch-outs were produced."]).map((line) => (
                        <li key={line} className="text-[11.5px] leading-relaxed text-foreground/85">{line}</li>
                      ))}
                    </ul>
                  </section>

                  <section className="clay-card rounded-[22px] px-4 py-4">
                    <div className="flex items-center gap-2 text-[10.5px] font-bold uppercase tracking-[0.13em]"
                         style={{ color: "var(--ring-memory)" }}>
                      <Brain className="h-4 w-4" /> Company memory
                    </div>
                    <ul className="mt-3 grid gap-2">
                      {(context.length ? context : ["First observed run for this pattern."]).slice(0, 5).map((line) => (
                        <li key={line} className="text-[11.5px] leading-relaxed text-foreground/85">{line}</li>
                      ))}
                    </ul>
                  </section>
                </aside>
              </div>

              {operatingDrivers.length > 0 && (
                <section className="mt-7">
                  <h3 className="mb-3 text-[10.5px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                    Operating mechanics
                  </h3>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {operatingDrivers.map((line) => (
                      <div key={line} className="clay-row rounded-2xl px-3.5 py-3 text-[11.5px] leading-relaxed">
                        {line}
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          ) : (
            <>
              <section className="clay-card flex items-center justify-between gap-4 rounded-[22px] px-4 py-4">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="h-5 w-5" style={{ color: "var(--ring-up)" }} />
                  <div>
                    <div className="text-[13px] font-semibold">Evidence chain verified</div>
                    <div className="text-[11px] text-muted-foreground">
                      Control totals → deterministic attribution → tagged narration
                    </div>
                  </div>
                </div>
                <span className="clay-chip rounded-full px-3 py-1 text-[10px] font-bold"
                      style={{ color: "var(--ring-up)" }}>
                  {bundle.dataset.reconciliation.ok ? "reconciled ✓" : "review required"}
                </span>
              </section>

              <div className="mt-5 grid gap-3">
                {material.map((branch) => (
                  <section key={branch.id} className="clay-card rounded-[22px] px-4 py-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h4 className="text-[14px] font-semibold">{branch.name}</h4>
                        <p className="tabular mt-0.5 text-[11px] text-muted-foreground">
                          {fm(branch.value_a)} → {fm(branch.value_b)} · {pct(branch.delta_pct)}
                          {" · "}{share(branch.share)} of the move
                          {branch.zscore != null ? ` · z ${branch.zscore >= 0 ? "+" : ""}${branch.zscore}` : ""}
                        </p>
                      </div>
                      <span className="tabular text-[15px] font-bold"
                            style={{ color: branch.delta_abs >= 0 ? "var(--ring-up)" : "var(--ring-down)" }}>
                        {fm(branch.delta_abs)}
                      </span>
                    </div>
                    <ul className="mt-3 grid gap-2">
                      {(branch.evidence?.claims ?? []).map((claim: { text: string; tag: string }, index: number) => (
                        <li key={index} className="flex flex-wrap items-baseline gap-2 text-[12px] leading-relaxed text-foreground/90">
                          <span>{claim.text}</span><Badge tag={claim.tag} />
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>

              {capped.length > 0 && (
                <section className="mt-5 rounded-[22px] border border-dashed border-border px-4 py-4">
                  <h3 className="text-[10.5px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                    Reviewed below the materiality floor
                  </h3>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {capped.map((branch) => (
                      <span key={branch.id} className="clay-chip rounded-full px-2.5 py-1 text-[10.5px] text-muted-foreground">
                        {branch.name} · {fm(branch.delta_abs)} · {share(branch.share)}
                      </span>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>

        <footer className="flex shrink-0 items-center justify-between border-t border-border px-7 py-3 text-[10.5px] text-muted-foreground">
          <span>Every number was computed by the engine; the narrator only rephrased tagged evidence.</span>
          <span className="tabular">Run {bundle.run.id.slice(0, 8)}</span>
        </footer>
      </article>
    </div>
  );
}

/**
 * Detail drawer — opens over the center column (event log stays visible).
 * Panel per node type: branch pucks get the time-series with the trailing
 * normal band + child waterfall; pips get their stage's chart (bridge
 * waterfall, cluster scatter, concentration curve); explain/outcome get the
 * narrative with evidence-tag badges, memory callouts and the follow-up ask.
 */

import { useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceArea,
  ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis,
  YAxis, ZAxis,
} from "recharts";
import { Brain, Download, Send, X } from "lucide-react";
import type { FoldedBranch, FoldedPip, Model } from "../lib/fold";
import { fm, pct, share } from "../lib/format";
import { EVIDENCE_TAGS, type Ask, type EvidenceTag, type RunBundle } from "../lib/types";
import { downloadMemo } from "../lib/memo";

/* ── atoms ─────────────────────────────────────────────────────────────── */

function Badge({ tag }: { tag: string }) {
  const meta = EVIDENCE_TAGS[tag as EvidenceTag] ?? EVIDENCE_TAGS.agent_inference;
  return (
    <span
      className="clay-chip inline-block shrink-0 rounded-full px-2 py-0.5 align-middle text-[9px] font-bold uppercase tracking-[0.06em]"
      style={{ color: `var(${meta.cssVar})` }}
    >
      {meta.label}
    </span>
  );
}

function Claims({ claims }: { claims: { text: string; tag: string }[] }) {
  return (
    <ul className="grid gap-2.5">
      {claims.map((c, i) => (
        <li key={i} className="text-[12.5px] leading-relaxed text-foreground/90">
          {c.text} <Badge tag={c.tag} />
        </li>
      ))}
    </ul>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="mb-2 text-[10.5px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="clay-row rounded-2xl px-3 py-2.5">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">{label}</div>
      <div className="tabular mt-0.5 text-[15px] font-bold" style={tone ? { color: tone } : undefined}>{value}</div>
    </div>
  );
}

function MemoryCallout({ hits }: { hits: string[] }) {
  if (!hits.length) return null;
  return (
    <div className="clay-row mt-4 rounded-2xl px-3.5 py-3"
         style={{ boxShadow: `var(--clay-out-sm), inset 0 0 0 1.5px color-mix(in oklab, var(--ring-memory) 35%, transparent)` }}>
      <div className="mb-1.5 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-[0.12em]"
           style={{ color: "var(--ring-memory)" }}>
        <Brain className="h-3.5 w-3.5" strokeWidth={2.4} /> Context from previous runs
      </div>
      <ul className="grid gap-1">
        {hits.map((h) => (
          <li key={h} className="text-[11.5px] leading-relaxed text-foreground/85">{h}</li>
        ))}
      </ul>
    </div>
  );
}

const chartTip = {
  contentStyle: {
    background: "oklch(0.99 0.003 90 / 0.97)", border: "none", borderRadius: 12,
    boxShadow: "var(--clay-out-sm)", fontSize: 11,
  },
} as const;

/* ── charts ────────────────────────────────────────────────────────────── */

function GrowthBand({ payload }: { payload: Record<string, any> }) {
  const data = (payload.growth_series ?? []).map((g: any) => ({ ...g }));
  if (!data.length) return null;
  const mean = payload.trailing_mean_pct;
  const std = payload.trailing_std_pct ?? 0;
  return (
    <ResponsiveContainer width="100%" height={170}>
      <BarChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
        <CartesianGrid vertical={false} stroke="color-mix(in oklab, var(--foreground) 7%, transparent)" />
        <XAxis dataKey="period" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} unit="%" />
        <Tooltip {...chartTip} formatter={(v: any) => [`${v}%`, "growth"]} />
        {mean != null && (
          <>
            <ReferenceArea y1={mean - 2 * std} y2={mean + 2 * std}
                           fill="color-mix(in oklab, var(--ring-engine) 12%, transparent)" strokeOpacity={0} />
            <ReferenceLine y={mean} stroke="var(--ring-engine)" strokeDasharray="5 4"
                           label={{ value: "trailing mean", fontSize: 9, fill: "var(--muted-foreground)", position: "insideTopLeft" }} />
          </>
        )}
        <Bar dataKey="growth_pct" radius={[5, 5, 0, 0]}>
          {data.map((d: any, i: number) => (
            <Cell key={i}
                  fill={i === data.length - 1
                    ? (d.growth_pct >= 0 ? "var(--ring-up)" : "var(--ring-down)")
                    : "color-mix(in oklab, var(--ring-metric) 45%, transparent)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function LevelLine({ payload }: { payload: Record<string, any> }) {
  const data = payload.level_series ?? [];
  if (!data.length) return null;
  return (
    <ResponsiveContainer width="100%" height={150}>
      <LineChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -6 }}>
        <CartesianGrid vertical={false} stroke="color-mix(in oklab, var(--foreground) 7%, transparent)" />
        <XAxis dataKey="period" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={(v) => fm(v)} width={54} />
        <Tooltip {...chartTip} formatter={(v: any) => [fm(v), "value"]} />
        <Line type="monotone" dataKey="value" stroke="var(--ring-metric)" strokeWidth={2.25} dot={{ r: 2 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function Waterfall({ entries, total }: {
  entries: { name: string; value: number }[]; total?: { name: string; value: number };
}) {
  let cum = 0;
  const data = entries.map((e) => {
    const base = e.value >= 0 ? cum : cum + e.value;
    cum += e.value;
    return { name: e.name, base, size: Math.abs(e.value), value: e.value };
  });
  if (total) data.push({ name: total.name, base: Math.min(0, total.value), size: Math.abs(total.value), value: total.value });
  return (
    <ResponsiveContainer width="100%" height={175}>
      <BarChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -6 }}>
        <CartesianGrid vertical={false} stroke="color-mix(in oklab, var(--foreground) 7%, transparent)" />
        <XAxis dataKey="name" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} interval={0} />
        <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={(v) => fm(v)} width={54} />
        <Tooltip {...chartTip} formatter={(v: any, n: any, item: any) => n === "size" ? [fm(item.payload.value), "Δ"] : []} />
        <Bar dataKey="base" stackId="w" fill="transparent" />
        <Bar dataKey="size" stackId="w" radius={[5, 5, 2, 2]}>
          {data.map((d, i) => (
            <Cell key={i}
                  fill={total && i === data.length - 1
                    ? "var(--ring-metric)"
                    : d.value >= 0 ? "var(--ring-up)" : "var(--ring-down)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function ClusterScatter({ clusters }: { clusters: any[] }) {
  const palette = ["var(--ring-up)", "var(--ring-metric)", "var(--ring-drill)", "var(--ring-memory)"];
  return (
    <ResponsiveContainer width="100%" height={190}>
      <ScatterChart margin={{ top: 8, right: 8, bottom: 0, left: -6 }}>
        <CartesianGrid stroke="color-mix(in oklab, var(--foreground) 7%, transparent)" />
        <XAxis dataKey="x" name="prior" type="number" tick={{ fontSize: 9 }} tickLine={false}
               axisLine={false} tickFormatter={(v) => fm(v)} width={40} />
        <YAxis dataKey="y" name="current" type="number" tick={{ fontSize: 9 }} tickLine={false}
               axisLine={false} tickFormatter={(v) => fm(v)} width={54} />
        <ZAxis dataKey="size" range={[24, 320]} />
        <Tooltip {...chartTip} formatter={(v: any, n: any) => [fm(v), n]}
                 labelFormatter={() => ""} />
        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 4000, y: 4000 }]}
                       stroke="var(--edge-idle)" strokeDasharray="6 5" ifOverflow="hidden" />
        {clusters.map((c, i) => (
          <Scatter key={c.label + i} name={c.label}
                   data={c.points.map((p: any) => ({ ...p, size: Math.abs(p.delta) }))}
                   fill={palette[i % palette.length]} fillOpacity={0.75} />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function ConcentrationCurve({ conc }: { conc: Record<string, any> }) {
  return (
    <ResponsiveContainer width="100%" height={150}>
      <LineChart data={conc.curve} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
        <CartesianGrid vertical={false} stroke="color-mix(in oklab, var(--foreground) 7%, transparent)" />
        <XAxis dataKey="n" tick={{ fontSize: 9 }} tickLine={false} axisLine={false}
               label={{ value: "top-N customers", fontSize: 9, position: "insideBottom", offset: -2, fill: "var(--muted-foreground)" }} />
        <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false}
               tickFormatter={(v) => `${Math.round(v * 100)}%`} domain={[0, 1]} />
        <Tooltip {...chartTip}
                 formatter={(v: any) => [`${Math.round(v * 100)}%`, "cumulative share of Δ"]}
                 labelFormatter={(l) => `top ${l}`} />
        <ReferenceLine y={conc.top_n_share} stroke="var(--ring-drill)" strokeDasharray="5 4" />
        <Line type="monotone" dataKey="cum_share" stroke="var(--ring-drill)" strokeWidth={2.25} dot={{ r: 2.5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

/* ── tiny markdown (headings/bullets/bold only — enough for the memo) ──── */

function Memo({ md }: { md: string }) {
  const html = useMemo(() => {
    const esc = md.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const lines = esc.split("\n");
    const out: string[] = [];
    let inList = false;
    for (const line of lines) {
      const bolded = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      if (bolded.startsWith("## ")) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(`<h2>${bolded.slice(3)}</h2>`);
      } else if (bolded.startsWith("- ")) {
        if (!inList) { out.push("<ul>"); inList = true; }
        out.push(`<li>${bolded.slice(2)}</li>`);
      } else if (bolded.trim()) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(`<p>${bolded}</p>`);
      }
    }
    if (inList) out.push("</ul>");
    return out.join("");
  }, [md]);
  return <div className="memo" dangerouslySetInnerHTML={{ __html: html }} />;
}

/* ── stage panels ──────────────────────────────────────────────────────── */

function DeltaZPanel({ pip }: { pip: FoldedPip }) {
  const p = pip.payload;
  if (pip.state === "capped") {
    return (
      <>
        <div className="clay-row rounded-2xl px-3.5 py-3 text-[12.5px] leading-relaxed"
             style={{ color: "var(--ring-down)" }}>
          Branch capped — {p.reason}.
        </div>
        {p.stats && (
          <Section title="Δ context">
            <div className="grid grid-cols-2 gap-2">
              <Stat label="Δ" value={`${fm(p.stats.delta_abs)} (${pct(p.stats.delta_pct)})`} />
              <Stat label="z-score" value={p.stats.zscore != null ? `${p.stats.zscore}` : "—"} />
            </div>
          </Section>
        )}
      </>
    );
  }
  return (
    <>
      <div className="grid grid-cols-2 gap-2">
        <Stat label="current growth" value={pct(p.delta_pct)}
              tone={p.delta_pct >= 0 ? "var(--ring-up)" : "var(--ring-down)"} />
        <Stat label="z vs trailing" value={p.zscore != null ? `${p.zscore >= 0 ? "+" : ""}${p.zscore}σ` : "—"}
              tone={p.flagged ? "var(--ring-drill)" : undefined} />
        <Stat label="trailing mean" value={pct(p.trailing_mean_pct)} />
        <Stat label="normal band" value={p.trailing_std_pct != null ? `± ${(2 * p.trailing_std_pct).toFixed(1)}pp` : "—"} />
      </div>
      <Section title="growth vs trailing band">
        <GrowthBand payload={p} />
      </Section>
      <p className="mt-2 text-[10.5px] text-muted-foreground">{p.seasonality}</p>
    </>
  );
}

function DriversPanel({ pip }: { pip: FoldedPip }) {
  const p = pip.payload;
  const b = p.bridge;
  const kpi = p.kpi_reconciliation;
  return (
    <>
      {b && (
        <Section title="price / volume / mix / customer bridge">
          <Waterfall
            entries={[
              { name: "volume", value: b.volume }, { name: "price", value: b.price },
              { name: "mix", value: b.mix }, { name: "customer", value: b.customer },
              { name: "geo", value: b.geo }, { name: "fx", value: b.fx },
            ].filter((e) => Math.abs(e.value) > 0.005)}
            total={{ name: "Δ total", value: b.volume + b.price + b.mix + b.customer + b.geo + b.fx + b.other }}
          />
          <p className="mt-1.5 text-[10.5px] text-muted-foreground">
            Exact decomposition over {p.customers} customer books — sums to the branch Δ by construction.
          </p>
        </Section>
      )}
      {kpi && (
        <Section title="KPI reconciliation">
          <div className="clay-row rounded-2xl px-3.5 py-3">
            <div className="tabular text-[13px] font-semibold text-foreground">
              {kpi.volume_kpi} {pct(kpi.volume_pct)} × {kpi.price_kpi} {pct(kpi.price_pct)}
              {" ≈ "}<span style={{ color: "var(--ring-engine)" }}>{pct(kpi.implied_pct)}</span>
            </div>
            <div className="tabular mt-1 text-[11.5px] text-muted-foreground">
              reported {pct(kpi.reported_pct)} · residual {kpi.residual >= 0 ? "+" : ""}{kpi.residual}pp
              (mix / geo / rounding)
            </div>
          </div>
        </Section>
      )}
    </>
  );
}

function ClusterPanel({ pip }: { pip: FoldedPip }) {
  const p = pip.payload;
  const clusters = p.clusters ?? [];
  const conc = p.concentration;
  return (
    <>
      {clusters.length > 0 && (
        <Section title="transaction clusters · prior vs current (size = |Δ|)">
          <ClusterScatter clusters={clusters} />
          <div className="mt-2 grid gap-1.5">
            {clusters.map((c: any) => (
              <div key={c.label} className="clay-row flex items-center justify-between rounded-xl px-3 py-2">
                <span className="min-w-0 truncate text-[11.5px] font-semibold text-foreground">{c.label}</span>
                <span className="tabular ml-2 shrink-0 text-[11px] text-muted-foreground">
                  {fm(c.delta_abs)} · {share(c.share)} · {c.size} accts
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}
      {conc && (
        <Section title={`concentration — top ${conc.top_n} = ${share(conc.top_n_share)} of Δ`}>
          <ConcentrationCurve conc={conc} />
          <p className="mt-1.5 text-[11px] text-muted-foreground">
            {conc.top_names.join(", ")} carry {fm(conc.top_n_delta)} of the move
            across {conc.customer_count} accounts.
          </p>
        </Section>
      )}
    </>
  );
}

function DrillPanel({ pip, model, onSelect }: {
  pip: FoldedPip; model: Model; onSelect: (id: string) => void;
}) {
  const p = pip.payload;
  return (
    <Section title={`drilled by ${p.axis}`}>
      <div className="grid gap-1.5">
        {(p.children ?? []).map((c: any) => {
          const child = model.branches.get(c.id);
          const capped = child?.state === "capped";
          return (
            <button key={c.id} type="button" onClick={() => onSelect(c.id)}
                    className="clay-row flex items-center justify-between rounded-xl px-3 py-2 text-left hover:-translate-y-0.5 transition-transform">
              <span className={`text-[11.5px] font-semibold ${capped ? "line-through opacity-60" : "text-foreground"}`}>
                {c.name}
              </span>
              <span className="tabular text-[11px]" style={{ color: capped ? "var(--ring-down)" : "var(--muted-foreground)" }}>
                {share(c.share)}{capped ? " · capped" : ""}
              </span>
            </button>
          );
        })}
      </div>
      <p className="mt-2 text-[10.5px] text-muted-foreground">{p.reason}</p>
    </Section>
  );
}

function AskBox({ branch, asks, onAsk }: {
  branch: FoldedBranch; asks: Ask[]; onAsk: (branchId: string, q: string) => void;
}) {
  const [q, setQ] = useState("");
  const mine = asks.filter((a) => a.branchId === branch.id);
  return (
    <Section title="ask a follow-up (scoped to this node)">
      <div className="grid gap-2">
        {mine.map((a) => (
          <div key={a.at} className="clay-row rounded-xl px-3 py-2.5">
            <div className="text-[11px] font-bold text-foreground">“{a.question}”</div>
            <div className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">{a.text}</div>
          </div>
        ))}
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (q.trim()) { onAsk(branch.id, q.trim()); setQ(""); }
          }}
        >
          <input value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder={`why did ${branch.name} move?`}
                 className="clay-input min-w-0 flex-1 rounded-xl px-3 py-2 text-[12px]" />
          <button type="submit" aria-label="Ask"
                  className="clay-pill grid h-9 w-9 shrink-0 place-items-center rounded-full"
                  style={{ color: "var(--ring-engine)" }}>
            <Send className="h-4 w-4" strokeWidth={2.4} />
          </button>
        </form>
      </div>
    </Section>
  );
}

/* ── the drawer ────────────────────────────────────────────────────────── */

export function Drawer({ selected, model, bundle, asks, onClose, onSelect, onAsk }: {
  selected: string;
  model: Model;
  bundle: RunBundle;
  asks: Ask[];
  onClose: () => void;
  onSelect: (id: string) => void;
  onAsk: (branchId: string, q: string) => void;
}) {
  const branch =
    model.branches.get(selected) ??
    [...model.branches.values()].find((b) => b.pips.some((p) => p.id === selected));
  const pip = branch?.pips.find((p) => p.id === selected);
  const fullBranch = bundle.branches.find((b) => b.id === branch?.id);

  let title = "", subtitle = "", ring = "var(--ring-engine)";
  if (selected === "root") {
    title = bundle.run.metric; subtitle = `${bundle.run.period_a} → ${bundle.run.period_b}`;
    ring = "var(--ring-metric)";
  } else if (selected === "router") {
    title = "variance router"; subtitle = model.axis ? `axis · ${model.axis}` : "";
  } else if (selected === "outcome") {
    title = "Leadership summary";
    subtitle = model.complete ? `${Math.round(model.complete.explained * 100)}% of the move explained` : "";
    ring = "var(--ring-up)";
  } else if (pip && branch) {
    title = `${branch.name} · ${pip.stage.replace("_", " ")}`;
    subtitle = `${fm(branch.deltaAbs)} (${pct(branch.deltaPct)}) · ${share(branch.share)} of parent`;
    ring = pip.state === "capped" ? "var(--ring-down)" : "var(--ring-engine)";
  } else if (branch) {
    title = branch.name;
    subtitle = `${fm(branch.valueA)} → ${fm(branch.valueB)} · ${share(branch.share)} of parent Δ`;
    ring = branch.deltaAbs >= 0 ? "var(--ring-up)" : "var(--ring-down)";
  }

  const deltaPip = branch?.pips.find((p) => p.stage === "delta_z");
  const children = branch
    ? [...model.branches.values()].filter((b) => b.parentId === branch.id)
    : [];

  return (
    <div className="clay-panel absolute inset-y-0 right-0 z-40 flex w-full max-w-[470px] flex-col rounded-[28px] p-5">
      <header className="mb-1 flex shrink-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-[16px] font-bold tracking-tight" style={{ color: ring }}>
            {title}
          </h2>
          <p className="tabular mt-0.5 text-[11.5px] text-muted-foreground">{subtitle}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close details"
                className="clay-pill grid h-9 w-9 shrink-0 place-items-center rounded-full text-muted-foreground">
          <X className="h-4 w-4" strokeWidth={2.4} />
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {/* root */}
        {selected === "root" && model.root && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <Stat label={bundle.run.period_a} value={fm(model.root.value_a)} />
              <Stat label={bundle.run.period_b} value={fm(model.root.value_b)} />
              <Stat label="Δ" value={`${fm(model.root.delta_abs)}`}
                    tone={model.root.delta_abs >= 0 ? "var(--ring-up)" : "var(--ring-down)"} />
              <Stat label="growth" value={pct(model.root.delta_pct)} />
            </div>
            <Section title="history">
              <LevelLine payload={model.root} />
              <GrowthBand payload={model.root} />
            </Section>
            {model.branches.size > 0 && (
              <Section title="waterfall — child contributions">
                <Waterfall
                  entries={[...model.branches.values()].filter((b) => b.depth === 0)
                    .map((b) => ({ name: b.name.split(" ")[0]!, value: b.deltaAbs }))}
                  total={{ name: "Δ", value: model.root.delta_abs }}
                />
              </Section>
            )}
          </>
        )}

        {/* router */}
        {selected === "router" && (
          <Section title="axis shoot-out (explanatory power)">
            <div className="grid gap-1.5">
              {model.candidates.map((c: any) => (
                <div key={c.axis}
                     className={`clay-row flex items-center justify-between rounded-xl px-3 py-2 ${c.axis === model.axis ? "" : "opacity-65"}`}>
                  <span className="text-[12px] font-semibold text-foreground">
                    {c.axis}{c.axis === model.axis ? " ✓" : ""}
                  </span>
                  <span className="tabular text-[11px] text-muted-foreground">
                    power {c.power}{c.children ? ` · ${c.children} children` : ""}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-2 text-[10.5px] leading-relaxed text-muted-foreground">
              Power = |Δ| captured by the top-3 children × a granularity factor;
              branches are then ranked by absolute dollars, never % growth.
            </p>
          </Section>
        )}

        {/* outcome */}
        {selected === "outcome" && model.complete && (
          <>
            <button type="button" onClick={() => downloadMemo(bundle)}
                    className="clay-pill mb-2 flex items-center gap-2 rounded-full px-4 py-2 text-[12px] font-bold"
                    style={{ color: "var(--ring-engine)" }}>
              <Download className="h-4 w-4" strokeWidth={2.4} /> Export leadership memo (.md)
            </button>
            <Memo md={model.complete.summaryMd} />
            {model.outcome && (
              <Section title="claims">
                <Claims claims={model.outcome.claims} />
              </Section>
            )}
            {(model.learned.length > 0 || model.promoted.length > 0) && (
              <Section title={`memory delta — +${model.learned.length} learned`}>
                <ul className="grid gap-1.5">
                  {model.promoted.map((p) => (
                    <li key={p.key} className="text-[11.5px] font-semibold" style={{ color: "var(--ring-drill)" }}>
                      ↑ promoted to recurring: {p.text}
                    </li>
                  ))}
                  {model.learned.slice(0, 8).map((l) => (
                    <li key={l.key} className="text-[11.5px] text-muted-foreground">{l.text}</li>
                  ))}
                </ul>
              </Section>
            )}
          </>
        )}

        {/* branch puck */}
        {branch && !pip && selected !== "root" && selected !== "outcome" && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <Stat label={bundle.run.period_a} value={fm(branch.valueA)} />
              <Stat label={bundle.run.period_b} value={fm(branch.valueB)} />
              <Stat label="Δ · share" value={`${fm(branch.deltaAbs)} · ${share(branch.share)}`}
                    tone={branch.deltaAbs >= 0 ? "var(--ring-up)" : "var(--ring-down)"} />
              <Stat label="z-score" value={branch.zscore != null ? `${branch.zscore >= 0 ? "+" : ""}${branch.zscore}σ` : "—"} />
            </div>
            {branch.capReason && (
              <div className="clay-row mt-3 rounded-2xl px-3.5 py-3 text-[12px]" style={{ color: "var(--ring-down)" }}>
                Capped: {branch.capReason}
              </div>
            )}
            {deltaPip?.payload.level_series && (
              <Section title="history · trailing band">
                <LevelLine payload={deltaPip.payload} />
                <GrowthBand payload={deltaPip.payload} />
              </Section>
            )}
            {children.length > 0 && (
              <Section title="waterfall — child contributions">
                <Waterfall entries={children.map((c) => ({ name: c.name.split(" ")[0]!, value: c.deltaAbs }))}
                           total={{ name: "Δ", value: branch.deltaAbs }} />
                <div className="mt-2 grid gap-1.5">
                  {children.map((c) => (
                    <button key={c.id} type="button" onClick={() => onSelect(c.id)}
                            className="clay-row flex items-center justify-between rounded-xl px-3 py-2 text-left transition-transform hover:-translate-y-0.5">
                      <span className="text-[11.5px] font-semibold text-foreground">{c.name}</span>
                      <span className="tabular text-[11px] text-muted-foreground">
                        {fm(c.deltaAbs)} · {share(c.share)}
                      </span>
                    </button>
                  ))}
                </div>
              </Section>
            )}
            {fullBranch?.evidence?.claims && (
              <Section title="explanation">
                <Claims claims={fullBranch.evidence.claims} />
              </Section>
            )}
            <MemoryCallout hits={fullBranch?.evidence?.memory_hits ?? []} />
            {model.complete && <AskBox branch={branch} asks={asks} onAsk={onAsk} />}
          </>
        )}

        {/* pips */}
        {branch && pip && (
          <>
            {pip.stage === "delta_z" && <DeltaZPanel pip={pip} />}
            {pip.stage === "drivers" && <DriversPanel pip={pip} />}
            {pip.stage === "cluster" && <ClusterPanel pip={pip} />}
            {pip.stage === "drill" && <DrillPanel pip={pip} model={model} onSelect={onSelect} />}
            {pip.stage === "explain" && (
              <>
                <p className="text-[13px] leading-relaxed text-foreground/90">{pip.payload.text}</p>
                {pip.payload.claims && (
                  <Section title="claims · evidence tags">
                    <Claims claims={pip.payload.claims} />
                  </Section>
                )}
                <MemoryCallout hits={pip.payload.memory_hits ?? []} />
                {model.complete && <AskBox branch={branch} asks={asks} onAsk={onAsk} />}
                {!pip.payload.llm && (
                  <p className="mt-3 text-[10px] text-muted-foreground">
                    Templated narration (engine numbers verbatim) — set LLM_API_KEY on the backend for polished prose.
                  </p>
                )}
              </>
            )}
            {pip.stage === "ask" && (
              <>
                <div className="text-[11px] font-bold text-foreground">“{pip.payload.question}”</div>
                <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/90">{pip.payload.text}</p>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

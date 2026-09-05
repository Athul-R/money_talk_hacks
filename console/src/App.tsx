/**
 * Delta Ledger — live "Explain the Change" console.
 * Front door → executive summary → high-level or detailed lineage.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronRight, FileText, Landmark, Network } from "lucide-react";
import { Architecture } from "./components/Architecture";
import { BeatBar } from "./components/BeatBar";
import { Drawer } from "./components/Drawer";
import { EventLog } from "./components/EventLog";
import { Landing } from "./components/Landing";
import { MethodStrip } from "./components/MethodStrip";
import { PrismDebug } from "./components/PrismDebug";
import { RunsRail } from "./components/RunsRail";
import { StoryGraph } from "./components/StoryGraph";
import { Summary } from "./components/Summary";
import * as api from "./lib/api";
import { captions, fold } from "./lib/fold";
import { breadcrumb, frame, frameOverview } from "./lib/frame";
import { companyLabel, datasetLabel, fm, pct } from "./lib/format";
import { MemoSheet } from "./components/MemoSheet";
import type { Ask, ConsoleIndex, RunBundle } from "./lib/types";

/** Live pacing: each step takes about as long as the work it represents —
 * the web search lingers, a cap is instant, a drill takes a breath. ±20%
 * jitter so no two uploads play identically. */
const LIVE_MS: Record<string, number> = {
  run_started: 900, web_context: 2800, axis_selected: 1300, memory_recalled: 1200,
  branch_ranked: 1500, zscore_flagged: 950, attribution_done: 1250,
  cluster_found: 1400, concentration_flagged: 900, drill_spawned: 1550,
  branch_capped: 650, explanation_ready: 1200, memory_learned: 1100,
  run_complete: 1700,
};

// Documentation recorder uses the real upload/run path with a shorter reveal.
const STORY_RATE = new URLSearchParams(window.location.search).has("film") ? 0.12 : 1;

/** Hero YoY pair if the books carry it, else last quarter vs a year before. */
function pickPeriods(periods: string[]): [string, string] {
  if (periods.includes("2025-Q2") && periods.includes("2026-Q2")) return ["2025-Q2", "2026-Q2"];
  if (periods.length >= 5) return [periods[periods.length - 5], periods[periods.length - 1]];
  return [periods[0] ?? "2025-Q2", periods[periods.length - 1] ?? "2026-Q2"];
}
const EMPTY_LIVE: ConsoleIndex = {
  company: { id: "company", name: "Company" },
  dataset: { name: "Quarterly books", periods: ["2025-Q2", "2026-Q2"], reconciliation: { ok: false, checks: [] } },
  runs: [],
  memory: [],
};

export default function App() {
  const [view, setView] = useState<"home" | "summary" | "closer">("home");
  const [lineageView, setLineageView] = useState<"overview" | "audit">("overview");
  const [prismOpen, setPrismOpen] = useState(false);
  const [memoOpen, setMemoOpen] = useState(false);
  const [archOpen, setArchOpen] = useState(() => window.location.hash === "#architecture");
  const [activeFile, setActiveFile] = useState("");
  const [bundle, setBundle] = useState<RunBundle | null>(null);
  const [beat, setBeat] = useState(1);
  const [playing, setPlaying] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [asks, setAsks] = useState<Ask[]>([]);

  const [liveIndex, setLiveIndex] = useState<ConsoleIndex>(EMPTY_LIVE);
  const [datasetId, setDatasetId] = useState("alphabet-given");
  const [datasets, setDatasets] = useState<{ id: string; name: string }[]>([
    { id: "alphabet-given", name: "Company · quarterly books" },
  ]);
  const [liveOk, setLiveOk] = useState(false);
  const [liveHint, setLiveHint] = useState("");
  const [prismOn, setPrismOn] = useState(false);
  const [starting, setStarting] = useState(false);

  const index = liveIndex;

  const playBundle = useCallback((next: RunBundle, file: string, nextView?: "summary" | "closer") => {
    setBundle(next);
    setActiveFile(file);
    setBeat(1);
    setPlaying(true);
    setSelected(null);
    setAsks([]);
    setLineageView("overview");
    if (nextView) setView(nextView);
  }, []);

  useEffect(() => {
    const onHash = () => setArchOpen(window.location.hash === "#architecture");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const openArch = (open: boolean) => {
    setArchOpen(open);
    window.history.replaceState(null, "", open ? "#architecture" : "#");
  };

  useEffect(() => {
    let cancelled = false;
    setBundle(null);
    setSelected(null);
    setView("home");
    (async () => {
      try {
        const [h, cat] = await Promise.all([api.health(), api.catalog()]);
        if (cancelled) return;
        setLiveOk(h.ok);
        setPrismOn(h.prism);
        setLiveHint(h.given ? "" : "data/given is missing on the API host");
        setLiveIndex({
          company: cat.company,
          dataset: cat.dataset,
          runs: cat.runs,
          memory: cat.memory,
        });
        if (cat.datasets?.length) {
          setDatasets(cat.datasets.map((d) => ({ id: d.id, name: d.name })));
        }
        setDatasetId((id) => cat.datasets?.some((d) => d.id === id) ? id : (cat.dataset.id ?? "alphabet-given"));
        // Nothing auto-starts: upload a ledger or open a prior production run.
      } catch {
        if (cancelled) return;
        setLiveOk(false);
        setLiveHint("API offline — run `make api` in another terminal, then stay on live.");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const maxBeat = bundle?.run.beats ?? 1;

  // First event kind per beat — drives the live pacing.
  const beatKinds = useMemo(() => {
    const m = new Map<number, string>();
    for (const ev of bundle?.events ?? []) {
      const b = ev.payload.beat as number;
      if (!m.has(b)) m.set(b, ev.kind);
    }
    return m;
  }, [bundle]);

  useEffect(() => {
    if (!playing || !bundle) return;
    if (beat >= maxBeat) { setPlaying(false); return; }
    const ms = STORY_RATE * (LIVE_MS[beatKinds.get(beat + 1) ?? ""] ?? 1000)
      * (0.85 + Math.random() * 0.4);
    const t = setTimeout(() => setBeat((b) => b + 1), ms);
    return () => clearTimeout(t);
  }, [playing, beat, maxBeat, bundle, beatKinds]);

  const model = useMemo(
    () => (bundle ? fold(bundle.events, beat, asks) : null),
    [bundle, beat, asks],
  );
  const caps = useMemo(() => (bundle ? captions(bundle.events) : new Map()), [bundle]);
  const graph = useMemo(
    () => (model
      ? lineageView === "overview"
        ? frameOverview(model, selected)
        : frame(model, selected)
      : { nodes: [], edges: [] }),
    [model, selected, lineageView],
  );
  const crumbs = useMemo(
    () => (model ? breadcrumb(model, selected) : []),
    [model, selected],
  );

  const onAsk = useCallback(async (branchId: string, question: string) => {
    if (!bundle) return;
    try {
      const row = await api.ask(bundle.run.id, branchId, question);
      setAsks((prev) => [...prev, row]);
      return;
    } catch { /* fall through to the evidence-scoped local answer */ }
    const evidence = bundle.branches.find((b) => b.id === branchId)?.evidence;
    const facts = (evidence?.claims ?? []).map((c: any) => c.text).slice(0, 3).join(" ");
    setAsks((prev) => [...prev, {
      branchId, question,
      text: facts
        ? `Scoped to this node's computed evidence: ${facts}`
        : "No computed evidence on this node yet — step the story forward first.",
      at: new Date().toISOString(),
    }]);
  }, [bundle]);

  const onPick = useCallback(async (file: string) => {
    const b = await api.getRun(file);
    playBundle(b, file, "closer");
  }, [playBundle]);

  const runLive = useCallback(async (dsId: string, metric: string, periodA: string, periodB: string) => {
    setStarting(true);
    try {
      const next = await api.startRun({
        dataset_id: dsId, metric, period_a: periodA, period_b: periodB,
        company: companyLabel(index.company.name),
      });
      playBundle(next, next.run.id, "summary");
      setLiveIndex((prev) => ({
        ...prev,
        runs: [api.indexRun(next), ...prev.runs.filter((r) => r.id !== next.run.id)],
        memory: next.memory_after ?? prev.memory,
      }));
    } finally {
      setStarting(false);
    }
  }, [index.company.name, playBundle]);

  // Upload a CSV pack → reconcile → the analysis starts automatically.
  const onUpload = useCallback(async (files: FileList) => {
    const meta = await api.uploadDataset(files);
    setDatasetId(meta.id);
    setDatasets((prev) => [{ id: meta.id, name: meta.name }, ...prev.filter((d) => d.id !== meta.id)]);
    setLiveIndex((prev) => ({
      ...prev,
      dataset: {
        id: meta.id,
        name: meta.name,
        periods: meta.periods,
        reconciliation: meta.reconciliation,
      },
    }));
    const [pa, pb] = pickPeriods(meta.periods);
    await runLive(meta.id, "Revenue", pa, pb);
  }, [runLive]);

  const onStartRun = useCallback(
    (metric: string, periodA: string, periodB: string) => runLive(datasetId, metric, periodA, periodB),
    [datasetId, runLive],
  );

  return (
    <main className="flex h-screen flex-col overflow-hidden px-5 py-5 lg:px-7">
      <header className="mx-auto mb-5 grid w-full max-w-[1720px] shrink-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl"
                style={{ boxShadow: "var(--clay-out)" }}>
            <span className="flex items-end gap-[3px]">
              <i className="block h-2 w-[3px] rounded-full" style={{ background: "var(--ring-engine)" }} />
              <i className="block h-4 w-[3px] rounded-full" style={{ background: "var(--ring-up)" }} />
              <i className="block h-3 w-[3px] rounded-full" style={{ background: "var(--ring-drill)" }} />
            </span>
          </span>
          <div className="min-w-0">
            <h1 className="wordmark truncate text-[19px] font-bold tracking-tight text-foreground">
              Delta Ledger
            </h1>
            <p className="truncate text-[11.5px] text-muted-foreground">
              explain the change · {companyLabel(index.company.name)} · {datasetLabel(index.dataset.name)}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {bundle && model?.root && (
            <span className="clay-pill tabular flex items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-semibold text-foreground">
              <Landmark className="h-4 w-4" style={{ color: "var(--ring-metric)" }} strokeWidth={2.2} />
              {bundle.run.metric} {pct(model.root.delta_pct)} · {fm(model.root.delta_abs)}
            </span>
          )}
          {bundle && (
            <button type="button" onClick={() => setMemoOpen(true)}
                    className="clay-pill flex items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-semibold text-foreground transition-transform hover:-translate-y-0.5">
              <FileText className="h-4 w-4" style={{ color: "var(--ring-engine)" }} strokeWidth={2.4} />
              leadership memo
            </button>
          )}
          <button type="button" onClick={() => openArch(true)}
                  className="clay-pill flex items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-semibold text-foreground">
            <Network className="h-4 w-4" style={{ color: "var(--ring-engine)" }} strokeWidth={2.2} />
            architecture
          </button>
          {bundle && (
            <button type="button" onClick={() => { setView("closer"); setPrismOpen((o) => !o); }}
                    className="clay-pill rounded-full px-4 py-2.5 text-[12px] font-semibold"
                    style={{ color: "var(--ring-memory)" }}>
              PRISM
            </button>
          )}
          {view !== "home" && bundle && (
            <button type="button" onClick={() => setView(view === "closer" ? "summary" : "closer")}
                    className="clay-pill rounded-full px-4 py-2.5 text-[12px] font-semibold"
                    style={{ color: "var(--ring-engine)" }}>
              {view === "closer" ? "executive summary" : "open closer"}
            </button>
          )}
          <span className="clay-pill flex items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-semibold text-foreground">
            <i className="block h-2 w-2 animate-pulse rounded-full"
               style={{
                 background: !liveOk ? "var(--ring-down)"
                   : starting || (playing && bundle) ? "var(--ring-active)"
                   : "var(--ring-up)",
               }} />
            {!liveOk ? "engine · offline"
              : starting ? "reconciling…"
              : playing && bundle ? "analyzing…"
              : "production · live"}
            {prismOn && (
              <span className="text-[10px] font-bold uppercase tracking-wide" style={{ color: "var(--ring-memory)" }}>
                prism
              </span>
            )}
          </span>
        </div>
      </header>

      {view === "home" && (
        <Landing
          liveOk={liveOk} liveHint={liveHint}
          starting={starting} onUpload={onUpload}
        />
      )}

      {view === "summary" && bundle && (
        <Summary
          bundle={bundle} playing={playing} beat={beat} maxBeat={maxBeat}
          prismOn={prismOn}
          onCloser={() => setView("closer")}
          onPrism={() => { setPrismOpen(true); setView("closer"); }}
          onMemo={() => setMemoOpen(true)}
        />
      )}

      {view === "closer" && (
      <div className="mx-auto grid w-full max-w-[1720px] min-h-0 flex-1 gap-5 lg:grid-cols-[280px_minmax(0,1fr)_340px]">
        <RunsRail
          index={index} activeFile={activeFile} onPick={onPick}
          datasets={datasets}
          datasetId={datasetId} onDataset={setDatasetId}
          onUpload={onUpload}
          onStartRun={onStartRun}
          starting={starting} liveOk={liveOk} liveHint={liveHint}
        />

        <section className="clay-panel relative flex min-h-0 flex-col gap-4 rounded-[32px] p-5">
          {bundle && (
            <BeatBar
              beat={beat} maxBeat={maxBeat}
              caption={caps.get(beat) ?? ""}
            />
          )}

          <div className="flex shrink-0 items-center justify-between gap-4">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                Live lineage
              </p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                {lineageView === "overview"
                  ? "Leadership path: reconcile → route → top movers → explained."
                  : "Audit path: every z-score, bridge, cluster, drill, and narrative."}
              </p>
            </div>
            <div className="clay-pill flex shrink-0 items-center gap-0.5 rounded-full p-1">
              {([
                ["overview", "High level"],
                ["audit", "Detailed audit"],
              ] as const).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => { setLineageView(value); setSelected(null); }}
                  className={`rounded-full px-3 py-1.5 text-[10.5px] font-bold ${
                    lineageView === value ? "clay-pill-active" : ""
                  }`}
                  style={{ color: lineageView === value ? "var(--ring-engine)" : "var(--muted-foreground)" }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {lineageView === "audit" && <MethodStrip />}

          {crumbs.length > 1 && (
            <nav className="flex shrink-0 items-center gap-1 px-1 text-[11.5px] font-semibold">
              {crumbs.map((c, i) => (
                <span key={i} className="flex items-center gap-1">
                  {i > 0 && <ChevronRight className="h-3 w-3 text-muted-foreground" strokeWidth={2.4} />}
                  <span style={{ color: i === crumbs.length - 1 ? "var(--ring-engine)" : "var(--muted-foreground)" }}>
                    {c}
                  </span>
                </span>
              ))}
            </nav>
          )}

          {bundle ? (
            <StoryGraph
              nodes={graph.nodes} edges={graph.edges}
              beatKey={`${activeFile}:${lineageView}:${beat}`}
              selected={selected} onSelect={(id) => {
                if (id === "outcome") { setMemoOpen(true); return; }
                if (id === "overview-context") {
                  setPrismOpen(true);
                  return;
                }
                if (id === "overview-evidence") {
                  setLineageView("audit");
                  setSelected(null);
                  return;
                }
                setSelected(id);
              }}
            />
          ) : (
            <div className="clay-empty grid flex-1 place-items-center rounded-[24px] px-8 text-center">
              <p className="max-w-sm text-[13px] leading-relaxed text-muted-foreground">
                Pick a run on the left, or go back to the front page to upload books.
              </p>
            </div>
          )}

          {selected && model && bundle && (
            <Drawer
              selected={selected} model={model} bundle={bundle} asks={asks}
              onClose={() => setSelected(null)} onSelect={setSelected} onAsk={onAsk}
              onOpenMemo={() => setMemoOpen(true)}
            />
          )}
        </section>

        {prismOpen && bundle ? (
          <PrismDebug events={bundle.events} prismOn={prismOn} onClose={() => setPrismOpen(false)} />
        ) : bundle ? (
          <EventLog
            events={bundle.events} upto={beat}
            onPick={(ev) => {
              setPlaying(false);
              setBeat(ev.payload.beat);
              if (ev.payload.node_id) setSelected(ev.payload.node_id);
            }}
          />
        ) : null}
      </div>
      )}

      {archOpen && <Architecture onClose={() => openArch(false)} />}
      {memoOpen && bundle && <MemoSheet bundle={bundle} onClose={() => setMemoOpen(false)} />}
    </main>
  );
}

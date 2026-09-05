/**
 * Delta Ledger — "Explain the Change" console.
 * Three columns like the reference scheduler: runs rail · story graph · event
 * log. One state machine: pick a run → fold its events up to the current beat
 * → frame() → React Flow. The drawer overlays the center; the log stays put.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronRight, Download, Landmark } from "lucide-react";
import { BeatBar } from "./components/BeatBar";
import { Drawer } from "./components/Drawer";
import { EventLog } from "./components/EventLog";
import { RunsRail } from "./components/RunsRail";
import { StoryGraph } from "./components/StoryGraph";
import { captions, fold } from "./lib/fold";
import { breadcrumb, frame } from "./lib/frame";
import { fm, pct } from "./lib/format";
import { DEFAULT_RUN_FILE, loadBundle, mockIndex } from "./lib/mock";
import { downloadMemo } from "./lib/memo";
import type { Ask, RunBundle } from "./lib/types";

const PLAY_MS = 1150;

export default function App() {
  const [activeFile, setActiveFile] = useState(DEFAULT_RUN_FILE);
  const [bundle, setBundle] = useState<RunBundle | null>(null);
  const [beat, setBeat] = useState(1);
  const [playing, setPlaying] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [asks, setAsks] = useState<Ask[]>([]);

  useEffect(() => {
    let cancelled = false;
    loadBundle(activeFile).then((b) => {
      if (cancelled) return;
      setBundle(b);
      setBeat(1);
      setPlaying(true);
      setSelected(null);
      setAsks([]);
    });
    return () => { cancelled = true; };
  }, [activeFile]);

  const maxBeat = bundle?.run.beats ?? 1;

  useEffect(() => {
    if (!playing || !bundle) return;
    if (beat >= maxBeat) { setPlaying(false); return; }
    const t = setTimeout(() => setBeat((b) => b + 1), PLAY_MS);
    return () => clearTimeout(t);
  }, [playing, beat, maxBeat, bundle]);

  const model = useMemo(
    () => (bundle ? fold(bundle.events, beat, asks) : null),
    [bundle, beat, asks],
  );
  const caps = useMemo(() => (bundle ? captions(bundle.events) : new Map()), [bundle]);
  const graph = useMemo(
    () => (model ? frame(model, selected) : { nodes: [], edges: [] }),
    [model, selected],
  );
  const crumbs = useMemo(
    () => (model ? breadcrumb(model, selected) : []),
    [model, selected],
  );

  const onAsk = useCallback((branchId: string, question: string) => {
    if (!bundle) return;
    const evidence = bundle.branches.find((b) => b.id === branchId)?.evidence;
    const facts = (evidence?.claims ?? [])
      .map((c: any) => c.text).slice(0, 3).join(" ");
    setAsks((prev) => [...prev, {
      branchId, question,
      text: facts
        ? `Scoped to this node's computed evidence: ${facts} (Templated answer — wire the backend with an LLM key for free-form follow-ups.)`
        : "No computed evidence on this node yet — step the story forward first.",
      at: new Date().toISOString(),
    }]);
  }, [bundle]);

  const onPlay = useCallback((p: boolean) => {
    if (p && beat >= maxBeat) setBeat(1);
    setPlaying(p);
  }, [beat, maxBeat]);

  return (
    <main className="flex h-screen flex-col overflow-hidden px-5 py-5 lg:px-7">
      {/* ── top bar ── */}
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
              explain the change · {mockIndex.company.name} · {mockIndex.dataset.name}
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
            <button type="button" onClick={() => downloadMemo(bundle)}
                    className="clay-pill flex items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-semibold text-foreground transition-transform hover:-translate-y-0.5">
              <Download className="h-4 w-4" style={{ color: "var(--ring-engine)" }} strokeWidth={2.4} />
              leadership memo
            </button>
          )}
          <span className="clay-pill flex items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-semibold text-foreground">
            <i className="block h-2 w-2 animate-pulse rounded-full" style={{ background: "var(--ring-up)" }} />
            replay · mock
          </span>
        </div>
      </header>

      {/* ── three columns ── */}
      <div className="mx-auto grid w-full max-w-[1720px] min-h-0 flex-1 gap-5 lg:grid-cols-[280px_minmax(0,1fr)_340px]">
        <RunsRail index={mockIndex} activeFile={activeFile} onPick={setActiveFile} />

        <section className="clay-panel relative flex min-h-0 flex-col gap-4 rounded-[32px] p-5">
          {bundle && (
            <BeatBar
              beat={beat} maxBeat={maxBeat}
              caption={caps.get(beat) ?? ""}
              playing={playing}
              onSeek={setBeat} onPlay={onPlay}
            />
          )}

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

          <StoryGraph
            nodes={graph.nodes} edges={graph.edges}
            beatKey={`${activeFile}:${beat}`}
            selected={selected} onSelect={setSelected}
          />

          {selected && model && bundle && (
            <Drawer
              selected={selected} model={model} bundle={bundle} asks={asks}
              onClose={() => setSelected(null)} onSelect={setSelected} onAsk={onAsk}
            />
          )}
        </section>

        {bundle && (
          <EventLog
            events={bundle.events} upto={beat}
            onPick={(ev) => {
              setPlaying(false);
              setBeat(ev.payload.beat);
              if (ev.payload.node_id) setSelected(ev.payload.node_id);
            }}
          />
        )}
      </div>
    </main>
  );
}

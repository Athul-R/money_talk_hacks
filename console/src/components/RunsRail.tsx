/**
 * Left rail (fork of the scheduler's WorkflowRail): dataset upload card with
 * control-total check, "new run" card, past runs, and the company memory chip.
 * Mock mode: uploads validate locally against the baked dataset; new runs map
 * onto the baked engine outputs (the backend wire-up swaps these two handlers).
 */

import { useMemo, useRef, useState } from "react";
import {
  Brain, Check, ChevronDown, FileSpreadsheet, Play, Sparkles, UploadCloud,
} from "lucide-react";
import type { MockIndex, RunIndexEntry } from "../lib/types";

function StatusPill({ entry, active }: { entry: RunIndexEntry; active: boolean }) {
  return (
    <span
      className="clay-chip tabular rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.06em]"
      style={{ color: active ? "var(--ring-engine)" : "var(--ring-up)" }}
    >
      {entry.status === "complete" ? `explained ${Math.round(entry.explained_share * 100)}%` : entry.status}
    </span>
  );
}

export function RunsRail({ index, activeFile, onPick }: {
  index: MockIndex;
  activeFile: string;
  onPick: (file: string) => void;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploaded, setUploaded] = useState<string[]>([]);
  const [validating, setValidating] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [newRunOpen, setNewRunOpen] = useState(false);
  const [metric, setMetric] = useState("Revenue");
  const [periodA, setPeriodA] = useState("2025-Q2");
  const [periodB, setPeriodB] = useState("2026-Q2");
  const [runHint, setRunHint] = useState("");

  const recon = index.dataset.reconciliation;
  const memory = index.memory;
  const runsNewestFirst = useMemo(
    () => [...index.runs].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)),
    [index.runs],
  );

  const onFiles = (files: FileList | null) => {
    if (!files?.length) return;
    setUploaded([...files].map((f) => f.name));
    setValidating(true);
    setTimeout(() => setValidating(false), 700); // local validation beat (mock)
  };

  const startRun = () => {
    const match = index.runs.find(
      (r) => r.metric === metric && r.period_a === periodA && r.period_b === periodB,
    );
    if (match) {
      setRunHint("");
      setNewRunOpen(false);
      onPick(match.file);
    } else {
      setRunHint("Engine offline in mock mode — pick one of the baked runs below.");
    }
  };

  return (
    <aside className="flex min-h-0 flex-col gap-3">
      {/* ── dataset card ── */}
      <div
        className="clay-card rounded-[22px] px-4 py-3.5"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); onFiles(e.dataTransfer.files); }}
      >
        <button type="button" className="flex w-full items-center gap-3 text-left"
                onClick={() => fileInput.current?.click()}>
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full"
                style={{ boxShadow: "var(--clay-out-sm)", color: "var(--ring-engine)" }}>
            <UploadCloud className="h-4 w-4" strokeWidth={2.2} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-semibold text-foreground">
              {index.dataset.name}
            </span>
            <span className="block truncate text-[11px] text-muted-foreground">
              {uploaded.length
                ? uploaded.join(" · ")
                : "summaries · transactions · dimensions · kpis"}
            </span>
          </span>
        </button>
        <input ref={fileInput} type="file" multiple accept=".csv,.json" className="hidden"
               onChange={(e) => onFiles(e.target.files)} />
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <span className="clay-chip tabular rounded-full px-2.5 py-1 text-[10px] font-semibold"
                style={{ color: "var(--ring-metric)" }}>
            {index.dataset.periods.length} quarters
          </span>
          <span className="clay-chip flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold"
                style={{ color: validating ? "var(--ring-active)" : recon.ok ? "var(--ring-up)" : "var(--ring-down)" }}>
            {validating ? "validating…" : (
              <>
                <Check className="h-3 w-3" strokeWidth={3} />
                txns reconcile to summaries
              </>
            )}
          </span>
        </div>
      </div>

      {/* ── new run card ── */}
      <div className="clay-card rounded-[22px] px-4 py-3.5">
        <button type="button" onClick={() => setNewRunOpen((o) => !o)}
                className="flex w-full items-center justify-between text-left">
          <span className="flex items-center gap-2 text-[13px] font-semibold"
                style={{ color: "var(--ring-engine)" }}>
            <Play className="h-4 w-4" strokeWidth={2.6} /> New run
          </span>
          <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${newRunOpen ? "rotate-180" : ""}`} />
        </button>
        {newRunOpen && (
          <div className="mt-3 grid gap-2">
            <select value={metric} onChange={(e) => setMetric(e.target.value)}
                    className="clay-input rounded-xl px-3 py-2 text-[12px] font-medium">
              {["Revenue", "Operating income", "Gross profit", "Free cash flow"].map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
            <div className="grid grid-cols-2 gap-2">
              {[{ v: periodA, set: setPeriodA }, { v: periodB, set: setPeriodB }].map((s, i) => (
                <select key={i} value={s.v} onChange={(e) => s.set(e.target.value)}
                        className="clay-input rounded-xl px-3 py-2 text-[12px] font-medium tabular">
                  {index.dataset.periods.map((p) => <option key={p}>{p}</option>)}
                </select>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <span className="clay-chip rounded-full px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">
                materiality · 5% share / 80% stop
              </span>
            </div>
            <button type="button" onClick={startRun}
                    className="clay-pill rounded-xl px-3 py-2 text-[12px] font-bold"
                    style={{ color: "var(--ring-engine)" }}>
              Explain the change
            </button>
            {runHint && (
              <p className="text-[10.5px] leading-snug" style={{ color: "var(--ring-drill)" }}>{runHint}</p>
            )}
          </div>
        )}
      </div>

      {/* ── runs list ── */}
      <div className="flex items-center justify-between px-1 pt-1">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Runs
        </h2>
        <span className="clay-chip rounded-full px-2 py-0.5 text-[10px] font-semibold"
              style={{ color: "var(--ring-engine)" }}>
          {index.runs.length}
        </span>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto pr-0.5">
        {runsNewestFirst.map((r) => {
          const active = r.file === activeFile;
          return (
            <button
              key={r.file}
              type="button"
              onClick={() => onPick(r.file)}
              className={`rounded-[20px] px-4 py-3 text-left transition-transform hover:-translate-y-0.5 ${
                active ? "clay-pill-active" : "clay-card"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4 shrink-0"
                                   style={{ color: active ? "var(--ring-engine)" : "var(--muted-foreground)" }}
                                   strokeWidth={2.2} />
                  <span className="truncate text-[12.5px] font-semibold text-foreground">
                    {r.metric}
                  </span>
                </span>
                <StatusPill entry={r} active={active} />
              </div>
              <div className="tabular mt-1 text-[11px] text-muted-foreground">
                {r.period_a} → {r.period_b}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {r.memory_delta > 0 && (
                  <span className="clay-chip rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        style={{ color: "var(--ring-memory)" }}>
                    +{r.memory_delta} learned
                  </span>
                )}
                {r.recalled > 0 && (
                  <span className="clay-chip rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        style={{ color: "var(--ring-memory)" }}>
                    {r.recalled} recalled
                  </span>
                )}
                {r.promoted > 0 && (
                  <span className="clay-chip flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        style={{ color: "var(--ring-drill)" }}>
                    <Sparkles className="h-3 w-3" /> promoted
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* ── memory chip ── */}
      <div className="clay-card shrink-0 rounded-[22px] px-4 py-3">
        <button type="button" onClick={() => setMemoryOpen((o) => !o)}
                className="flex w-full items-center justify-between text-left">
          <span className="flex items-center gap-2 text-[12.5px] font-semibold text-foreground">
            <Brain className="h-4 w-4" style={{ color: "var(--ring-memory)" }} strokeWidth={2.2} />
            {index.company.name}
          </span>
          <span className="clay-chip rounded-full px-2 py-0.5 text-[10px] font-bold"
                style={{ color: "var(--ring-memory)" }}>
            {memory.length} patterns
          </span>
        </button>
        {memoryOpen && (
          <ul className="mt-2.5 grid max-h-44 gap-1.5 overflow-y-auto">
            {memory.map((m) => (
              <li key={m.id} className="flex items-start gap-2 text-[10.5px] leading-snug text-muted-foreground">
                <span className="clay-chip mt-[1px] shrink-0 rounded-full px-1.5 py-0.5 text-[8.5px] font-bold uppercase tracking-wide"
                      style={{ color: m.kind === "recurring_driver" ? "var(--ring-drill)" : "var(--ring-memory)" }}>
                  {m.kind.replace("_", " ")}
                </span>
                {m.text}
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

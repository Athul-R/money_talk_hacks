/**
 * Production front door: drop the company's books, get the quarter explained.
 */

import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";

export function Landing({
  liveOk, liveHint, starting, onUpload,
}: {
  liveOk: boolean;
  liveHint: string;
  starting: boolean;
  onUpload: (files: FileList) => Promise<void> | void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [names, setNames] = useState<string[]>([]);
  const [err, setErr] = useState("");

  const take = async (files: FileList | null) => {
    if (!files?.length) return;
    setNames([...files].map((f) => f.name));
    setErr("");
    try {
      await onUpload(files);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "upload failed");
    }
  };

  return (
    <section className="clay-panel mx-auto flex min-h-0 w-full max-w-[920px] flex-1 flex-col justify-center rounded-[36px] px-10 py-12">
      <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
        Delta Ledger · live production
      </p>
      <h2 className="wordmark mt-3 text-[34px] font-bold tracking-tight">
        Why did this quarter move?
      </h2>
      <p className="mt-3 max-w-xl text-[14px] leading-relaxed text-muted-foreground">
        Upload your company's books. The engine reconciles the totals, the router
        ranks the movers, the z-bridge flags what is unusual, and you get a
        leadership memo — then you can open the closer and watch the agent work.
      </p>

      <button
        type="button"
        disabled={starting || !liveOk}
        onClick={() => input.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); void take(e.dataTransfer.files); }}
        className="clay-empty mt-8 flex flex-col items-center gap-3 rounded-[28px] px-8 py-12 text-center disabled:opacity-50"
      >
        <span className="grid h-14 w-14 place-items-center rounded-full"
              style={{ boxShadow: "var(--clay-out)", color: "var(--ring-engine)" }}>
          <UploadCloud className="h-6 w-6" strokeWidth={2.2} />
        </span>
        <span className="text-[15px] font-semibold">
          {starting ? "Reconciling the books…" : "Drop the quarterly books here"}
        </span>
        <span className="text-[12px] text-muted-foreground">
          {names.length ? names.join(" · ") : "SEC · product · geography · users"}
        </span>
      </button>
      <input ref={input} type="file" multiple accept=".csv,.json" className="hidden"
             onChange={(e) => void take(e.target.files)} />

      {(err || liveHint) && (
        <p className="mt-3 text-[12px]" style={{ color: "var(--ring-down)" }}>{err || liveHint}</p>
      )}

      <div className="mt-8 grid gap-3 sm:grid-cols-3">
        {[
          ["1 · Reconcile", "Do the books add up? Σ transactions must equal reported totals."],
          ["2 · Router", "Who owns the move? Lanes ranked by |Δ$|, never % growth."],
          ["3 · Z-bridge", "Is it unusual? Each lane vs its own trailing band."],
        ].map(([t, b]) => (
          <div key={t} className="clay-card rounded-[20px] px-4 py-3.5">
            <div className="text-[12.5px] font-semibold">{t}</div>
            <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">{b}</p>
          </div>
        ))}
      </div>

    </section>
  );
}

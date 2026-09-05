/** Live analysis status + append-only progress strip. */

export function BeatBar({ beat, maxBeat, caption }: {
  beat: number;
  maxBeat: number;
  caption: string;
}) {
  const done = beat >= maxBeat;

  return (
    <div className="shrink-0">
      <div className="mb-3 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4">
        <div className="min-w-0">
          <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Live analysis
          </span>
          <p className="mt-0.5 truncate text-[13px] font-medium text-foreground/85">
            {caption || "—"}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="clay-pill flex items-center gap-2 rounded-full px-4 py-2 text-[12px] font-semibold"
                style={{ color: done ? "var(--ring-up)" : "var(--ring-active)" }}>
            <i className={`block h-2 w-2 rounded-full ${done ? "" : "animate-pulse"}`}
               style={{ background: done ? "var(--ring-up)" : "var(--ring-active)" }} />
            {done ? "analysis complete" : "analyzing…"}
          </span>
          <span className="tabular ml-1 text-[11px] font-semibold text-muted-foreground">
            step {beat}/{maxBeat}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-1">
        {Array.from({ length: maxBeat }, (_, i) => i + 1).map((b) => (
          <span
            key={b}
            className="h-1.5 flex-1 rounded-full transition-all"
            style={{
              background: b <= beat
                ? !done ? "var(--ring-active)" : "var(--ring-engine)"
                : "color-mix(in oklab, var(--foreground) 9%, transparent)",
            }}
          />
        ))}
      </div>
    </div>
  );
}

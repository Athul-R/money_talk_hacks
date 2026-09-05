/**
 * The beat scrubber: caption + transport controls + one segment per beat, so
 * the presenter can replay the analysis growing (◀ ▶, play/pause, click-to-seek).
 */

import { ChevronLeft, ChevronRight, Pause, Play, RotateCcw } from "lucide-react";

export function BeatBar({ beat, maxBeat, caption, playing, onSeek, onPlay }: {
  beat: number;
  maxBeat: number;
  caption: string;
  playing: boolean;
  onSeek: (b: number) => void;
  onPlay: (p: boolean) => void;
}) {
  return (
    <div className="shrink-0">
      <div className="mb-3 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4">
        <div className="min-w-0">
          <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Story
          </span>
          <p className="mt-0.5 truncate text-[13px] font-medium text-foreground/85">
            {caption || "—"}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button type="button" aria-label="Previous beat"
            onClick={() => { onPlay(false); onSeek(Math.max(1, beat - 1)); }}
            className="clay-pill grid h-9 w-9 place-items-center rounded-full text-muted-foreground">
            <ChevronLeft className="h-4 w-4" strokeWidth={2.4} />
          </button>
          <button type="button"
            onClick={() => onPlay(!playing)}
            className="clay-pill-active flex items-center gap-2 rounded-full px-4 py-2 text-[12px] font-semibold"
            style={{ color: "var(--ring-engine)" }}>
            {playing ? <Pause className="h-4 w-4" strokeWidth={2.6} /> : <Play className="h-4 w-4" strokeWidth={2.6} />}
            {playing ? "pause" : beat >= maxBeat ? "replay" : "play"}
          </button>
          <button type="button" aria-label="Next beat"
            onClick={() => { onPlay(false); onSeek(Math.min(maxBeat, beat + 1)); }}
            className="clay-pill grid h-9 w-9 place-items-center rounded-full text-muted-foreground">
            <ChevronRight className="h-4 w-4" strokeWidth={2.4} />
          </button>
          <button type="button" aria-label="Reset story"
            onClick={() => { onPlay(false); onSeek(1); }}
            className="clay-pill grid h-9 w-9 place-items-center rounded-full text-muted-foreground">
            <RotateCcw className="h-4 w-4" strokeWidth={2.4} />
          </button>
          <span className="tabular ml-1 text-[11px] font-semibold text-muted-foreground">
            beat {beat}/{maxBeat}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-1">
        {Array.from({ length: maxBeat }, (_, i) => i + 1).map((b) => (
          <button
            key={b}
            type="button"
            aria-label={`Beat ${b}`}
            onClick={() => { onPlay(false); onSeek(b); }}
            className="h-1.5 flex-1 rounded-full transition-all"
            style={{
              background: b <= beat
                ? "var(--ring-engine)"
                : "color-mix(in oklab, var(--foreground) 9%, transparent)",
            }}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Clay nodes for the lineage canvas, ported from the reference scheduler:
 * pucks (72px — metric, router, branches, outcome) and pips (36px — one
 * analysis stage). Ring color carries state; hover card carries the facts.
 */

import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  Activity, Boxes, Check, FileText, MessageCircleQuestion, Share2, Sigma,
  SlidersHorizontal, X, ZoomIn,
} from "lucide-react";
import type { PipData, PuckData } from "../lib/frame";

function HoverCard({ title, lines, accent, compact = false }: {
  title: string; lines: string[]; accent: string; compact?: boolean;
}) {
  if (!lines.length) return null;
  return (
    <span
      className={`clay-hovercard pointer-events-none absolute bottom-full left-1/2 z-30 mb-3 -translate-x-1/2 rounded-2xl px-3 py-2 text-left opacity-0 transition-all duration-200 group-hover:-translate-y-0.5 group-hover:opacity-100 ${
        compact ? "min-w-[136px]" : "min-w-[172px]"
      }`}
    >
      <span
        className="block whitespace-nowrap text-[11px] font-bold uppercase tracking-[0.1em]"
        style={{ color: accent }}
      >
        {title}
      </span>
      {lines.map((l) => (
        <span key={l} className="mt-0.5 block whitespace-nowrap text-[11px] font-medium leading-[1.5] text-muted-foreground">
          {l}
        </span>
      ))}
    </span>
  );
}

const hiddenHandle = { opacity: 0, width: 1, height: 1, minWidth: 1, minHeight: 1, border: "none" };

export function PuckNode({ data }: NodeProps) {
  const d = data as unknown as PuckData & { label: string };
  return (
    <div className="group relative h-[72px] w-[72px] animate-node-pop">
      <Handle type="target" position={Position.Left} style={hiddenHandle} />
      <Handle type="source" position={Position.Right} style={hiddenHandle} />
      <span className="relative grid h-full w-full place-items-center">
        {d.pulse && (
          <>
            <span className="clay-ripple" style={{ borderColor: d.ring }} />
            <span className="clay-ripple [animation-delay:0.8s]" style={{ borderColor: d.ring }} />
          </>
        )}
        <span
          className={`clay-puck relative grid h-[72px] w-[72px] place-items-center rounded-full transition-transform duration-300 group-hover:-translate-y-0.5 ${d.muted ? "opacity-70" : ""}`}
          style={{
            boxShadow: `var(--clay-out), 0 12px 26px color-mix(in oklab, ${d.ring} 26%, transparent), inset 0 0 0 3px ${d.ring}`,
          }}
        >
          {d.glyph === "sigma" && <Sigma className="h-6 w-6" style={{ color: d.ring }} strokeWidth={2.2} />}
          {d.glyph === "router" && <Share2 className="h-6 w-6" style={{ color: d.ring }} strokeWidth={2.2} />}
          {d.glyph === "check" && <Check className="h-7 w-7" style={{ color: d.ring }} strokeWidth={3} />}
          {!d.glyph && d.initials && (
            <span className="text-[15px] font-semibold tracking-tight text-foreground/80">{d.initials}</span>
          )}
        </span>
        {d.badge && (
          <span
            className="absolute -right-0.5 -top-0.5 grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold text-white"
            style={{ background: "var(--ring-metric)", boxShadow: "0 2px 6px oklch(0.5 0.11 270 / 0.45)" }}
          >
            {d.badge}
          </span>
        )}
        {d.selected && (
          <span className="pointer-events-none absolute -inset-2 rounded-full" style={{ boxShadow: `0 0 0 1.5px ${d.ring}` }} />
        )}
      </span>

      <span className="pointer-events-none absolute left-1/2 top-full mt-3 -translate-x-1/2 text-center">
        <span className="block whitespace-nowrap text-[13px] font-semibold tracking-tight text-foreground">
          {d.label}
        </span>
        <span className="tabular mt-0.5 block whitespace-nowrap text-[11.5px] font-medium" style={{ color: d.ring }}>
          {d.sub}
        </span>
      </span>

      <HoverCard title={d.label} accent={d.ring} lines={d.tooltip ?? []} />
    </div>
  );
}

const PIP_GLYPH: Record<string, typeof Activity> = {
  delta_z: Activity,
  drivers: SlidersHorizontal,
  cluster: Boxes,
  drill: ZoomIn,
  explain: FileText,
  ask: MessageCircleQuestion,
};

export function PipNode({ data }: NodeProps) {
  const d = data as unknown as PipData;
  const capped = d.state === "capped";
  const active = d.state === "active";
  const Glyph = capped ? X : PIP_GLYPH[d.stage] ?? Activity;
  return (
    <div className="group relative h-9 w-9 animate-pip-pop">
      <Handle type="target" position={Position.Left} style={hiddenHandle} />
      <Handle type="source" position={Position.Right} style={hiddenHandle} />
      <span className="relative grid h-full w-full place-items-center" style={{ color: d.ring }}>
        {active && (
          <>
            <span className="clay-ripple-sm" />
            <span className="clay-ripple-sm [animation-delay:0.7s]" />
          </>
        )}
        <span
          className={`clay-puck relative grid h-9 w-9 place-items-center rounded-full transition-transform duration-300 group-hover:-translate-y-0.5 ${active ? "animate-pip-breathe" : ""}`}
          style={{
            boxShadow: `var(--clay-out-sm), 0 6px 14px color-mix(in oklab, ${d.ring} 24%, transparent), inset 0 0 0 2.5px ${d.ring}`,
          }}
        >
          <Glyph className="h-[15px] w-[15px]" style={{ color: d.ring }} strokeWidth={2.6} />
        </span>
        {d.selected && (
          <span className="pointer-events-none absolute -inset-1.5 rounded-full" style={{ boxShadow: `0 0 0 1.5px ${d.ring}` }} />
        )}
      </span>
      <span className="pointer-events-none absolute left-1/2 top-full mt-2 -translate-x-1/2 text-center">
        <span className="block whitespace-nowrap text-[10px] font-semibold tracking-tight" style={{ color: capped ? "var(--ring-down)" : "var(--muted-foreground)" }}>
          {d.label}
        </span>
      </span>
      <HoverCard title={d.stage.replace("_", " ")} accent={d.ring} lines={d.tooltip ?? []} compact />
    </div>
  );
}

export const nodeTypes = { puck: PuckNode, pip: PipNode };

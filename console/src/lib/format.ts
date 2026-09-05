/** Formatting: values are USD millions everywhere (mirror of narrator.fm). */

export function fm(v: number | null | undefined): string {
  if (v == null) return "—";
  const sign = v < 0 ? "-" : "";
  const a = Math.abs(v);
  if (a >= 1000) return `${sign}$${(a / 1000).toLocaleString(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 })}B`;
  if (a >= 1) return `${sign}$${a.toLocaleString(undefined, { maximumFractionDigits: 0 })}M`;
  return `${sign}$${(a * 1000).toLocaleString(undefined, { maximumFractionDigits: 0 })}K`;
}

export function pct(v: number | null | undefined, signed = true): string {
  if (v == null) return "—";
  return `${signed && v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

export function share(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${Math.round(Math.abs(v) * 100)}%`;
}

export function hhmmss(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour12: false });
}

/** ring token for a branch given its state + delta direction */
export function branchRing(state: string, delta: number): string {
  if (state === "capped") return "var(--ring-down)";
  if (state === "active") return "var(--ring-active)";
  return delta >= 0 ? "var(--ring-up)" : "var(--ring-down)";
}

export const STAGE_RING: Record<string, string> = {
  delta_z: "var(--ring-engine)",
  drivers: "var(--ring-metric)",
  cluster: "var(--ring-active)",
  drill: "var(--ring-drill)",
  explain: "var(--ring-up)",
  ask: "var(--ring-memory)",
};

export const TAG_TONE: Record<string, string> = {
  router: "var(--ring-engine)",
  z: "var(--ring-metric)",
  drivers: "var(--ring-metric)",
  cluster: "var(--ring-active)",
  drill: "var(--ring-drill)",
  memory: "var(--ring-memory)",
  explain: "var(--ring-up)",
  capped: "var(--ring-down)",
  ok: "var(--ring-up)",
};

/**
 * Model -> React Flow nodes/edges. Deterministic geometry, same law as the
 * reference scheduler: positions derive from (lane, depth, pip index) only, so
 * the graph GROWS right and down and a node never moves once placed.
 *
 *   root x=40 · router x=260 · branches x=520 + depth·170 · pips march +92
 *   lanes every 138px, assigned once at spawn in rank order (append-only)
 */

import type { Edge, Node } from "@xyflow/react";
import type { FoldedBranch, FoldedPip, Model } from "./fold";
import { branchRing, fm, pct, share, STAGE_RING } from "./format";

export const GEO = {
  rootX: 40,
  routerX: 260,
  branchX: 520,
  indent: 170,
  pipStart: 124,
  pipDX: 92,
  laneGap: 138,
  outcomeGap: 240,
};

const laneY = (lane: number) => lane * GEO.laneGap;

export type PuckData = {
  variant: "root" | "router" | "branch" | "outcome";
  label: string;
  sub: string;
  ring: string;
  glyph?: "sigma" | "router" | "check" | "alert";
  initials?: string;
  pulse?: boolean;
  badge?: string;
  tooltip: string[];
  selected: boolean;
  muted?: boolean;
};

export type PipData = {
  stage: string;
  state: string;
  label: string;
  ring: string;
  tooltip: string[];
  selected: boolean;
};

const initialsOf = (name: string) =>
  name.split(/[\s·]+/).map((w) => w[0] ?? "").join("").slice(0, 2).toUpperCase();

function pipLabel(p: FoldedPip): string {
  const pay = p.payload;
  switch (p.stage) {
    case "delta_z":
      if (p.state === "capped") return "capped";
      return pay.zscore != null ? `z ${(pay.zscore as number) >= 0 ? "+" : ""}${pay.zscore}` : "Δ";
    case "drivers":
      return pay.bridge?.top_driver ? `${pay.bridge.top_driver}-led` : "drivers";
    case "cluster": {
      const top = pay.clusters?.[0];
      return top ? `${share(top.share)} cluster` : "cluster";
    }
    case "drill":
      return `drill ×${pay.children?.length ?? 0}`;
    case "explain":
      return "explain";
    case "ask":
      return "follow-up";
    default:
      return p.stage;
  }
}

function pipTooltip(b: FoldedBranch, p: FoldedPip): string[] {
  const pay = p.payload;
  switch (p.stage) {
    case "delta_z":
      if (p.state === "capped") return [pay.reason ?? "capped"];
      return [
        `Δ ${fm(pay.delta_abs)} (${pct(pay.delta_pct)})`,
        `z ${pay.zscore ?? "—"} vs trailing ${pct(pay.trailing_mean_pct)}`,
        pay.seasonality ?? "",
      ].filter(Boolean);
    case "drivers": {
      const br = pay.bridge;
      const out = br
        ? [`volume ${fm(br.volume)} · price ${fm(br.price)}`, `mix ${fm(br.mix)} · customer ${fm(br.customer)}`]
        : [];
      if (pay.kpi_reconciliation)
        out.push(`identity ${pct(pay.kpi_reconciliation.implied_pct)} vs ${pct(pay.kpi_reconciliation.reported_pct)} reported`);
      return out;
    }
    case "cluster": {
      const out = (pay.clusters ?? []).slice(0, 2).map(
        (c: any) => `${c.label} · ${share(c.share)}`);
      if (pay.concentration)
        out.push(`top ${pay.concentration.top_n} = ${share(pay.concentration.top_n_share)} of Δ`);
      return out;
    }
    case "drill":
      return (pay.children ?? []).map((c: any) => `${c.name} · ${share(c.share)}`);
    case "explain":
      return [(pay.text ?? "").slice(0, 90) + "…"];
    case "ask":
      return [`“${pay.question}”`];
    default:
      return [];
  }
}

function branchTooltip(b: FoldedBranch): string[] {
  const lines = [
    `Δ ${fm(b.deltaAbs)} (${pct(b.deltaPct)})`,
    `share of parent variance · ${share(b.share)}`,
  ];
  if (b.zscore != null) lines.push(`z-score · ${b.zscore >= 0 ? "+" : ""}${b.zscore}`);
  const drivers = b.pips.find((p) => p.stage === "drivers")?.payload?.bridge;
  if (drivers?.top_driver) lines.push(`top driver · ${drivers.top_driver}`);
  const cluster = b.pips.find((p) => p.stage === "cluster")?.payload?.clusters?.[0];
  if (cluster) lines.push(`top cluster · ${cluster.label}`);
  if (b.capReason) lines.push(`capped · ${b.capReason}`);
  return lines;
}

export function frame(model: Model, selected: string | null) {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const running = !model.complete;

  const top = [...model.branches.values()].filter((b) => b.depth === 0);
  const rootY = top.length ? ((top.length - 1) / 2) * GEO.laneGap : 1.5 * GEO.laneGap;

  const puck = (id: string, x: number, y: number, data: PuckData) =>
    nodes.push({
      id, type: "puck", position: { x: x - 36, y: y - 36 },
      data: { ...data, selected: selected === id },
      draggable: false, selectable: false,
    });
  const pip = (id: string, x: number, y: number, data: PipData) =>
    nodes.push({
      id, type: "pip", position: { x: x - 18, y: y - 18 },
      data: { ...data, selected: selected === id },
      draggable: false, selectable: false,
    });

  if (!model.run) return { nodes, edges, rootY };

  puck("root", GEO.rootX, rootY, {
    variant: "root",
    label: model.run.metric,
    sub: model.root ? `${pct(model.root.delta_pct)} · ${fm(model.root.delta_abs)}` : "…",
    ring: "var(--ring-metric)",
    glyph: "sigma",
    pulse: running && !model.axis,
    tooltip: model.root
      ? [
          `${model.run.period_a} → ${model.run.period_b}`,
          `${fm(model.root.value_a)} → ${fm(model.root.value_b)}`,
          `control totals ${model.reconciliationOk ? "reconcile ✓" : "MISMATCH ✗"}`,
        ]
      : [],
    selected: false,
  });

  if (model.axis || model.candidates.length) {
    puck("router", GEO.routerX, rootY, {
      variant: "router",
      label: "variance router",
      sub: model.axis ? `axis · ${model.axis}` : "scoring axes…",
      ring: "var(--ring-engine)",
      glyph: "router",
      pulse: running && model.branches.size === 0,
      tooltip: model.candidates.map(
        (c: any) => `${c.axis} · power ${c.power}${c.note ? ` · ${c.note}` : ""}`),
      selected: false,
    });
    edges.push({
      id: "e-root-router", source: "root", target: "router", type: "smoothstep",
      animated: running,
      style: { stroke: "var(--ring-metric)", strokeWidth: 2 },
    });
  }

  let maxX = GEO.routerX;

  for (const id of model.order) {
    const b = model.branches.get(id)!;
    const bx = GEO.branchX + b.depth * GEO.indent;
    const by = laneY(b.lane);
    // line items color by CONTRIBUTION: COGS rising drags the metric down,
    // so its lane rings crimson even though its own delta is positive.
    const direction = b.dimension === "line_item" ? b.share : b.deltaAbs;
    const ring = branchRing(b.state, direction);
    const capped = b.state === "capped";

    puck(b.id, bx, by, {
      variant: "branch",
      label: b.name,
      sub: capped ? `capped · ${share(b.share)}` : `${fm(b.deltaAbs)} · ${share(b.share)}`,
      ring,
      initials: initialsOf(b.name),
      pulse: b.state === "active",
      muted: capped,
      badge: b.zscore != null && Math.abs(b.zscore) >= 2 ? "z" : undefined,
      tooltip: branchTooltip(b),
      selected: false,
    });

    // lineage edge: router feeds depth-0 lanes; a drill pip feeds children.
    if (b.depth === 0) {
      edges.push({
        id: `e-router-${b.id}`, source: "router", target: b.id, type: "smoothstep",
        animated: b.state === "active",
        label: `${b.deltaAbs >= 0 ? "+" : "−"}${fm(Math.abs(b.deltaAbs)).replace("$", "$")} · ${share(b.share)}`,
        labelStyle: { fill: "var(--muted-foreground)", fontSize: 10, fontWeight: 650 },
        pathOptions: { borderRadius: 22, offset: 14 + b.lane * 8 },
        style: {
          stroke: capped ? "var(--edge-idle)" : ring, strokeWidth: capped ? 1.75 : 2,
          ...(capped ? { strokeDasharray: "6 6", opacity: 0.8 } : {}),
        },
      } as Edge);
    } else if (b.parentId) {
      const parent = model.branches.get(b.parentId);
      const drillPip = parent?.pips.find((p) => p.stage === "drill");
      edges.push({
        id: `e-drill-${b.id}`,
        source: drillPip ? drillPip.id : b.parentId, target: b.id, type: "smoothstep",
        animated: b.state === "active",
        pathOptions: { borderRadius: 22, offset: 10 + (b.lane % 6) * 7 },
        style: {
          stroke: capped ? "var(--edge-idle)" : "var(--ring-drill)",
          strokeWidth: capped ? 1.5 : 2,
          ...(capped ? { strokeDasharray: "6 6", opacity: 0.8 } : {}),
        },
      } as Edge);
    }

    // pip chain, compact append order (stage_idx sorted; never re-sorts).
    const ordered = [...b.pips].sort((a, z) => a.stageIdx - z.stageIdx);
    let prev = b.id;
    ordered.forEach((p, k) => {
      const px = bx + GEO.pipStart + k * GEO.pipDX;
      maxX = Math.max(maxX, px);
      pip(p.id, px, by, {
        stage: p.stage,
        state: p.state,
        label: pipLabel(p),
        ring: p.state === "capped" ? "var(--ring-down)" : STAGE_RING[p.stage] ?? "var(--ring-idle)",
        tooltip: pipTooltip(b, p),
        selected: false,
      });
      edges.push({
        id: `e-${prev}-${p.id}`, source: prev, target: p.id, type: "smoothstep",
        pathOptions: { borderRadius: 16 },
        style: {
          stroke: p.state === "capped" ? "var(--ring-down)" : "var(--edge-idle)",
          strokeWidth: 1.75,
          ...(p.state === "capped" ? { strokeDasharray: "1 6" } : {}),
        },
      } as Edge);
      prev = p.id;
    });
    maxX = Math.max(maxX, bx);
  }

  if (model.complete && model.outcome) {
    const x = maxX + GEO.outcomeGap;
    puck("outcome", x, rootY, {
      variant: "outcome",
      label: "Explained",
      sub: `${Math.round(model.complete.explained * 100)}% of the move`,
      ring: "var(--ring-up)",
      glyph: "check",
      tooltip: ["leadership summary ready", "click for memo + evidence tree"],
      selected: false,
    });
    // the biggest explained lane hands off to the outcome — the "winner" edge.
    const winner = [...model.branches.values()]
      .filter((b) => b.depth === 0 && b.state === "done")
      .sort((a, z) => Math.abs(z.deltaAbs) - Math.abs(a.deltaAbs))[0];
    const from = winner
      ? [...winner.pips].sort((a, z) => a.stageIdx - z.stageIdx).at(-1)?.id ?? winner.id
      : "router";
    edges.push({
      id: "e-outcome", source: from, target: "outcome", type: "smoothstep",
      animated: true,
      pathOptions: { borderRadius: 22 },
      style: { stroke: "var(--ring-up)", strokeWidth: 2.5 },
    } as Edge);
  }

  return { nodes, edges, rootY };
}

/** Breadcrumb for a selected node: Revenue › Cloud › Enterprise › Helios. */
export function breadcrumb(model: Model, selected: string | null): string[] {
  if (!model.run) return [];
  const trail = [model.run.metric];
  if (!selected) return trail;
  let branch =
    model.branches.get(selected) ??
    [...model.branches.values()].find((b) => b.pips.some((p) => p.id === selected));
  const chain: string[] = [];
  while (branch) {
    chain.unshift(branch.name);
    branch = branch.parentId ? model.branches.get(branch.parentId) : undefined;
  }
  return [...trail, ...chain];
}

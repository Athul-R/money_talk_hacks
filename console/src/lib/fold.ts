/**
 * Event-sourced replay: fold events[0..k] into the picture the graph draws.
 * One code path for everything — the beat scrubber replays a stored run, and a
 * future realtime feed just folds rows as they arrive (the UI never polls).
 */

import type { Ask, EventRow } from "./types";

export type FoldedPip = {
  id: string;
  branchId: string;
  stage: string;
  stageIdx: number;
  state: string;
  payload: Record<string, any>;
};

export type FoldedBranch = {
  id: string;
  parentId: string | null;
  depth: number;
  dimension: string;
  name: string;
  lane: number;
  valueA: number;
  valueB: number;
  deltaAbs: number;
  deltaPct: number | null;
  share: number;
  zscore: number | null;
  state: string;
  pips: FoldedPip[];
  capReason?: string;
};

export type Model = {
  run: Record<string, any> | null;
  root: Record<string, any> | null; // delta stats of the metric total
  reconciliationOk: boolean;
  webContext: { query: string; sources: any[] } | null;
  axis: string | null;
  candidates: any[];
  recalled: { kind: string; key?: string; text: string }[];
  learned: { kind: string; key: string; text: string }[];
  promoted: { kind: string; key: string; text: string }[];
  branches: Map<string, FoldedBranch>;
  order: string[]; // branch ids in lane order (append-only)
  outcome: { text: string; claims: any[]; evidence: Record<string, any> } | null;
  complete: { explained: number; summaryMd: string } | null;
  maxBeat: number;
};

function upsertPip(b: FoldedBranch, pip: Record<string, any>) {
  const idx = b.pips.findIndex((p) => p.id === pip.id);
  const folded: FoldedPip = {
    id: pip.id,
    branchId: pip.branch_id,
    stage: pip.stage,
    stageIdx: pip.stage_idx,
    state: pip.state,
    payload: pip.payload ?? {},
  };
  if (idx === -1) b.pips.push(folded);
  else b.pips[idx] = folded;
}

function addBranch(model: Model, row: Record<string, any>) {
  if (model.branches.has(row.id)) return;
  model.branches.set(row.id, {
    id: row.id,
    parentId: row.parent_branch_id ?? null,
    depth: row.depth,
    dimension: row.dimension,
    name: row.name,
    lane: row.lane,
    valueA: row.value_a,
    valueB: row.value_b,
    deltaAbs: row.delta_abs,
    deltaPct: row.delta_pct,
    share: row.share,
    zscore: row.zscore ?? null,
    state: "active",
    pips: [],
  });
  model.order.push(row.id);
}

export function fold(events: EventRow[], upto: number, asks: Ask[] = []): Model {
  const model: Model = {
    run: null, root: null, reconciliationOk: true, webContext: null,
    axis: null, candidates: [],
    recalled: [], learned: [], promoted: [],
    branches: new Map(), order: [], outcome: null, complete: null,
    maxBeat: events.length ? events[events.length - 1]!.payload.beat : 0,
  };

  for (const ev of events) {
    const p = ev.payload;
    if (p.beat > upto) break;
    const branch = ev.branch_id ? model.branches.get(ev.branch_id) : undefined;

    switch (ev.kind) {
      case "run_started":
        model.run = p.run;
        model.root = p.root;
        model.reconciliationOk = p.reconciliation?.ok ?? true;
        break;
      case "web_context":
        model.webContext = {
          query: p.sources?.[0]?.query ?? "",
          sources: p.sources ?? [],
        };
        break;
      case "axis_selected":
        model.axis = p.axis;
        model.candidates = p.candidates ?? [];
        break;
      case "memory_recalled":
        model.recalled = p.hits ?? [];
        break;
      case "branch_ranked":
        for (const row of p.branches ?? []) addBranch(model, row);
        break;
      case "drill_spawned":
        if (branch && p.pip) upsertPip(branch, p.pip);
        for (const row of p.children ?? []) addBranch(model, row);
        break;
      case "zscore_flagged":
      case "attribution_done":
      case "cluster_found":
        if (branch && p.pip) {
          upsertPip(branch, p.pip);
          if (ev.kind === "zscore_flagged") branch.zscore = p.pip.payload?.zscore ?? branch.zscore;
        }
        break;
      case "concentration_flagged":
        break; // data already lives on the cluster pip; event is for the log
      case "branch_capped":
        if (branch) {
          if (p.pip) upsertPip(branch, p.pip);
          branch.state = "capped";
          branch.capReason = p.reason;
        }
        break;
      case "explanation_ready":
        if (p.outcome) {
          model.outcome = { text: p.text, claims: p.claims ?? [], evidence: p.evidence ?? {} };
        } else if (branch) {
          if (p.pip) upsertPip(branch, p.pip);
          branch.state = "done";
        }
        break;
      case "memory_learned":
        model.learned = p.learned ?? [];
        model.promoted = p.promoted ?? [];
        break;
      case "run_complete":
        model.complete = { explained: p.explained_share, summaryMd: p.summary_md };
        break;
    }
  }

  // Follow-up asks append as extra pips on their branch.
  for (const ask of asks) {
    const b = model.branches.get(ask.branchId);
    if (b && model.complete) {
      upsertPip(b, {
        id: `ask-${ask.branchId}-${ask.at}`,
        branch_id: ask.branchId,
        stage: "ask",
        stage_idx: 90 + b.pips.filter((p) => p.stage === "ask").length,
        state: "done",
        payload: { question: ask.question, text: ask.text },
      });
    }
  }

  return model;
}

/** Beat captions for the scrubber: beat number -> last caption at or before it. */
export function captions(events: EventRow[]): Map<number, string> {
  const map = new Map<number, string>();
  let last = "";
  let beat = 0;
  for (const ev of events) {
    if (ev.payload.caption) last = ev.payload.caption;
    beat = ev.payload.beat;
    map.set(beat, last);
  }
  for (let i = 1; i <= beat; i++) if (!map.has(i)) map.set(i, map.get(i - 1) ?? "");
  return map;
}

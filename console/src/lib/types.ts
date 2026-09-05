/**
 * Row shapes mirror backend/fpa bundles 1:1 (and data/schema.sql). The console
 * derives EVERYTHING from the events list, so replaying a stored run and
 * folding a live realtime feed are the same code path.
 */

export type EventRow = {
  id: number;
  run_id: string;
  branch_id: string | null;
  kind: string;
  at: string;
  payload: Record<string, any>;
};

export type BranchRow = {
  id: string;
  run_id: string;
  parent_branch_id: string | null;
  depth: number;
  dimension: string;
  name: string;
  lane: number;
  value_a: number;
  value_b: number;
  delta_abs: number;
  delta_pct: number | null;
  share: number;
  zscore: number | null;
  state: "active" | "done" | "capped";
  evidence: Record<string, any>;
};

export type PipRow = {
  id: string;
  branch_id: string;
  stage: "delta_z" | "drivers" | "cluster" | "drill" | "explain" | "ask";
  stage_idx: number;
  state: "waiting" | "active" | "done" | "capped";
  payload: Record<string, any>;
  at: string;
};

export type RunMeta = {
  id: string;
  company: string;
  dataset: string;
  metric: string;
  period_a: string;
  period_b: string;
  status: string;
  summary_md: string;
  explained_share: number;
  memory_delta: number;
  promoted: number;
  beats: number;
  created_at: string;
};

export type MemoryRow = {
  id: string;
  company_id: string;
  kind: string;
  key: string;
  value: Record<string, any>;
  evidence_run_ids: string[];
  updated_at: string;
  text?: string;
};

export type RunBundle = {
  company: { id: string; name: string };
  dataset: { name: string; periods: string[]; reconciliation: { ok: boolean; checks: any[] } };
  run: RunMeta;
  branches: BranchRow[];
  pips: PipRow[];
  events: EventRow[];
  recalled: { kind: string; text: string }[];
  learned: { kind: string; key: string; text: string }[];
  promoted: { kind: string; key: string; text: string }[];
  memory_after: MemoryRow[];
};

export type RunIndexEntry = {
  file: string;
  id: string;
  metric: string;
  period_a: string;
  period_b: string;
  status: string;
  explained_share: number;
  memory_delta: number;
  recalled: number;
  promoted: number;
  created_at: string;
  beats: number;
};

export type MockIndex = {
  company: { id: string; name: string };
  dataset: { name: string; periods: string[]; reconciliation: { ok: boolean; checks: any[] } };
  runs: RunIndexEntry[];
  memory: MemoryRow[];
};

/** A follow-up asked on a node (mock mode keeps these client-side). */
export type Ask = { branchId: string; question: string; text: string; at: string };

export const EVIDENCE_TAGS = {
  reported_fact: { label: "reported fact", cssVar: "--tag-fact" },
  calculated_attribution: { label: "calculated", cssVar: "--tag-calc" },
  management_commentary: { label: "mgmt commentary", cssVar: "--tag-mgmt" },
  agent_inference: { label: "agent inference", cssVar: "--tag-inference" },
} as const;

export type EvidenceTag = keyof typeof EVIDENCE_TAGS;

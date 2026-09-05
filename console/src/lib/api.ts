/** Live backend. Vite proxies /api → :8000. */

import type { Ask, ConsoleIndex, RunBundle, RunIndexEntry } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";

export type LiveCatalog = ConsoleIndex & {
  datasets: {
    id: string;
    name: string;
    periods?: string[];
    reconciliation?: { ok: boolean; checks: any[] };
    files?: string[];
    seed?: boolean;
  }[];
  prism?: boolean;
  metrics?: string[];
};

export type Health = { ok: boolean; given: boolean; prism: boolean; llm: boolean };

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init);
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      detail = body.detail || JSON.stringify(body);
    } catch { /* keep statusText */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return r.json() as Promise<T>;
}

export function health(): Promise<Health> {
  return json("/health");
}

export function catalog(): Promise<LiveCatalog> {
  return json("/catalog");
}

export function getRun(id: string): Promise<RunBundle> {
  return json(`/runs/${id}`);
}

export function startRun(body: {
  dataset_id: string;
  metric: string;
  period_a: string;
  period_b: string;
  company?: string;
}): Promise<RunBundle> {
  return json("/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function uploadDataset(files: FileList | File[], company = "Company"): Promise<{
  id: string; name: string; periods: string[];
  reconciliation: { ok: boolean; checks: any[] }; files: string[];
}> {
  const fd = new FormData();
  fd.append("company", company);
  for (const f of Array.from(files)) fd.append("files", f);
  return json("/datasets", { method: "POST", body: fd });
}

export async function ask(runId: string, branchId: string, question: string): Promise<Ask> {
  const row = await json<{ branch_id: string; question: string; text: string }>(
    `/runs/${runId}/ask`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ branch_id: branchId, question }),
    },
  );
  return { branchId: row.branch_id, question: row.question, text: row.text, at: new Date().toISOString() };
}

export function indexRun(bundle: RunBundle): RunIndexEntry {
  return {
    file: bundle.run.id,
    id: bundle.run.id,
    metric: bundle.run.metric,
    period_a: bundle.run.period_a,
    period_b: bundle.run.period_b,
    status: bundle.run.status,
    explained_share: bundle.run.explained_share,
    memory_delta: bundle.run.memory_delta,
    recalled: (bundle.recalled || []).length,
    promoted: bundle.run.promoted,
    created_at: bundle.run.created_at,
    beats: bundle.run.beats,
    source: "live",
  };
}

/**
 * Mock mode: the baked bundles under src/mock are REAL engine output
 * (backend/scripts/make_mock.py) — the console replays them as beats. When the
 * backend is wired, the same fold/frame path consumes live rows instead.
 */

import type { MockIndex, RunBundle } from "./types";
import indexJson from "../mock/index.json";

export const mockIndex = indexJson as unknown as MockIndex;

const loaders: Record<string, () => Promise<{ default: unknown }>> = {
  "run-1.json": () => import("../mock/run-1.json"),
  "run-2.json": () => import("../mock/run-2.json"),
  "run-3.json": () => import("../mock/run-3.json"),
};

export async function loadBundle(file: string): Promise<RunBundle> {
  const loader = loaders[file];
  if (!loader) throw new Error(`unknown mock bundle ${file}`);
  const mod = await loader();
  return mod.default as RunBundle;
}

/** The demo default: the hero run (Revenue 2025-Q2 → 2026-Q2). */
export const DEFAULT_RUN_FILE = "run-2.json";

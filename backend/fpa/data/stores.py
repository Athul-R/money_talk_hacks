"""LocalStore: JSON files under backend/.fpa_state — runs, memory, datasets.
SupabaseWriter: best-effort row inserts matching data/schema.sql; every method
is a no-op when SUPABASE_URL/SERVICE_KEY are absent, and failures never break a
run (the local bundle is always the source of truth for replay)."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import STATE_DIR, SUPABASE_SERVICE_KEY, SUPABASE_URL


class LocalStore:
    def __init__(self, root: Path | None = None):
        self.root = root or STATE_DIR
        (self.root / "runs").mkdir(parents=True, exist_ok=True)
        (self.root / "datasets").mkdir(parents=True, exist_ok=True)

    # ── runs ─────────────────────────────────────────────────────────────

    def save_run(self, bundle: dict) -> None:
        path = self.root / "runs" / f"{bundle['run']['id']}.json"
        path.write_text(json.dumps(bundle, indent=1))

    def load_run(self, run_id: str) -> dict | None:
        path = self.root / "runs" / f"{run_id}.json"
        return json.loads(path.read_text()) if path.exists() else None

    def list_runs(self) -> list[dict]:
        out = []
        for path in sorted((self.root / "runs").glob("*.json")):
            bundle = json.loads(path.read_text())
            run = bundle["run"]
            out.append({k: run[k] for k in
                        ("id", "metric", "period_a", "period_b", "status",
                         "explained_share", "created_at", "company", "dataset")
                        if k in run})
        return sorted(out, key=lambda r: r.get("created_at", ""), reverse=True)

    # ── memory ───────────────────────────────────────────────────────────

    def load_memory(self) -> list[dict]:
        path = self.root / "memory.json"
        return json.loads(path.read_text()) if path.exists() else []

    def save_memory(self, rows: list[dict]) -> None:
        (self.root / "memory.json").write_text(json.dumps(rows, indent=1))

    # ── datasets ─────────────────────────────────────────────────────────

    def dataset_dir(self, dataset_id: str) -> Path:
        d = self.root / "datasets" / dataset_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def list_datasets(self) -> list[dict]:
        out = []
        for d in (self.root / "datasets").iterdir():
            meta = d / "meta.json"
            if meta.exists():
                out.append(json.loads(meta.read_text()))
        return out


class SupabaseWriter:
    """Streams engine rows into Supabase as the run progresses, so the console's
    realtime subscription animates the graph live. Import is lazy: the supabase
    package is an optional extra."""

    def __init__(self) -> None:
        self.client = None
        if SUPABASE_URL and SUPABASE_SERVICE_KEY:
            try:
                from supabase import create_client  # type: ignore

                self.client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            except Exception:
                self.client = None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def _insert(self, table: str, row: dict) -> None:
        if not self.client:
            return
        try:
            self.client.table(table).insert(row).execute()
        except Exception:
            pass  # local bundle stays authoritative

    def _upsert(self, table: str, row: dict, on: str) -> None:
        if not self.client:
            return
        try:
            self.client.table(table).upsert(row, on_conflict=on).execute()
        except Exception:
            pass

    # Row shapes mirror data/schema.sql exactly.

    def company(self, row: dict) -> None:
        self._upsert("companies", row, "id")

    def dataset(self, row: dict) -> None:
        self._upsert("datasets", row, "id")

    def run(self, row: dict) -> None:
        self._upsert("runs", row, "id")

    def branch(self, row: dict) -> None:
        self._upsert("branches", row, "id")

    def pip(self, row: dict) -> None:
        self._upsert("pips", row, "id")

    def event(self, row: dict) -> None:
        self._insert("events", {k: v for k, v in row.items() if k != "id"})

    def memory(self, row: dict) -> None:
        self._upsert("memory", row, "company_id,kind,key")

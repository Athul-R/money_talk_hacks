"""Bake the demo story: run the REAL engine on the fixtures three times with a
shared memory store, and write the bundles into console/src/mock so the console
plays the full flow with zero backend or keys.

    run 1  Revenue          2025-Q1 → 2026-Q1   (background quarter; seeds memory)
    run 2  Revenue          2025-Q2 → 2026-Q2   (the hero — recalls run 1, drills to customers)
    run 3  Operating income 2025-Q2 → 2026-Q2   (profitability follow-up; cites run 2 instead of re-drilling)

Deterministic: fixed run ids, fixed start clocks. Every number in the mock is an
engine output — the console never invents one.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from fpa.config import FIXTURES_DIR, Materiality  # noqa: E402
from fpa.engine.normalize import load  # noqa: E402
from fpa.engine.run import Runner  # noqa: E402
from fpa.memory.store import MemoryStore, humanize  # noqa: E402

MOCK_DIR = BACKEND.parent / "console" / "src" / "mock"
COMPANY_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "fpa:company:auric"))

RUNS = [
    ("Revenue", "2025-Q1", "2026-Q1", datetime(2026, 4, 18, 9, 12, tzinfo=timezone.utc)),
    ("Revenue", "2025-Q2", "2026-Q2", datetime(2026, 7, 21, 8, 47, tzinfo=timezone.utc)),
    ("Operating income", "2025-Q2", "2026-Q2", datetime(2026, 7, 21, 10, 3, tzinfo=timezone.utc)),
]


def main() -> None:
    ds = load(FIXTURES_DIR, name="auric-fy26")
    assert ds.reconciliation.ok, "fixtures failed reconciliation"
    memory = MemoryStore()
    cfg = Materiality()

    MOCK_DIR.mkdir(parents=True, exist_ok=True)
    index = []
    for i, (metric, pa, pb, started) in enumerate(RUNS, start=1):
        before = len(memory.rows)
        runner = Runner(
            ds, company_id=COMPANY_ID, company_name="Auric Technologies",
            cfg=cfg, memory_store=memory,
            run_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"fpa:run:{i}")),
            started_at=started,
        )
        bundle = runner.run(metric, pa, pb)
        path = MOCK_DIR / f"run-{i}.json"
        path.write_text(json.dumps(bundle, indent=None))
        run = bundle["run"]
        index.append({
            "file": f"run-{i}.json", "id": run["id"], "metric": metric,
            "period_a": pa, "period_b": pb, "status": run["status"],
            "explained_share": run["explained_share"],
            "memory_delta": len(memory.rows) - before,
            "recalled": len(bundle["recalled"]),
            "promoted": run["promoted"],
            "created_at": run["created_at"],
            "beats": run["beats"],
        })
        print(f"run {i}: {metric} {pa}→{pb} · explained "
              f"{run['explained_share']:.0%} · beats {run['beats']} · "
              f"recalled {len(bundle['recalled'])} · +{len(memory.rows) - before} memories"
              f" · promoted {run['promoted']}")

    (MOCK_DIR / "index.json").write_text(json.dumps({
        "company": {"id": COMPANY_ID, "name": "Auric Technologies"},
        "dataset": {"name": "auric-fy26", "periods": ds.periods,
                    "reconciliation": ds.reconciliation.as_dict()},
        "runs": index,
        "memory": [{**r, "text": humanize(r)} for r in memory.rows],
    }, indent=None))
    print(f"mock written to {MOCK_DIR} · {len(memory.rows)} memory rows")


if __name__ == "__main__":
    main()

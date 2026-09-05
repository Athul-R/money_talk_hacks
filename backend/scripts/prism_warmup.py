"""Run the given-data agent once so PRISM has Observe → Improve → Prove
data before the hackathon. No keys = still runs the engine, then prints
exactly which env vars to paste.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fpa import observe
from fpa.config import GIVEN_DIR, LLM_API_KEY, Materiality
from fpa.engine.given import load_given
from fpa.engine.run import Runner
from fpa.memory.store import MemoryStore


def main() -> int:
    print("dataset :", GIVEN_DIR)
    print("prism   :", "ON" if observe.enabled() else "OFF (need API key + project id)")
    print("host    :", observe.HOST)
    print("project :", (observe.PROJECT_ID or "")[:8] + "…" if observe.PROJECT_ID else "(none)")
    print("llm     :", "ON" if LLM_API_KEY else "OFF (templated narration is fine)")
    if not (GIVEN_DIR / "sec_metrics.csv").exists():
        print("missing data/given/sec_metrics.csv")
        return 1

    if observe.enabled():
        doctor = observe.ping()
        print("doctor  :", "ok" if doctor.get("ok") else doctor)
        hello = observe.trace(
            session_id="delta-ledger-warmup",
            user="Warmup: explain Alphabet Revenue 2025-Q2 → 2026-Q2.",
            output="Delta Ledger warmup. Cloud and Search carry the move. "
                   "Open Traces and look for agent delta-ledger.",
            latency_ms=12,
            kind="warmup",
        )
        print("hello   :", "trace sent" if hello else observe.LAST_ERROR)

    ds = load_given(GIVEN_DIR, company="Alphabet", name="alphabet-given")
    print("recon   :", "ok" if ds.reconciliation.ok else "FAIL",
          f"· {len(ds.periods)} periods")

    run_id = str(uuid.uuid4())
    from fpa.agent.providers import SESSION_ID

    SESSION_ID.set(run_id)
    bundle = Runner(
        ds, company_id="warmup", company_name="Alphabet",
        cfg=Materiality(), memory_store=MemoryStore(), run_id=run_id,
    ).run("Revenue", "2025-Q2", "2026-Q2")
    traj = observe.trace_run(bundle)
    run = bundle["run"]
    print(f"run     : {run['metric']} {run['period_a']} → {run['period_b']}")
    print(f"explained {run['explained_share']:.0%} · {run['beats']} beats · "
          f"{len(bundle['branches'])} lanes")
    if observe.enabled():
        print("trajectory:", "sent" if traj else observe.LAST_ERROR)
        print("open    :", f"{observe.HOST.rstrip('/')}/traces")
        return 0 if hello or traj else 1
    print()
    print("To seed PRISM before the hackathon, add to .env:")
    print("  PRISMTRACE_API_KEY=pt-sk-...")
    print("  PRISMTRACE_PROJECT_ID=<your project uuid>")
    print("  PRISMTRACE_HOST=https://prism.blockconvey.com")
    print("Then: make prism-warmup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

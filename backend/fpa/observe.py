"""PRISM — Observe → Improve → Prove.

Uses prismtrace-sdk when PRISMTRACE_API_KEY + PRISMTRACE_PROJECT_ID are set.
Missing keys = no-op so the mock demo still runs. Send one LLM trace per
narration, plus one trajectory per finished run so the hackathon project
has data before tomorrow.
"""

from __future__ import annotations

import os
import time

from .config import LLM_MODEL, LLM_PROVIDER, PRISMTRACE_API_KEY, PRISMTRACE_HOST, PRISMTRACE_PROJECT_ID

HOST = PRISMTRACE_HOST or os.getenv("PRISMTRACE_HOST", "https://prism.blockconvey.com")
API_KEY = PRISMTRACE_API_KEY
PROJECT_ID = PRISMTRACE_PROJECT_ID
AGENT_ID = os.getenv("PRISMTRACE_AGENT_ID", "delta-ledger")
LAST_ERROR = ""


def enabled() -> bool:
    return bool(API_KEY and PROJECT_ID)


def _client():
    if not enabled():
        return None
    try:
        from prismtrace import PRISMtrace  # type: ignore

        return PRISMtrace(api_key=API_KEY, host=HOST, project_id=PROJECT_ID)
    except Exception:
        return None


def trace(*, session_id: str, user: str, output: str, latency_ms: int,
          kind: str = "narrate") -> bool:
    global LAST_ERROR
    if not enabled():
        LAST_ERROR = "PRISM keys missing"
        return False
    model = LLM_MODEL or LLM_PROVIDER or "templated"
    client = _client()
    try:
        if client is not None:
            client.trace_llm(
                model=model,
                input_messages=[{"role": "user", "content": user[:4000]}],
                output=(output or "")[:4000],
                latency_ms=latency_ms,
                agent_id=AGENT_ID,
                agent_name=AGENT_ID,
                metadata={"kind": kind, "session_id": session_id,
                          "observe": "explain-the-change"},
            )
            LAST_ERROR = ""
            return True
        import httpx

        r = httpx.post(
            f"{HOST.rstrip('/')}/api/traces",
            headers={"Content-Type": "application/json", "X-PRISMtrace-Key": API_KEY},
            json={
                "project_id": PROJECT_ID,
                "api_key": API_KEY,
                "model": model,
                "input_messages": [{"role": "user", "content": user[:4000]}],
                "output_message": (output or "")[:4000],
                "latency_ms": latency_ms,
                "session_id": session_id,
                "agent_id": AGENT_ID,
                "metadata": {"kind": kind, "observe": "explain-the-change"},
            },
            timeout=8.0,
        )
        if r.status_code >= 300:
            LAST_ERROR = f"trace HTTP {r.status_code}: {r.text[:240]}"
            return False
        LAST_ERROR = ""
        return True
    except Exception as exc:
        LAST_ERROR = str(exc)
        return False


def timed_complete(fn, *, session_id: str, user: str, kind: str = "narrate"):
    t0 = time.perf_counter()
    out = fn()
    # Always emit a trace so a keyless templated run still seeds PRISM when
    # keys are present — Observe needs *a* run, not only LLM-polished ones.
    text = out if out is not None else "(templated narration — no LLM key)"
    trace(session_id=session_id, user=user, output=text,
          latency_ms=int((time.perf_counter() - t0) * 1000), kind=kind)
    return out


def ping() -> dict:
    """Hit setup-doctor so we know the key/project pair is live."""
    global LAST_ERROR
    if not enabled():
        LAST_ERROR = "PRISM keys missing"
        return {"ok": False, "error": LAST_ERROR}
    try:
        import httpx

        r = httpx.get(
            f"{HOST.rstrip('/')}/api/setup-doctor",
            params={"project_id": PROJECT_ID},
            headers={"X-PRISMtrace-Key": API_KEY},
            timeout=10.0,
        )
        body = {}
        try:
            body = r.json()
        except Exception:
            body = {"text": r.text[:300]}
        if r.status_code >= 300:
            LAST_ERROR = f"setup-doctor HTTP {r.status_code}"
            return {"ok": False, "status": r.status_code, **body}
        LAST_ERROR = ""
        return {"ok": True, "status": r.status_code, **body}
    except Exception as exc:
        LAST_ERROR = str(exc)
        return {"ok": False, "error": str(exc)}


def trace_run(bundle: dict) -> bool:
    """One trajectory for the finished run — the Prove artifact."""
    global LAST_ERROR
    if not enabled():
        LAST_ERROR = "PRISM keys missing"
        return False
    client = _client()
    if client is None or not hasattr(client, "submit_trajectory"):
        LAST_ERROR = "prismtrace-sdk missing submit_trajectory"
        return False
    run = bundle.get("run") or {}
    steps = []
    for ev in (bundle.get("events") or [])[:48]:
        payload = ev.get("payload") or {}
        kind = ev.get("kind", "")
        step_type = "final_answer" if kind in ("explanation_ready", "run_complete") else (
            "tool_call" if kind in ("attribution_done", "cluster_found", "drill_spawned")
            else "reasoning"
        )
        steps.append({
            "step_type": step_type,
            "label": payload.get("title") or kind,
            "input_summary": kind,
            "output_summary": str(payload.get("detail") or payload.get("caption") or "")[:240],
            "duration_ms": 80,
        })
    if not steps:
        LAST_ERROR = "no events to submit"
        return False
    try:
        client.submit_trajectory(
            steps=steps,
            agent_name=AGENT_ID,
            agent_id=AGENT_ID,
            conversation_id=run.get("id"),
            model=LLM_MODEL or LLM_PROVIDER or "templated",
        )
        LAST_ERROR = ""
        return True
    except Exception as exc:
        LAST_ERROR = str(exc)
        return False

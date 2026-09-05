"""LLM client — Claude (Anthropic) by default, OpenAI optional. Template fallback if no key."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from fpa_agent.env import load_env


def _anthropic_key() -> str | None:
    return os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")


def _openai_key() -> str | None:
    return os.getenv("FPA_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")


def llm_available() -> bool:
    load_env()
    return bool(_anthropic_key() or _openai_key())


def complete(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> str:
    """Complete with Claude if ANTHROPIC_API_KEY / CLAUDE_API_KEY is set, else OpenAI.

    Env (repo `.env` or shell):
      ANTHROPIC_API_KEY or CLAUDE_API_KEY   (preferred)
      FPA_LLM_MODEL (default claude-haiku-4-5)
      OPENAI_API_KEY / FPA_LLM_API_KEY      (optional fallback)
    """
    load_env()
    if _anthropic_key():
        return _complete_anthropic(
            system, user, model=model, temperature=temperature, max_tokens=max_tokens
        )
    if _openai_key():
        return _complete_openai(
            system, user, model=model, temperature=temperature, max_tokens=max_tokens
        )
    return _fallback(system, user)


def _complete_anthropic(
    system: str,
    user: str,
    *,
    model: str | None,
    temperature: float,
    max_tokens: int,
) -> str:
    api_key = _anthropic_key()
    assert api_key
    model = model or os.getenv("FPA_LLM_MODEL") or os.getenv("ANTHROPIC_MODEL") or "claude-haiku-4-5"
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    with httpx.Client(timeout=90.0) as client:
        resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    parts = data.get("content") or []
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    return text.strip()


def _complete_openai(
    system: str,
    user: str,
    *,
    model: str | None,
    temperature: float,
    max_tokens: int,
) -> str:
    api_key = _openai_key()
    assert api_key
    base = os.getenv("FPA_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = model or os.getenv("FPA_LLM_MODEL", "gpt-4o-mini")
    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{base}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _fallback(system: str, user: str) -> str:
    """Deterministic summary when no LLM key is configured."""
    try:
        payload = json.loads(user)
    except json.JSONDecodeError:
        return (
            "LLM key not configured (set ANTHROPIC_API_KEY). "
            "Deterministic fallback cannot parse non-JSON prompt.\n\n" + user[:2000]
        )

    prior = payload.get("prior_period")
    period = payload.get("period")
    rev_line = (
        f"**Revenue:** {payload.get('revenue_prior_value'):,.2f} → {payload.get('revenue_value'):,.2f}  |  "
        f"Δ={payload.get('revenue_delta'):,.2f} ({_pct(payload.get('revenue_pct'))} vs {prior})"
        + (f"  |  z={payload.get('revenue_z'):.2f} vs trailing history" if payload.get("revenue_z") is not None else "")
        if payload.get("revenue_value") is not None and payload.get("revenue_prior_value") is not None
        else (
            f"**North-star delta (revenue):** {payload.get('revenue_delta'):,.2f} "
            f"({_pct(payload.get('revenue_pct'))} vs {prior})"
            + (f"  |  z={payload.get('revenue_z'):.2f} vs trailing history" if payload.get("revenue_z") is not None else "")
        )
    )
    lines = [
        "## Causal FP&A summary (template fallback — set ANTHROPIC_API_KEY for Claude prose)",
        "",
        f"**Company:** {payload.get('company')}  |  **Compare:** {prior} → {period}",
        rev_line,
        "",
        "### 1) Dollar attribution clusters",
    ]
    dollar = payload.get("dollar_attribution_clusters") or [
        c for c in payload.get("clusters", []) if "kpi" not in (c.get("dimensions") or [])
    ]
    kpis = payload.get("operational_kpi_clusters") or [
        c for c in payload.get("clusters", []) if "kpi" in (c.get("dimensions") or [])
    ]
    for c in dollar:
        lines.append(
            f"- **{c.get('label')}** (Δ={c.get('total_delta'):,.2f}, "
            f"mean z={c.get('mean_z'):.2f} vs trailing history)"
        )
        for d in c.get("drivers", [])[:5]:
            z = d.get("z_score")
            z_s = f", z={z:.2f} vs trailing history" if isinstance(z, (int, float)) else ""
            share = d.get("share_of_parent_delta")
            share_s = f", share={share:.0%} of parent Δ" if isinstance(share, (int, float)) else ""
            lines.append(
                f"  - {d.get('label')}: Δ={d.get('delta'):,.2f}"
                f"{_pct_inline(d.get('pct_change'))} vs {prior}{share_s}{z_s}"
            )
        evidence = _interpret_cluster(c)
        if evidence:
            lines.append(f"  - Evidence note: {evidence}")
    lines.append("")
    lines.append("### 2) Operational KPI evidence")
    if not kpis:
        lines.append("- No material KPI moves flagged.")
    for c in kpis:
        lines.append(f"- **{c.get('label')}** (mean z={c.get('mean_z'):.2f} vs trailing history)")
        for d in c.get("drivers", [])[:5]:
            z = d.get("z_score")
            z_s = f", z={z:.2f} vs trailing history" if isinstance(z, (int, float)) else ""
            lines.append(
                f"  - {d.get('label')}: {_pct_inline(d.get('pct_change')).strip() or 'n/a'} vs prior{z_s}"
            )
    if payload.get("companion_metrics"):
        lines.append("")
        lines.append("### 3) Material SEC companion metrics")
        for s in payload["companion_metrics"][:6]:
            lines.append(
                f"- {s.get('metric')}: Δ={s.get('delta'):,.2f}{_pct_inline(s.get('pct_change'))} vs prior"
                + (f", z={s['z_score']:.2f} vs trailing history" if s.get("z_score") is not None else "")
            )
    lines.append("")
    lines.append("### Evidence discipline")
    lines.append(
        "- Dollar shares are arithmetic attribution. "
        "KPI moves (CPC/CTR/ARPU) are supporting operational evidence, not $ partitions."
    )
    lines.append(
        "- No evaluative adjectives without a number and an explicit baseline "
        f"({payload.get('prior_period')} or trailing history)."
    )
    return "\n".join(lines)


def _pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x:.1%}"


def _pct_inline(x: float | None) -> str:
    if x is None:
        return ""
    return f" ({x:.1%})"


def _interpret_cluster(c: dict) -> str:
    """Factual one-liner — numbers only, no evaluative adjectives."""
    dims = c.get("dimensions") or []
    total = c.get("total_delta")
    mean_z = c.get("mean_z")
    bits: list[str] = [f"dimension={','.join(dims) if dims else 'mixed'}"]
    if isinstance(total, (int, float)) and "kpi" not in dims:
        bits.append(f"cluster net Δ={total:,.2f}")
    if isinstance(mean_z, (int, float)):
        bits.append(f"mean z={mean_z:.2f} vs trailing history")
    return "; ".join(bits)

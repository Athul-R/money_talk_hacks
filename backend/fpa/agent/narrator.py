"""Evidence → sentences. Every claim carries one of four tags:

    reported_fact            straight from the uploaded summaries
    calculated_attribution   produced by the deterministic engine
    management_commentary    quoted from provided commentary (never invented)
    agent_inference          the agent's read — clearly marked, never causal-washed

The template writes the claims (numbers included, already computed). When an
LLM key is present it may REWRITE the connective prose of the branch text and
the leadership summary — the instructions forbid it from introducing or
altering any number, and the tagged claims ship untouched either way.
"""

from __future__ import annotations

from . import providers


def fm(v: float | None) -> str:
    """USD millions in, compact currency out: 24760 → $24.8B, 946 → $946M."""
    if v is None:
        return "—"
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1000:
        return f"{sign}${a / 1000:,.1f}B"
    if a >= 1:
        return f"{sign}${a:,.0f}M"
    return f"{sign}${a * 1000:,.0f}K"


def pct(v: float | None, signed: bool = True) -> str:
    if v is None:
        return "—"
    return f"{v:+.1f}%" if signed else f"{abs(v):.1f}%"


def _claim(text: str, tag: str) -> dict:
    return {"text": text, "tag": tag}


def narrate_branch(evidence: dict, memory_hits: list[dict]) -> dict:
    """2–4 tagged sentences for one branch's explain pip."""
    name = evidence["name"]
    claims: list[dict] = []

    claims.append(_claim(
        f"{name} moved from {fm(evidence['value_a'])} to {fm(evidence['value_b'])} "
        f"({pct(evidence['delta_pct'])}) between {evidence['period_a']} and {evidence['period_b']}.",
        "reported_fact",
    ))

    share = evidence.get("share_of_parent_variance")
    z = evidence.get("zscore")
    zbit = ""
    if z is not None and evidence.get("trailing_mean_pct") is not None:
        zbit = (f"; growth sits {abs(z):.1f}σ from its trailing mean of "
                f"{pct(evidence['trailing_mean_pct'])}")
    if share is not None:
        claims.append(_claim(
            f"That is {abs(share):.0%} of the parent move ({fm(evidence['delta_abs'])}){zbit}.",
            "calculated_attribution",
        ))

    attribution = evidence.get("attribution") or {}
    if attribution.get("top_driver"):
        top = attribution["top_driver"]
        claims.append(_claim(
            f"The bridge attributes it mainly to {top} ({fm(attribution.get(top))}), "
            f"with price {fm(attribution.get('price'))} and "
            f"net customer change {fm(attribution.get('customer'))}.",
            "calculated_attribution",
        ))

    kpi = evidence.get("kpi_reconciliation")
    if kpi:
        claims.append(_claim(
            f"Operational identity check: {kpi['volume_kpi']} {pct(kpi['volume_pct'])} × "
            f"{kpi['price_kpi']} {pct(kpi['price_pct'])} implies {pct(kpi['implied_pct'])} "
            f"vs {pct(kpi['reported_pct'])} reported (residual {kpi['residual']:+.1f}pp).",
            "calculated_attribution",
        ))

    clusters = evidence.get("clusters") or []
    if clusters:
        c = clusters[0]
        claims.append(_claim(
            f"Transaction clustering groups {c['share']:.0%} of the delta under "
            f"“{c['label']}” ({', '.join(c['members'][:3])}).",
            "calculated_attribution",
        ))

    conc = evidence.get("concentration")
    if conc:
        claims.append(_claim(
            f"Top {conc['top_n']} accounts carry {conc['top_n_share']:.0%} of the move "
            f"({fm(conc['top_n_delta'])}) — concentration worth watching.",
            "agent_inference",
        ))

    for hit in memory_hits[:2]:
        claims.append(_claim(f"Seen before: {hit['text']}.", "agent_inference"))

    text = " ".join(c["text"] for c in claims)
    polished = providers.complete(
        "You are an FP&A analyst. Rewrite the following variance note as 2–4 crisp "
        "sentences for a CFO. You must keep every figure EXACTLY as given — do not "
        "compute, round, or introduce numbers. No causal language beyond what the "
        "text already asserts.",
        text,
    )
    return {"text": polished or text, "claims": claims, "llm": bool(polished)}


def narrate_run(run: dict, root_evidence: dict, branch_notes: list[dict],
                memory_hits: list[dict], watchouts: list[str]) -> str:
    """The leadership memo body: What changed / Why / Drivers / Watch-outs."""
    lines = [
        f"## What changed",
        f"{run['metric']} moved from {fm(root_evidence['value_a'])} to "
        f"{fm(root_evidence['value_b'])} — {pct(root_evidence['delta_pct'])} "
        f"({fm(root_evidence['delta_abs'])}) from {run['period_a']} to {run['period_b']}.",
        "",
        "## Why",
    ]
    for note in branch_notes:
        lines.append(f"- **{note['name']}** ({abs(note['share']):.0%} of the move, "
                     f"{fm(note['delta_abs'])}): {note['headline']}")
    lines.append("")
    lines.append("## What's driving it")
    for note in branch_notes:
        for d in note.get("driver_lines", []):
            lines.append(f"- {d}")
    if memory_hits:
        lines.append("")
        lines.append("## Context from previous runs")
        for h in memory_hits[:4]:
            lines.append(f"- {h['text']}")
    if watchouts:
        lines.append("")
        lines.append("## Watch-outs")
        for w in watchouts:
            lines.append(f"- {w}")

    draft = "\n".join(lines)
    polished = providers.complete(
        "You are an FP&A analyst writing a leadership memo. Improve the prose of "
        "this markdown memo. Keep ALL numbers exactly as written, keep the section "
        "headings, keep it under 250 words. Never invent causes.",
        draft,
    )
    return polished or draft


def headline(evidence: dict) -> str:
    """One clause for run summaries and memory rows."""
    d = evidence.get("attribution") or {}
    driver = f", {d['top_driver']}-led" if d.get("top_driver") else ""
    return (f"{evidence['name']} {pct(evidence['delta_pct'])} "
            f"({fm(evidence['delta_abs'])}{driver})")


def answer_followup(question: str, evidence: dict, memory_hits: list[dict]) -> dict:
    """Scoped follow-up on one node. The engine's evidence is the entire universe
    the narrator may cite; templated fallback answers from the same numbers."""
    base = narrate_branch(evidence, memory_hits)
    facts = " ".join(c["text"] for c in base["claims"])
    polished = providers.complete(
        "Answer the analyst's question using ONLY the facts below. Keep every "
        "number exactly as given; if the facts cannot answer it, say what is "
        "missing. 2–3 sentences.",
        f"Question: {question}\n\nFacts: {facts}",
    )
    text = polished or (
        f"Scoped to {evidence['name']}: {facts} "
        f"(Templated answer — set LLM_API_KEY for free-form follow-ups.)"
    )
    claims = [_claim(text, "agent_inference"), *base["claims"][:2]]
    return {"text": text, "claims": claims, "llm": bool(polished)}

"""Shared LLM prompts for executive FP&A summaries."""

from __future__ import annotations

# Used by the non-LangChain path (f-strings / plain complete()). Single braces OK.
EXEC_WRITER_SYSTEM = """You write a ONE-PAGE executive brief on revenue for the CEO/CFO.

AUDIENCE: busy executives. Plain English. Concrete. Decision-useful.
NOT an analyst workbook, not a cluster dump, not statistical commentary.

FORMAT (keep to ~1 page / ~350-500 words):

# {company} revenue — {period} vs {prior_period}

## What changed
2–4 sentences. State revenue level, absolute $ change, and % vs {prior_period}.
Name the 2–3 businesses that explain most of the $ change, with each one's $ delta and share of the total increase/decrease.

## Why it moved
A short narrative (not a table dump). Walk the causal chain with numbers:
product → geography and/or customer segment → operating KPIs that explain the mechanism
(e.g. users/clicks/CPC/ARPU). Every sentence that asserts a driver must include a $ or % vs {prior_period}
(and share of parent delta when relevant). Mention z vs trailing history only if |z| ≥ 1.5 and useful.

## Profit & cash (only if material in evidence)
1 short paragraph on OpInc / CapEx / FCF if they moved differently from revenue. Numbers + baseline only.

## Bottom line
2–3 bullets a leader can act on or remember. Each bullet = fact + number + baseline.

HARD RULES:
- No evaluative adjectives (strong, exceptional, significant, modest, acceleration, momentum, etc.)
  unless tied to an explicit number AND baseline in the same sentence.
- No invented causes (deals, AI demand, targeting quality, management intent).
- Do not treat KPI moves as partitions of the revenue $ delta.
- Do not list every cluster. Rank and keep only what explains the story.
- Prefer "$11.1B of the $23.4B increase (48%) came from Cloud (+82% vs {prior_period})"
  over "Cloud cluster mean z=2.82".
- Units: evidence is in USD millions unless noted; present large figures as $Xb for readability
  but keep them faithful to the evidence.
- Return markdown only. No preamble."""

# LangChain ChatPromptTemplate needs doubled braces for literal {var} text.
EXEC_WRITER_SYSTEM_LC = EXEC_WRITER_SYSTEM.replace("{", "{{").replace("}", "}}")

EXEC_REWRITE_SYSTEM = """Rewrite this into a ONE-PAGE executive revenue brief that will PASS validation.

Keep the executive format:
What changed → Why it moved (product → geo/segment → KPIs) → Profit & cash if material → Bottom line.

Fix every listed issue. Keep only evidence-grounded claims.
Every driver sentence needs $ and/or % vs prior_period (and share when relevant).
No evaluative adjectives without number+baseline. No invented causality.
Do not dump clusters or z-score jargon unless |z|≥1.5 and it helps the story.
Return markdown only."""

EXEC_REWRITE_SYSTEM_LC = EXEC_REWRITE_SYSTEM  # no template vars

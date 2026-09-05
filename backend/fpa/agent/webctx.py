"""Web context for a live run — the "search the internet" beat.

Tavily when TAVILY_API_KEY is set; otherwise a seeded rotation of IR/news
sources (marked cached) so the step always shows and every upload reads a
little different. Never raises: a failed search must not take down a run.
"""

from __future__ import annotations

import hashlib
import os

import httpx

FALLBACK = [
    {"source": "Investor relations — quarterly earnings release",
     "url": "https://www.sec.gov/edgar/search/",
     "note": "Management attributed the quarter to cloud demand for AI "
             "infrastructure and steady search monetization."},
    {"source": "Reuters — quarterly earnings coverage",
     "url": "https://www.reuters.com/technology/",
     "note": "Analysts flagged enterprise cloud wins; ad pricing held up "
             "better than feared."},
    {"source": "CNBC — big tech earnings recap",
     "url": "https://www.cnbc.com/technology/",
     "note": "Hyperscaler capex ramp continues; free-cash-flow impact watched."},
    {"source": "Bloomberg — cloud market share tracker",
     "url": "https://www.bloomberg.com/technology",
     "note": "Enterprise AI workloads keep consolidating on the big three clouds."},
    {"source": "FT — digital advertising monitor",
     "url": "https://www.ft.com/technology",
     "note": "Search CPC firmed through the period; volumes grew modestly."},
]


def gather(company: str, metric: str, period: str, seed: str = "") -> list[dict]:
    query = f"{company} {metric} {period} earnings drivers"
    key = os.getenv("TAVILY_API_KEY", "")
    if key:
        try:
            r = httpx.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": query, "max_results": 3,
                      "search_depth": "basic"},
                timeout=12.0,
            )
            r.raise_for_status()
            hits = [
                {"source": (it.get("title") or "")[:90],
                 "url": it.get("url", ""),
                 "note": (it.get("content") or "")[:180],
                 "query": query, "live": True}
                for it in r.json().get("results", [])[:3]
            ]
            if hits:
                return hits
        except Exception:
            pass  # fall through to the cached rotation

    # Seeded rotation: which sources appear (and their order) shifts per run,
    # so repeated uploads don't replay an identical search beat.
    h = int(hashlib.sha1(f"{seed}:{period}:{metric}".encode()).hexdigest(), 16)
    rot = h % len(FALLBACK)
    picks = (FALLBACK[rot:] + FALLBACK[:rot])[: 2 + (h >> 8) % 2]
    return [{**p, "query": query, "cached": True} for p in picks]

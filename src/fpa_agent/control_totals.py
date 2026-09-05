"""Alphabet financial control totals and operational KPIs from public filings.

Sources:
- Alphabet Q2 2026 earnings release (Ex-99.1), July 22, 2026
- Alphabet Form 10-Q operational KPIs (paid clicks / CPC / Network impressions)
- SEC CompanyFacts (entity-level GAAP series)

Amounts are in USD millions unless noted otherwise.
These are the hard constraints that synthetic ledgers must reconcile to.
"""

from __future__ import annotations

from typing import Any

# Period keys used throughout the system
PERIODS = ("2025-Q2", "2026-Q2")

ALPHABET_SEGMENTS: dict[str, dict[str, float]] = {
    "search_other": {"2025-Q2": 54190.0, "2026-Q2": 63271.0},
    "youtube_ads": {"2025-Q2": 9796.0, "2026-Q2": 11055.0},
    "network": {"2025-Q2": 7354.0, "2026-Q2": 7303.0},
    "subscriptions_platforms_devices": {"2025-Q2": 11203.0, "2026-Q2": 12911.0},
    "google_cloud": {"2025-Q2": 13624.0, "2026-Q2": 24768.0},
    "other_bets": {"2025-Q2": 373.0, "2026-Q2": 382.0},
    "hedging": {"2025-Q2": -112.0, "2026-Q2": 106.0},
}

ALPHABET_ROLLUPS: dict[str, dict[str, float]] = {
    "google_advertising": {"2025-Q2": 71340.0, "2026-Q2": 81629.0},
    "google_services": {"2025-Q2": 82543.0, "2026-Q2": 94540.0},
    "total_revenue": {"2025-Q2": 96428.0, "2026-Q2": 119796.0},
    "tac": {"2025-Q2": 14705.0, "2026-Q2": 16179.0},
    "operating_income": {"2025-Q2": 31271.0, "2026-Q2": 40770.0},
    "google_services_opinc": {"2025-Q2": 33063.0, "2026-Q2": 39544.0},
    "google_cloud_opinc": {"2025-Q2": 2826.0, "2026-Q2": 8814.0},
    "other_bets_opinc": {"2025-Q2": -1246.0, "2026-Q2": -1799.0},
    "alphabet_level_opinc": {"2025-Q2": -3372.0, "2026-Q2": -5789.0},
    "cost_of_revenue": {"2025-Q2": 39039.0, "2026-Q2": 45943.0},
    "rd_expense": {"2025-Q2": 13808.0, "2026-Q2": 18219.0},
    "sm_expense": {"2025-Q2": 7101.0, "2026-Q2": 8403.0},
    "ga_expense": {"2025-Q2": 5209.0, "2026-Q2": 6461.0},
    "net_income": {"2025-Q2": 28196.0, "2026-Q2": 112107.0},  # earnings release common NI
    "operating_cash_flow": {"2025-Q2": 27747.0, "2026-Q2": 39069.0},
    "capex": {"2025-Q2": 22446.0, "2026-Q2": 44924.0},
    "free_cash_flow": {"2025-Q2": 5301.0, "2026-Q2": -5855.0},  # OCF - CapEx
    "employees": {"2025-Q2": 187103.0, "2026-Q2": 198933.0},
}

# YoY operational drivers disclosed for advertising monetization
OPERATIONAL_KPIS: dict[str, dict[str, float]] = {
    "search_paid_clicks_yoy": {"2026-Q2": 0.13},
    "search_cpc_yoy": {"2026-Q2": 0.03},
    "network_impressions_yoy": {"2026-Q2": -0.12},
    "network_cpi_yoy": {"2026-Q2": 0.13},
}

# Management-attributed causal language from the earnings release (not arithmetic).
MANAGEMENT_CAUSALITY: dict[str, str] = {
    "google_cloud": (
        "Management attributes Cloud acceleration primarily to GCP demand across "
        "enterprise AI solutions, enterprise AI infrastructure, and core GCP services."
    ),
    "search_other": (
        "Management links Search growth to AI feature adoption (including Gemini-powered "
        "experiences) and higher query volume on owned properties."
    ),
    "capex": (
        "CapEx growth primarily reflects technology infrastructure investment to scale "
        "AI/compute capacity, with management raising FY26 CapEx guidance accordingly."
    ),
    "tac_mix": (
        "TAC intensity improved largely because advertising mix shifted toward Search "
        "(lower TAC rate) and away from Network (higher TAC rate)."
    ),
    "net_income": (
        "Net income was heavily influenced by a large unrealized gain on equity securities "
        "in Other income (expense); treat NI as distorted vs operating performance."
    ),
}

SEGMENT_LABELS: dict[str, str] = {
    "search_other": "Google Search & other",
    "youtube_ads": "YouTube ads",
    "network": "Google Network",
    "subscriptions_platforms_devices": "Subscriptions, platforms & devices",
    "google_cloud": "Google Cloud",
    "other_bets": "Other Bets",
    "hedging": "Hedging gains/(losses)",
    "google_advertising": "Google advertising",
    "google_services": "Google Services",
    "total_revenue": "Total revenue",
    "tac": "Traffic acquisition costs (TAC)",
    "operating_income": "Operating income",
    "cost_of_revenue": "Cost of revenues",
    "rd_expense": "R&D expense",
    "sm_expense": "Sales & marketing",
    "ga_expense": "G&A expense",
    "operating_cash_flow": "Operating cash flow",
    "capex": "Capital expenditures",
    "free_cash_flow": "Free cash flow",
    "employees": "Employees",
    "net_income": "Net income",
}


def metric_value(metric: str, period: str) -> float:
    if metric in ALPHABET_SEGMENTS:
        return ALPHABET_SEGMENTS[metric][period]
    if metric in ALPHABET_ROLLUPS:
        return ALPHABET_ROLLUPS[metric][period]
    raise KeyError(f"Unknown metric: {metric}")


def all_control_metrics() -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    out.update(ALPHABET_SEGMENTS)
    out.update(ALPHABET_ROLLUPS)
    return out


def as_control_table() -> list[dict[str, Any]]:
    rows = []
    for metric, series in all_control_metrics().items():
        a, b = series["2025-Q2"], series["2026-Q2"]
        delta = b - a
        pct = (delta / a) if a not in (0, 0.0) else None
        rows.append(
            {
                "metric": metric,
                "label": SEGMENT_LABELS.get(metric, metric),
                "period_a": "2025-Q2",
                "period_b": "2026-Q2",
                "value_a": a,
                "value_b": b,
                "delta": delta,
                "pct": pct,
                "source": "alphabet_earnings_q2_2026",
            }
        )
    return rows

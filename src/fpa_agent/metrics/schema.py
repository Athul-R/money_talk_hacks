"""Expected input schemas for the causal FP&A agent.

Data is assumed given. These schemas document the contracts the pipeline reads.
All monetary fields are in the same unit (e.g. USD millions) unless noted.
"""

from __future__ import annotations

from typing import TypedDict

# ---------------------------------------------------------------------------
# Layer 1 — SEC / entity financials (one row per company × period)
# ---------------------------------------------------------------------------
SEC_COLUMNS = [
    "company",
    "period",  # e.g. 2025-Q1
    "period_end",
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "rd_expense",
    "sm_expense",
    "ga_expense",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "capex",
    "free_cash_flow",
    "employees",
]

# ---------------------------------------------------------------------------
# Layer 2 — Product segment P&L (company × period × product)
# ---------------------------------------------------------------------------
PRODUCT_COLUMNS = [
    "company",
    "period",
    "product",  # Search, YouTube_Ads, Network, Cloud, Subscriptions, Devices, Other
    "parent_product",  # optional rollup, e.g. Advertising → Search
    "revenue",
    "direct_cost",  # e.g. TAC for ads, COGS for devices
    "operating_income",
]

# ---------------------------------------------------------------------------
# Layer 3 — Geography (company × period × product × geo)
# ---------------------------------------------------------------------------
GEO_COLUMNS = [
    "company",
    "period",
    "product",
    "parent_product",
    "geography",  # US, EU, APAC, LATAM, ROW
    "revenue",
    "users",
    "arpu",
]

# ---------------------------------------------------------------------------
# Layer 4 — User segmentation (company × period × product × geo × user_type)
# ---------------------------------------------------------------------------
USER_COLUMNS = [
    "company",
    "period",
    "product",
    "parent_product",
    "geography",
    "user_class",  # advertiser | consumer | customer
    "user_segment",  # e.g. enterprise_advertiser, smb_advertiser, paying_consumer, streaming_consumer
    "revenue",
    "users",
    "arpu",
    # Advertiser / ads KPIs (null for pure consumer rows)
    "impressions",
    "clicks",
    "ctr",
    "cpc",
    "cpm",
    "rpm",
    "revenue_per_click",
    "revenue_per_impression",
]

TABLES = {
    "sec_metrics": SEC_COLUMNS,
    "product_segments": PRODUCT_COLUMNS,
    "geography": GEO_COLUMNS,
    "user_segments": USER_COLUMNS,
}


class PeriodKey(TypedDict):
    company: str
    period: str

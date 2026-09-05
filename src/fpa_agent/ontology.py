"""Financial metric ontology / dependency graph for driver-based FP&A."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DecompositionKind = Literal[
    "sum",
    "difference",
    "ratio",
    "price_volume",
    "segment",
    "ledger",
]


@dataclass(frozen=True)
class MetricNode:
    id: str
    label: str
    kind: DecompositionKind
    children: tuple[str, ...] = ()
    formula: str | None = None
    ledger: str | None = None  # synthetic fact table for drilldown
    unit: str = "usd_millions"
    notes: str = ""


# Core graph: outcome → financial drivers → operational drivers → ledger
ONTOLOGY: dict[str, MetricNode] = {
    "total_revenue": MetricNode(
        id="total_revenue",
        label="Total revenue",
        kind="sum",
        children=(
            "search_other",
            "youtube_ads",
            "network",
            "subscriptions_platforms_devices",
            "google_cloud",
            "other_bets",
            "hedging",
        ),
        formula="sum(business_line_revenues)",
    ),
    "google_advertising": MetricNode(
        id="google_advertising",
        label="Google advertising",
        kind="sum",
        children=("search_other", "youtube_ads", "network"),
    ),
    "search_other": MetricNode(
        id="search_other",
        label="Google Search & other",
        kind="price_volume",
        children=("search_paid_clicks", "search_cpc"),
        ledger="ad_transactions",
        formula="paid_clicks × CPC",
        notes="Disclosed YoY: clicks +13%, CPC +3%.",
    ),
    "youtube_ads": MetricNode(
        id="youtube_ads",
        label="YouTube ads",
        kind="ledger",
        ledger="ad_transactions",
    ),
    "network": MetricNode(
        id="network",
        label="Google Network",
        kind="price_volume",
        children=("network_impressions", "network_cpi"),
        ledger="ad_transactions",
        formula="impressions × cost_per_impression",
        notes="Disclosed YoY: impressions −12%, CPI +13%.",
    ),
    "subscriptions_platforms_devices": MetricNode(
        id="subscriptions_platforms_devices",
        label="Subscriptions, platforms & devices",
        kind="ledger",
        ledger="subscriptions",
    ),
    "google_cloud": MetricNode(
        id="google_cloud",
        label="Google Cloud",
        kind="ledger",
        ledger="cloud_usage",
        notes="Largest incremental revenue driver in Q2'26.",
    ),
    "other_bets": MetricNode(
        id="other_bets",
        label="Other Bets",
        kind="segment",
    ),
    "hedging": MetricNode(
        id="hedging",
        label="Hedging gains/(losses)",
        kind="segment",
    ),
    "gross_profit": MetricNode(
        id="gross_profit",
        label="Gross profit",
        kind="difference",
        children=("total_revenue", "cost_of_revenue"),
        formula="revenue − cost_of_revenue",
    ),
    "cost_of_revenue": MetricNode(
        id="cost_of_revenue",
        label="Cost of revenues",
        kind="sum",
        children=("tac", "other_cogs"),
        ledger="opex",
    ),
    "tac": MetricNode(
        id="tac",
        label="Traffic acquisition costs",
        kind="ratio",
        children=("google_advertising",),
        formula="TAC / advertising_revenue",
        ledger="ad_transactions",
    ),
    "other_cogs": MetricNode(
        id="other_cogs",
        label="Other cost of revenues",
        kind="difference",
        children=("cost_of_revenue", "tac"),
        formula="cost_of_revenue − TAC",
    ),
    "operating_income": MetricNode(
        id="operating_income",
        label="Operating income",
        kind="difference",
        children=("gross_profit", "rd_expense", "sm_expense", "ga_expense"),
        formula="gross_profit − R&D − S&M − G&A",
    ),
    "rd_expense": MetricNode(
        id="rd_expense",
        label="R&D expense",
        kind="ledger",
        ledger="opex",
    ),
    "sm_expense": MetricNode(
        id="sm_expense",
        label="Sales & marketing",
        kind="ledger",
        ledger="opex",
    ),
    "ga_expense": MetricNode(
        id="ga_expense",
        label="G&A expense",
        kind="ledger",
        ledger="opex",
    ),
    "free_cash_flow": MetricNode(
        id="free_cash_flow",
        label="Free cash flow",
        kind="difference",
        children=("operating_cash_flow", "capex"),
        formula="operating_cash_flow − capex",
    ),
    "operating_cash_flow": MetricNode(
        id="operating_cash_flow",
        label="Operating cash flow",
        kind="segment",
    ),
    "capex": MetricNode(
        id="capex",
        label="Capital expenditures",
        kind="ledger",
        ledger="capex",
    ),
}


@dataclass
class DrillPath:
    """Ordered path an analyst / agent can walk."""

    steps: list[str] = field(default_factory=list)

    def push(self, metric_id: str) -> DrillPath:
        return DrillPath(steps=[*self.steps, metric_id])


def children_of(metric_id: str) -> tuple[str, ...]:
    node = ONTOLOGY.get(metric_id)
    return node.children if node else ()


def ledger_for(metric_id: str) -> str | None:
    node = ONTOLOGY.get(metric_id)
    return node.ledger if node else None

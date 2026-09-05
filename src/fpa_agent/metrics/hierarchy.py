"""Top-down metric hierarchy: Revenue → product → (geo | user | KPI) drills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Dimension = Literal["sec", "product", "geography", "user", "kpi"]


@dataclass(frozen=True)
class HierarchyNode:
    id: str
    label: str
    dimension: Dimension
    children: tuple[str, ...] = ()
    # Alternative non-additive drills (geo / user / KPI) — not summed into parent
    drills: tuple[str, ...] = ()
    table: str | None = None
    group_col: str | None = None
    filter: dict[str, str] | None = None
    value_col: str = "revenue"


# Additive tree for $ attribution. Dimensional drills are alternative views.
HIERARCHY: dict[str, HierarchyNode] = {
    "revenue": HierarchyNode(
        id="revenue",
        label="Total revenue",
        dimension="sec",
        children=("advertising", "cloud", "subscriptions_devices", "other"),
        table="sec_metrics",
        value_col="revenue",
    ),
    "advertising": HierarchyNode(
        id="advertising",
        label="Advertising revenue",
        dimension="product",
        children=("search", "youtube_ads", "network"),
        table="product_segments",
        filter={"parent_product": "Advertising"},
    ),
    "search": HierarchyNode(
        id="search",
        label="Search",
        dimension="product",
        drills=("search_by_geo", "search_by_user", "search_ad_kpis"),
        table="product_segments",
        filter={"product": "Search"},
    ),
    "youtube_ads": HierarchyNode(
        id="youtube_ads",
        label="YouTube ads",
        dimension="product",
        drills=("youtube_by_geo", "youtube_by_user", "youtube_ad_kpis"),
        table="product_segments",
        filter={"product": "YouTube_Ads"},
    ),
    "network": HierarchyNode(
        id="network",
        label="Network",
        dimension="product",
        drills=("network_by_geo", "network_by_user"),
        table="product_segments",
        filter={"product": "Network"},
    ),
    "cloud": HierarchyNode(
        id="cloud",
        label="Cloud",
        dimension="product",
        drills=("cloud_by_geo", "cloud_by_user"),
        table="product_segments",
        filter={"product": "Cloud"},
    ),
    "subscriptions_devices": HierarchyNode(
        id="subscriptions_devices",
        label="Subscriptions & devices",
        dimension="product",
        children=("subscriptions", "devices"),
        drills=("subs_by_geo", "subs_by_user"),
        table="product_segments",
        filter={"parent_product": "Subscriptions_Devices"},
    ),
    "subscriptions": HierarchyNode(
        id="subscriptions",
        label="Subscriptions",
        dimension="product",
        drills=("subs_by_user",),
        table="product_segments",
        filter={"product": "Subscriptions"},
    ),
    "devices": HierarchyNode(
        id="devices",
        label="Devices",
        dimension="product",
        table="product_segments",
        filter={"product": "Devices"},
    ),
    "other": HierarchyNode(
        id="other",
        label="Other / hedges",
        dimension="product",
        table="product_segments",
        filter={"parent_product": "Other"},
    ),
    "search_by_geo": HierarchyNode(
        id="search_by_geo",
        label="Search by geography",
        dimension="geography",
        table="geography",
        group_col="geography",
        filter={"product": "Search"},
    ),
    "youtube_by_geo": HierarchyNode(
        id="youtube_by_geo",
        label="YouTube ads by geography",
        dimension="geography",
        table="geography",
        group_col="geography",
        filter={"product": "YouTube_Ads"},
    ),
    "network_by_geo": HierarchyNode(
        id="network_by_geo",
        label="Network by geography",
        dimension="geography",
        table="geography",
        group_col="geography",
        filter={"product": "Network"},
    ),
    "cloud_by_geo": HierarchyNode(
        id="cloud_by_geo",
        label="Cloud by geography",
        dimension="geography",
        table="geography",
        group_col="geography",
        filter={"product": "Cloud"},
    ),
    "subs_by_geo": HierarchyNode(
        id="subs_by_geo",
        label="Subscriptions & devices by geography",
        dimension="geography",
        table="geography",
        group_col="geography",
        filter={"parent_product": "Subscriptions_Devices"},
    ),
    "search_by_user": HierarchyNode(
        id="search_by_user",
        label="Search by user segment",
        dimension="user",
        table="user_segments",
        group_col="user_segment",
        filter={"product": "Search", "user_class": "advertiser"},
    ),
    "youtube_by_user": HierarchyNode(
        id="youtube_by_user",
        label="YouTube by user segment",
        dimension="user",
        table="user_segments",
        group_col="user_segment",
        filter={"product": "YouTube_Ads"},
    ),
    "network_by_user": HierarchyNode(
        id="network_by_user",
        label="Network by user segment",
        dimension="user",
        table="user_segments",
        group_col="user_segment",
        filter={"product": "Network", "user_class": "advertiser"},
    ),
    "cloud_by_user": HierarchyNode(
        id="cloud_by_user",
        label="Cloud by user segment",
        dimension="user",
        table="user_segments",
        group_col="user_segment",
        filter={"product": "Cloud"},
    ),
    "subs_by_user": HierarchyNode(
        id="subs_by_user",
        label="Subscriptions by user segment",
        dimension="user",
        table="user_segments",
        group_col="user_segment",
        filter={"parent_product": "Subscriptions_Devices", "user_class": "consumer"},
    ),
    "search_ad_kpis": HierarchyNode(
        id="search_ad_kpis",
        label="Search advertiser KPIs",
        dimension="kpi",
        table="user_segments",
        filter={"product": "Search", "user_class": "advertiser"},
    ),
    "youtube_ad_kpis": HierarchyNode(
        id="youtube_ad_kpis",
        label="YouTube advertiser KPIs",
        dimension="kpi",
        table="user_segments",
        filter={"product": "YouTube_Ads", "user_class": "advertiser"},
    ),
}

AD_KPI_COLUMNS = (
    "ctr",
    "cpc",
    "cpm",
    "rpm",
    "arpu",
    "revenue_per_click",
    "revenue_per_impression",
    "impressions",
    "clicks",
    "users",
)

SEC_COMPANION_METRICS = (
    "cost_of_revenue",
    "gross_profit",
    "rd_expense",
    "sm_expense",
    "ga_expense",
    "operating_income",
    "operating_cash_flow",
    "capex",
    "free_cash_flow",
    "employees",
)


def children(node_id: str) -> tuple[str, ...]:
    node = HIERARCHY.get(node_id)
    return node.children if node else ()

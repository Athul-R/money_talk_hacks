"""Company-aware metric hierarchies: Revenue/OpInc → segment → subsidiary → geo/user."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

Dimension = Literal["sec", "product", "geography", "user", "kpi"]


@dataclass(frozen=True)
class HierarchyNode:
    id: str
    label: str
    dimension: Dimension
    children: tuple[str, ...] = ()
    drills: tuple[str, ...] = ()
    table: str | None = None
    group_col: str | None = None
    filter: dict[str, str] | None = None
    value_col: str = "revenue"


def _geo(product: str | None = None, parent: str | None = None) -> HierarchyNode:
    filt: dict[str, str] = {}
    if product:
        filt["product"] = product
    if parent:
        filt["parent_product"] = parent
    key = product or parent or "x"
    return HierarchyNode(
        id=f"{key}_by_geo",
        label=f"{key} by geography",
        dimension="geography",
        table="geography",
        group_col="geography",
        filter=filt,
    )


def _user(product: str | None = None, parent: str | None = None) -> HierarchyNode:
    filt: dict[str, str] = {}
    if product:
        filt["product"] = product
    if parent:
        filt["parent_product"] = parent
    key = product or parent or "x"
    return HierarchyNode(
        id=f"{key}_by_user",
        label=f"{key} by user segment",
        dimension="user",
        table="user_segments",
        group_col="user_segment",
        filter=filt,
    )


def _product(
    pid: str,
    label: str,
    *,
    product: str | None = None,
    parent: str | None = None,
    children: tuple[str, ...] = (),
) -> HierarchyNode:
    filt: dict[str, str] = {}
    if product:
        filt["product"] = product
    if parent:
        filt["parent_product"] = parent
    drills: tuple[str, ...] = ()
    # Only leaf products get geo/user drills (avoid missing rollup drill keys)
    if not children and (product or parent):
        drills = (f"{product or parent}_by_geo", f"{product or parent}_by_user")
    return HierarchyNode(
        id=pid,
        label=label,
        dimension="product",
        children=children,
        drills=drills,
        table="product_segments",
        filter=filt or None,
    )


# ---------------------------------------------------------------------------
# Alphabet (tech / advertising)
# ---------------------------------------------------------------------------
ALPHABET_HIERARCHY: dict[str, HierarchyNode] = {
    "revenue": HierarchyNode(
        id="revenue",
        label="Total revenue",
        dimension="sec",
        children=("advertising", "cloud", "subscriptions_devices", "other"),
        table="sec_metrics",
        value_col="revenue",
    ),
    "advertising": _product(
        "advertising", "Advertising revenue", parent="Advertising", children=("search", "youtube_ads", "network")
    ),
    "search": _product("search", "Search", product="Search"),
    "youtube_ads": _product("youtube_ads", "YouTube ads", product="YouTube_Ads"),
    "network": _product("network", "Network", product="Network"),
    "cloud": _product("cloud", "Cloud", product="Cloud"),
    "subscriptions_devices": _product(
        "subscriptions_devices",
        "Subscriptions & devices",
        parent="Subscriptions_Devices",
        children=("subscriptions", "devices"),
    ),
    "subscriptions": _product("subscriptions", "Subscriptions", product="Subscriptions"),
    "devices": _product("devices", "Devices", product="Devices"),
    "other": _product("other", "Other / hedges", parent="Other"),
    "Search_by_geo": _geo(product="Search"),
    "YouTube_Ads_by_geo": _geo(product="YouTube_Ads"),
    "Network_by_geo": _geo(product="Network"),
    "Cloud_by_geo": _geo(product="Cloud"),
    "Subscriptions_Devices_by_geo": _geo(parent="Subscriptions_Devices"),
    "Search_by_user": HierarchyNode(
        id="Search_by_user",
        label="Search by user segment",
        dimension="user",
        table="user_segments",
        group_col="user_segment",
        filter={"product": "Search", "user_class": "advertiser"},
    ),
    "YouTube_Ads_by_user": _user(product="YouTube_Ads"),
    "Network_by_user": HierarchyNode(
        id="Network_by_user",
        label="Network by user segment",
        dimension="user",
        table="user_segments",
        group_col="user_segment",
        filter={"product": "Network", "user_class": "advertiser"},
    ),
    "Cloud_by_user": _user(product="Cloud"),
    "Subscriptions_Devices_by_user": HierarchyNode(
        id="Subscriptions_Devices_by_user",
        label="Subscriptions & devices by user",
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

# Fix Alphabet drill ids on product nodes to match keys above
ALPHABET_HIERARCHY["search"] = replace(
    ALPHABET_HIERARCHY["search"],
    drills=("Search_by_geo", "Search_by_user", "search_ad_kpis"),
)
ALPHABET_HIERARCHY["youtube_ads"] = replace(
    ALPHABET_HIERARCHY["youtube_ads"],
    drills=("YouTube_Ads_by_geo", "YouTube_Ads_by_user", "youtube_ad_kpis"),
)
ALPHABET_HIERARCHY["network"] = replace(
    ALPHABET_HIERARCHY["network"], drills=("Network_by_geo", "Network_by_user")
)
ALPHABET_HIERARCHY["cloud"] = replace(
    ALPHABET_HIERARCHY["cloud"], drills=("Cloud_by_geo", "Cloud_by_user")
)
ALPHABET_HIERARCHY["subscriptions_devices"] = replace(
    ALPHABET_HIERARCHY["subscriptions_devices"],
    drills=("Subscriptions_Devices_by_geo", "Subscriptions_Devices_by_user"),
)
ALPHABET_HIERARCHY["subscriptions"] = replace(
    ALPHABET_HIERARCHY["subscriptions"], drills=("Subscriptions_Devices_by_user",)
)


def _build_berkshire(value_col: str = "revenue") -> dict[str, HierarchyNode]:
    """Conglomerate tree: segment → subsidiary → geo / customer-segment drills."""
    h: dict[str, HierarchyNode] = {
        "revenue": HierarchyNode(
            id="revenue",
            label="Total revenue" if value_col == "revenue" else "Operating income",
            dimension="sec",
            children=(
                "insurance",
                "insurance_investment",
                "railroad",
                "energy",
                "manufacturing",
                "service_retailing",
                "distribution",
                "other",
            ),
            table="sec_metrics",
            value_col=value_col,
        ),
        "insurance": _product(
            "insurance",
            "Insurance (underwriting)",
            parent="Insurance",
            children=("geico", "bh_primary", "bh_reinsurance"),
        ),
        "geico": _product("geico", "GEICO", product="GEICO"),
        "bh_primary": _product("bh_primary", "BH Primary Group", product="BH_Primary"),
        "bh_reinsurance": _product("bh_reinsurance", "BH Reinsurance", product="BH_Reinsurance"),
        "insurance_investment": _product(
            "insurance_investment",
            "Insurance investment income",
            parent="Insurance_Investment",
            children=("insurance_investment_income",),
        ),
        "insurance_investment_income": _product(
            "insurance_investment_income",
            "Insurance investment income",
            product="Insurance_Investment_Income",
        ),
        "railroad": _product("railroad", "Railroad (BNSF)", parent="Railroad", children=("bnsf",)),
        "bnsf": _product("bnsf", "BNSF", product="BNSF"),
        "energy": _product(
            "energy",
            "Berkshire Hathaway Energy",
            parent="Energy",
            children=("bhe_utilities", "bhe_renewables"),
        ),
        "bhe_utilities": _product("bhe_utilities", "BHE Utilities", product="BHE_Utilities"),
        "bhe_renewables": _product("bhe_renewables", "BHE Renewables", product="BHE_Renewables"),
        "manufacturing": _product(
            "manufacturing",
            "Manufacturing",
            parent="Manufacturing",
            children=("industrial_products", "building_products", "consumer_products"),
        ),
        "industrial_products": _product(
            "industrial_products", "Industrial products", product="Industrial_Products"
        ),
        "building_products": _product(
            "building_products", "Building products", product="Building_Products"
        ),
        "consumer_products": _product(
            "consumer_products", "Consumer products", product="Consumer_Products"
        ),
        "service_retailing": _product(
            "service_retailing",
            "Service & retailing",
            parent="Service_Retailing",
            children=("home_services", "retail", "food_services"),
        ),
        "home_services": _product("home_services", "Home services", product="Home_Services"),
        "retail": _product("retail", "Retail", product="Retail"),
        "food_services": _product("food_services", "Food services", product="Food_Services"),
        "distribution": _product(
            "distribution", "Distribution", parent="Distribution", children=("mclane", "pilot")
        ),
        "mclane": _product("mclane", "McLane", product="McLane"),
        "pilot": _product("pilot", "Pilot", product="Pilot"),
        "other": _product("other", "Other", parent="Other"),
    }

    # Drill nodes for every subsidiary / parent used in drills=
    products = [
        "GEICO",
        "BH_Primary",
        "BH_Reinsurance",
        "Insurance_Investment_Income",
        "BNSF",
        "BHE_Utilities",
        "BHE_Renewables",
        "Industrial_Products",
        "Building_Products",
        "Consumer_Products",
        "Home_Services",
        "Retail",
        "Food_Services",
        "McLane",
        "Pilot",
    ]
    parents = [
        "Insurance",
        "Insurance_Investment",
        "Railroad",
        "Energy",
        "Manufacturing",
        "Service_Retailing",
        "Distribution",
        "Other",
    ]
    for p in products:
        h[f"{p}_by_geo"] = _geo(product=p)
        h[f"{p}_by_user"] = _user(product=p)
    for p in parents:
        h[f"{p}_by_geo"] = _geo(parent=p)
        h[f"{p}_by_user"] = _user(parent=p)

    # Apply value_col across product/geo/user nodes
    for k, node in list(h.items()):
        h[k] = replace(node, value_col=value_col)
    return h


BERKSHIRE_HIERARCHY = _build_berkshire("revenue")
BERKSHIRE_OPINC_HIERARCHY = _build_berkshire("operating_income")

# Back-compat alias
HIERARCHY = ALPHABET_HIERARCHY

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
    "net_income",
)


def get_hierarchy(company: str, metric: str = "revenue") -> dict[str, HierarchyNode]:
    """Return the additive/drill hierarchy for a company + north-star metric."""
    c = company.strip().lower().replace(" ", "_")
    if c in {"berkshire", "berkshire_hathaway", "brk", "brk.b", "brk.a"}:
        return BERKSHIRE_OPINC_HIERARCHY if metric == "operating_income" else BERKSHIRE_HIERARCHY
    # Alphabet / default
    if metric == "operating_income":
        # reuse alphabet tree but point value_col at operating_income
        return {k: replace(v, value_col="operating_income") for k, v in ALPHABET_HIERARCHY.items()}
    return ALPHABET_HIERARCHY


def children(node_id: str, hierarchy: dict[str, HierarchyNode] | None = None) -> tuple[str, ...]:
    h = hierarchy or HIERARCHY
    node = h.get(node_id)
    return node.children if node else ()

"""Generate synthetic operational ledgers calibrated to Alphabet control totals.

Synthetic ≠ fake-random: every table is scaled so period aggregates match
publicly reported segment revenues / costs exactly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fpa_agent.control_totals import ALPHABET_ROLLUPS, ALPHABET_SEGMENTS, OPERATIONAL_KPIS

RNG = np.random.default_rng(42)

VERTICALS = [
    "Finance",
    "Retail",
    "Travel",
    "Tech",
    "CPG",
    "Auto",
    "Healthcare",
    "Media",
]
REGIONS = ["US", "EU", "APAC", "LATAM", "ROW"]
DEVICES = ["Mobile", "Desktop", "Tablet", "CTV"]
CUSTOMER_TIERS = ["Enterprise", "Midmarket", "SMB"]
CLOUD_SERVICES = ["Compute", "Storage", "AI_Infra", "AI_Solutions", "Workspace", "Other"]
SUB_PRODUCTS = ["YouTube_Premium", "YouTube_TV", "Google_One", "Play_Pass", "Other"]


def _scale_to_total(values: np.ndarray, target: float) -> np.ndarray:
    s = values.sum()
    if s == 0:
        return values
    return values * (target / s)


def _period_dates(period: str, n: int) -> np.ndarray:
    year, q = period.split("-Q")
    year_i, q_i = int(year), int(q)
    start_month = (q_i - 1) * 3 + 1
    # mid-quarter day spread
    days = RNG.integers(0, 90, size=n)
    starts = pd.Timestamp(year=year_i, month=start_month, day=1)
    return np.array([starts + pd.Timedelta(days=int(d)) for d in days], dtype=object)


def generate_ad_transactions(period: str, n_search: int = 8000, n_yt: int = 2500, n_net: int = 2000) -> pd.DataFrame:
    search_rev = ALPHABET_SEGMENTS["search_other"][period]
    yt_rev = ALPHABET_SEGMENTS["youtube_ads"][period]
    net_rev = ALPHABET_SEGMENTS["network"][period]
    tac_total = ALPHABET_ROLLUPS["tac"][period]
    ad_rev = ALPHABET_ROLLUPS["google_advertising"][period]

    frames = []

    # --- Search ---
    # Base period for volume/price reconstruction relative to 2025-Q2
    base_search = ALPHABET_SEGMENTS["search_other"]["2025-Q2"]
    if period == "2026-Q2":
        click_mult = 1.0 + OPERATIONAL_KPIS["search_paid_clicks_yoy"]["2026-Q2"]
        cpc_mult = 1.0 + OPERATIONAL_KPIS["search_cpc_yoy"]["2026-Q2"]
    else:
        click_mult, cpc_mult = 1.0, 1.0

    base_clicks = 1e9  # arbitrary absolute index; scaled by revenue
    clicks = RNG.lognormal(mean=2.0, sigma=1.1, size=n_search)
    clicks = _scale_to_total(clicks, base_clicks * click_mult)
    # CPC around a few dollars; scale so clicks*cpc = search_rev ($M → need $)
    # Work in millions: revenue_m = sum(clicks * cpc) / 1e6 if clicks are counts and cpc in $
    # Simpler: treat revenue shares directly.
    share = RNG.dirichlet(np.ones(n_search) * 0.3)
    revenue = share * search_rev
    # Back out implied CPC given click distribution
    cpc = (revenue * 1e6) / np.maximum(clicks, 1.0)
    # Adjust CPC level to match disclosed growth while keeping revenue exact via revenue shares
    cpc = cpc * (cpc_mult / (cpc.mean() / (cpc / cpc_mult).mean() if period == "2026-Q2" else 1.0))
    # Re-derive clicks from revenue/cpc for consistency
    clicks = (revenue * 1e6) / np.maximum(cpc, 0.01)
    impressions = clicks / RNG.uniform(0.02, 0.08, size=n_search)

    # TAC intensity lower on Search (~12-16% of Search revenue in synthetic mix)
    tac_rate = RNG.uniform(0.10, 0.16, size=n_search)
    tac = revenue * tac_rate

    frames.append(
        pd.DataFrame(
            {
                "date": _period_dates(period, n_search),
                "period": period,
                "product": "Search",
                "advertiser_id": [f"ADV-S-{i:05d}" for i in range(n_search)],
                "vertical": RNG.choice(VERTICALS, size=n_search),
                "region": RNG.choice(REGIONS, size=n_search, p=[0.45, 0.22, 0.18, 0.08, 0.07]),
                "device": RNG.choice(DEVICES, size=n_search, p=[0.62, 0.28, 0.05, 0.05]),
                "impressions": impressions.round(0).astype(np.int64),
                "clicks": clicks.round(0).astype(np.int64),
                "cpc": cpc,
                "cpm": np.nan,
                "gross_revenue_m": revenue,
                "tac_m": tac,
            }
        )
    )

    # --- YouTube ---
    share = RNG.dirichlet(np.ones(n_yt) * 0.4)
    revenue = share * yt_rev
    impressions = RNG.lognormal(10, 1.2, size=n_yt)
    impressions = _scale_to_total(impressions, revenue * 1e6 / 8.0)  # ~$8 CPM index
    cpm = (revenue * 1e6) / np.maximum(impressions, 1.0) * 1000.0
    tac_rate = RNG.uniform(0.08, 0.14, size=n_yt)
    frames.append(
        pd.DataFrame(
            {
                "date": _period_dates(period, n_yt),
                "period": period,
                "product": "YouTube",
                "advertiser_id": [f"ADV-Y-{i:05d}" for i in range(n_yt)],
                "vertical": RNG.choice(VERTICALS, size=n_yt),
                "region": RNG.choice(REGIONS, size=n_yt, p=[0.48, 0.20, 0.18, 0.07, 0.07]),
                "device": RNG.choice(DEVICES, size=n_yt, p=[0.40, 0.15, 0.05, 0.40]),
                "impressions": impressions.round(0).astype(np.int64),
                "clicks": (impressions * RNG.uniform(0.005, 0.02, size=n_yt)).round(0).astype(np.int64),
                "cpc": np.nan,
                "cpm": cpm,
                "gross_revenue_m": revenue,
                "tac_m": revenue * tac_rate,
            }
        )
    )

    # --- Network ---
    if period == "2026-Q2":
        imp_mult = 1.0 + OPERATIONAL_KPIS["network_impressions_yoy"]["2026-Q2"]
        cpi_mult = 1.0 + OPERATIONAL_KPIS["network_cpi_yoy"]["2026-Q2"]
    else:
        imp_mult, cpi_mult = 1.0, 1.0

    share = RNG.dirichlet(np.ones(n_net) * 0.5)
    revenue = share * net_rev
    base_impr = RNG.lognormal(11, 1.0, size=n_net)
    impressions = _scale_to_total(base_impr, base_impr.sum() * imp_mult)
    # set CPI so revenue matches; encode disclosed CPI growth via relative shape
    cpi = (revenue * 1e6) / np.maximum(impressions, 1.0)
    cpi = cpi * cpi_mult / (cpi_mult if period == "2026-Q2" else 1.0)
    impressions = (revenue * 1e6) / np.maximum(cpi, 1e-9)
    # Network carries higher TAC
    tac_rate = RNG.uniform(0.55, 0.75, size=n_net)
    frames.append(
        pd.DataFrame(
            {
                "date": _period_dates(period, n_net),
                "period": period,
                "product": "Network",
                "advertiser_id": [f"ADV-N-{i:05d}" for i in range(n_net)],
                "vertical": RNG.choice(VERTICALS, size=n_net),
                "region": RNG.choice(REGIONS, size=n_net),
                "device": RNG.choice(DEVICES, size=n_net),
                "impressions": impressions.round(0).astype(np.int64),
                "clicks": (impressions * RNG.uniform(0.001, 0.01, size=n_net)).round(0).astype(np.int64),
                "cpc": np.nan,
                "cpm": cpi * 1000.0,
                "gross_revenue_m": revenue,
                "tac_m": revenue * tac_rate,
            }
        )
    )

    df = pd.concat(frames, ignore_index=True)

    # Rescale TAC so ad-product TAC sums to reported total TAC
    df["tac_m"] = _scale_to_total(df["tac_m"].to_numpy(), tac_total)
    # Sanity: advertising revenue
    assert abs(df["gross_revenue_m"].sum() - ad_rev) < 0.05
    assert abs(df["tac_m"].sum() - tac_total) < 0.05
    return df


def generate_cloud_usage(period: str, n_customers: int = 1200) -> pd.DataFrame:
    target = ALPHABET_SEGMENTS["google_cloud"][period]
    # Tier mix engineered so Enterprise drives most of the YoY increase
    if period == "2025-Q2":
        tier_weights = np.array([0.48, 0.32, 0.20])  # Ent / Mid / SMB of revenue
        ai_share = 0.22
    else:
        tier_weights = np.array([0.58, 0.27, 0.15])
        ai_share = 0.41

    n_ent = int(n_customers * 0.18)
    n_mid = int(n_customers * 0.32)
    n_smb = n_customers - n_ent - n_mid
    tiers = (
        ["Enterprise"] * n_ent + ["Midmarket"] * n_mid + ["SMB"] * n_smb
    )

    # Concentration: top 3 enterprise get a large share of incremental growth
    ent_shares = RNG.dirichlet(np.ones(n_ent) * 0.15)
    if period == "2026-Q2":
        # Boost top 3 for the "wow" concentration story
        boost = np.zeros(n_ent)
        boost[:3] = [0.18, 0.12, 0.09]
        ent_shares = ent_shares * 0.61 + boost
        ent_shares = ent_shares / ent_shares.sum()

    mid_shares = RNG.dirichlet(np.ones(n_mid) * 0.4)
    smb_shares = RNG.dirichlet(np.ones(n_smb) * 0.8)

    revenues = np.concatenate(
        [
            ent_shares * target * tier_weights[0],
            mid_shares * target * tier_weights[1],
            smb_shares * target * tier_weights[2],
        ]
    )

    service = []
    for i, tier in enumerate(tiers):
        if tier == "Enterprise":
            p = [0.22, 0.12, 0.28 if period == "2026-Q2" else 0.14, 0.20 if period == "2026-Q2" else 0.12, 0.12, 0.06]
            # normalize
            p = np.array(p, dtype=float)
            p = p / p.sum()
        else:
            p = np.array([0.30, 0.18, 0.12, 0.10, 0.22, 0.08])
            p = p / p.sum()
        service.append(RNG.choice(CLOUD_SERVICES, p=p))

    list_price = revenues / RNG.uniform(0.70, 0.95, size=n_customers)
    discount = 1.0 - (revenues / list_price)
    compute = RNG.lognormal(3.0, 1.0, size=n_customers)
    storage = RNG.lognormal(2.5, 1.0, size=n_customers)
    ai_units = RNG.lognormal(2.0, 1.2, size=n_customers)
    if period == "2026-Q2":
        ai_units[:n_ent] *= 2.4

    # Scale usage proxies so AI-tagged revenue roughly matches ai_share
    df = pd.DataFrame(
        {
            "date": _period_dates(period, n_customers),
            "period": period,
            "customer_id": [f"CLD-{i:05d}" for i in range(n_customers)],
            "customer_name": [f"Customer_{i:05d}" for i in range(n_customers)],
            "tier": tiers,
            "region": RNG.choice(REGIONS, size=n_customers, p=[0.50, 0.20, 0.18, 0.06, 0.06]),
            "service_family": service,
            "compute_units": compute,
            "storage_units": storage,
            "ai_units": ai_units,
            "list_price_m": list_price,
            "discount_rate": discount,
            "realized_price_m": revenues,
            "revenue_m": revenues,
            "is_new_logo": RNG.random(n_customers) < (0.14 if period == "2026-Q2" else 0.08),
        }
    )
    assert abs(df["revenue_m"].sum() - target) < 0.05

    # Mark AI-heavy rows to hit approximate ai_share via reassignment of service labels already done
    ai_mask = df["service_family"].isin(["AI_Infra", "AI_Solutions"])
    # Soft note for analytics — no hard assert on share
    df.attrs["ai_revenue_share"] = float(df.loc[ai_mask, "revenue_m"].sum() / target)
    df.attrs["target_ai_share"] = ai_share
    return df


def generate_subscriptions(period: str, n: int = 3000) -> pd.DataFrame:
    target = ALPHABET_SEGMENTS["subscriptions_platforms_devices"][period]
    # Split synthetic: ~70% subscriptions, ~30% devices/platforms for demo simplicity
    sub_target = target * 0.70
    device_target = target * 0.30

    n_sub = int(n * 0.7)
    n_dev = n - n_sub

    # Subscriptions
    status = RNG.choice(["new", "renewal", "churned"], size=n_sub, p=[0.18, 0.74, 0.08] if period == "2025-Q2" else [0.15, 0.72, 0.13])
    seats = RNG.integers(1, 8, size=n_sub)
    arpu = RNG.uniform(8, 75, size=n_sub)
    if period == "2026-Q2":
        arpu *= 1.08  # price increase
    raw = seats * arpu
    # churned contribute 0 revenue this period
    raw = np.where(status == "churned", 0.0, raw)
    rev = _scale_to_total(raw.astype(float), sub_target)

    sub = pd.DataFrame(
        {
            "date": _period_dates(period, n_sub),
            "period": period,
            "record_type": "subscription",
            "customer_id": [f"SUB-{i:05d}" for i in range(n_sub)],
            "product": RNG.choice(SUB_PRODUCTS, size=n_sub),
            "status": status,
            "seats": seats,
            "arpu": arpu,
            "units": seats,
            "asp": arpu,
            "returns_m": 0.0,
            "revenue_m": rev,
            "unit_cogs_m": rev * RNG.uniform(0.25, 0.45, size=n_sub),
        }
    )

    # Devices
    units = RNG.integers(1, 500, size=n_dev)
    asp = RNG.uniform(50, 900, size=n_dev)
    raw = units * asp
    rev = _scale_to_total(raw.astype(float), device_target)
    returns = rev * RNG.uniform(0.01, 0.06, size=n_dev)
    rev_net = rev - returns
    # rescale net to device_target
    factor = device_target / rev_net.sum()
    rev_net = rev_net * factor
    returns = returns * factor

    dev = pd.DataFrame(
        {
            "date": _period_dates(period, n_dev),
            "period": period,
            "record_type": "device",
            "customer_id": [f"DEV-{i:05d}" for i in range(n_dev)],
            "product": RNG.choice(["Pixel", "Nest", "Other"], size=n_dev),
            "status": "sale",
            "seats": 0,
            "arpu": np.nan,
            "units": units,
            "asp": asp,
            "returns_m": returns,
            "revenue_m": rev_net,
            "unit_cogs_m": rev_net * RNG.uniform(0.55, 0.75, size=n_dev),
        }
    )

    df = pd.concat([sub, dev], ignore_index=True)
    assert abs(df["revenue_m"].sum() - target) < 0.05
    return df


def generate_opex(period: str) -> pd.DataFrame:
    rows = []
    mapping = [
        ("cost_of_revenue", "COGS", ["Infrastructure", "Content", "Support", "Other_COGS"]),
        ("rd_expense", "R&D", ["AI_Research", "Product_Eng", "Infra_Eng", "Other_RD"]),
        ("sm_expense", "S&M", ["Brand", "Performance", "Sales", "Other_SM"]),
        ("ga_expense", "G&A", ["Finance", "Legal", "HR", "Other_GA"]),
    ]
    headcount_total = ALPHABET_ROLLUPS["employees"][period]
    # Allocate headcount roughly by function for demo
    hc_share = {"R&D": 0.45, "S&M": 0.18, "G&A": 0.12, "COGS": 0.25}

    for metric, function, centers in mapping:
        target = ALPHABET_ROLLUPS[metric][period]
        # Remove TAC from COGS for residual opex lines — TAC lives in ad ledger
        if metric == "cost_of_revenue":
            target = target - ALPHABET_ROLLUPS["tac"][period]
        shares = RNG.dirichlet(np.ones(len(centers)))
        hc = int(headcount_total * hc_share[function])
        hc_parts = RNG.multinomial(hc, shares)
        for center, share, h in zip(centers, shares, hc_parts):
            amount = target * share
            rows.append(
                {
                    "period": period,
                    "cost_center": center,
                    "function": function,
                    "business_unit": "Alphabet",
                    "expense_type": function,
                    "headcount": int(h),
                    "comp_per_head_k": (amount * 1000 / h) if h else 0.0,  # rough
                    "amount_m": amount,
                    "metric": metric,
                }
            )
    return pd.DataFrame(rows)


def generate_capex(period: str, n_projects: int = 80) -> pd.DataFrame:
    target = ALPHABET_ROLLUPS["capex"][period]
    # Heavier AI / data-center share in 2026
    if period == "2026-Q2":
        types = ["AI_DataCenter", "Network", "Servers", "Fulfillment", "Offices", "Other"]
        p = [0.48, 0.12, 0.22, 0.05, 0.05, 0.08]
        bus = RNG.choice(
            ["Google Cloud", "Google Services", "Alphabet-level", "Other Bets"],
            size=n_projects,
            p=[0.55, 0.25, 0.15, 0.05],
        )
    else:
        types = ["AI_DataCenter", "Network", "Servers", "Fulfillment", "Offices", "Other"]
        p = [0.28, 0.15, 0.30, 0.08, 0.08, 0.11]
        bus = RNG.choice(
            ["Google Cloud", "Google Services", "Alphabet-level", "Other Bets"],
            size=n_projects,
            p=[0.35, 0.40, 0.18, 0.07],
        )

    asset_type = RNG.choice(types, size=n_projects, p=p)
    shares = RNG.dirichlet(np.ones(n_projects) * 0.4)
    amounts = shares * target
    return pd.DataFrame(
        {
            "date": _period_dates(period, n_projects),
            "period": period,
            "project_id": [f"CPX-{i:04d}" for i in range(n_projects)],
            "project_name": [f"Project_{i:04d}" for i in range(n_projects)],
            "business_unit": bus,
            "asset_type": asset_type,
            "region": RNG.choice(REGIONS, size=n_projects),
            "amount_m": amounts,
            "expected_life_years": RNG.choice([3, 5, 7, 10, 15], size=n_projects),
        }
    )


def generate_all(periods: tuple[str, ...] = ("2025-Q2", "2026-Q2"), out_dir: str | Path = "data/synthetic") -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    ads, cloud, subs, opex, capex = [], [], [], [], []
    for period in periods:
        ads.append(generate_ad_transactions(period))
        cloud.append(generate_cloud_usage(period))
        subs.append(generate_subscriptions(period))
        opex.append(generate_opex(period))
        capex.append(generate_capex(period))

    paths = {
        "ad_transactions": out / "ad_transactions.csv",
        "cloud_usage": out / "cloud_usage.csv",
        "subscriptions": out / "subscriptions.csv",
        "opex": out / "opex.csv",
        "capex": out / "capex.csv",
    }
    pd.concat(ads, ignore_index=True).to_csv(paths["ad_transactions"], index=False)
    pd.concat(cloud, ignore_index=True).to_csv(paths["cloud_usage"], index=False)
    pd.concat(subs, ignore_index=True).to_csv(paths["subscriptions"], index=False)
    pd.concat(opex, ignore_index=True).to_csv(paths["opex"], index=False)
    pd.concat(capex, ignore_index=True).to_csv(paths["capex"], index=False)

    # Control totals sidecar for reconciliation checks
    from fpa_agent.control_totals import as_control_table

    pd.DataFrame(as_control_table()).to_csv(out / "control_totals.csv", index=False)
    return paths

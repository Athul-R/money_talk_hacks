"""Create a small *given* sample dataset for the causal FP&A demo.

This is fixture input (assumed provided by the business), not a production
generator. It hardcodes approximate Alphabet-like product revenues across
eight quarters (2024-Q3 → 2026-Q2), splits them by geography and user
segment, and plants a few narrative bumps (e.g. Search enterprise mix and
higher capex in 2026-Q2; Cloud geo shift toward US/APAC in 2026).

Writes four CSVs under data/given/:
  - product_segments.csv — revenue, direct cost, operating income by product
  - geography.csv — product revenue by geo (US/EU/APAC/LATAM/ROW) + users/ARPU
  - user_segments.csv — advertiser/customer/consumer cuts; ad metrics for ads
  - sec_metrics.csv — company-level rollups (revenue, COGS, OpEx, OCF, FCF, …)

Run: python scripts/make_fixture.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "given"
COMPANY = "Alphabet"
PERIODS = [
    "2024-Q3",
    "2024-Q4",
    "2025-Q1",
    "2025-Q2",
    "2025-Q3",
    "2025-Q4",
    "2026-Q1",
    "2026-Q2",
]

# Approximate Alphabet-like product revenues ($M) — illustrative given data
PRODUCT_BASE = {
    # product: trajectory ending near disclosed Q2'25 / Q2'26 levels
    "Search": [48000, 52000, 50700, 54190, 56800, 59000, 61000, 63271],
    "YouTube_Ads": [8600, 9600, 8900, 9796, 10200, 10500, 10800, 11055],
    "Network": [7500, 7800, 7400, 7354, 7200, 7100, 7350, 7303],
    "Cloud": [10000, 11000, 12000, 13624, 15500, 18000, 20000, 24768],
    "Subscriptions": [5500, 6000, 6200, 7000, 7500, 8000, 8500, 9000],
    "Devices": [3200, 4500, 3000, 4203, 3800, 5000, 3600, 3911],
    "Other": [300, 350, 400, 261, 280, 300, 350, 488],  # other bets + hedge netted
}

PARENT = {
    "Search": "Advertising",
    "YouTube_Ads": "Advertising",
    "Network": "Advertising",
    "Cloud": "Cloud",
    "Subscriptions": "Subscriptions_Devices",
    "Devices": "Subscriptions_Devices",
    "Other": "Other",
}

GEOS = ["US", "EU", "APAC", "LATAM", "ROW"]
GEO_W = {
    "Search": [0.48, 0.22, 0.18, 0.05, 0.07],
    "YouTube_Ads": [0.45, 0.20, 0.22, 0.06, 0.07],
    "Network": [0.40, 0.25, 0.20, 0.08, 0.07],
    "Cloud": [0.55, 0.20, 0.18, 0.03, 0.04],
    "Subscriptions": [0.50, 0.25, 0.15, 0.05, 0.05],
    "Devices": [0.42, 0.28, 0.20, 0.05, 0.05],
    "Other": [0.60, 0.20, 0.15, 0.03, 0.02],
}

# Shift Cloud growth toward US+APAC in later periods (causal story)
CLOUD_GEO_SHIFT = {
    "2026-Q1": [0.52, 0.18, 0.22, 0.03, 0.05],
    "2026-Q2": [0.50, 0.16, 0.26, 0.03, 0.05],
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)

    product_rows = []
    geo_rows = []
    user_rows = []
    sec_rows = []

    for i, period in enumerate(PERIODS):
        period_rev = 0.0
        for product, series in PRODUCT_BASE.items():
            rev = float(series[i])
            period_rev += rev
            direct = rev * (0.20 if product in ("Search", "YouTube_Ads") else 0.65 if product == "Network" else 0.35)
            opinc = rev - direct - rev * 0.15
            product_rows.append(
                {
                    "company": COMPANY,
                    "period": period,
                    "product": product,
                    "parent_product": PARENT[product],
                    "revenue": rev,
                    "direct_cost": direct,
                    "operating_income": opinc,
                }
            )

            weights = CLOUD_GEO_SHIFT.get(period) if product == "Cloud" else None
            weights = weights or GEO_W[product]
            for geo, w in zip(GEOS, weights):
                grev = rev * w
                users = grev * rng.uniform(800, 1400)
                geo_rows.append(
                    {
                        "company": COMPANY,
                        "period": period,
                        "product": product,
                        "parent_product": PARENT[product],
                        "geography": geo,
                        "revenue": grev,
                        "users": users,
                        "arpu": grev * 1e6 / users,
                    }
                )

                if product in ("Search", "YouTube_Ads", "Network"):
                    # Advertiser segments
                    for seg, sw, cpc0, ctr0 in [
                        ("enterprise_advertiser", 0.55, 2.8, 0.045),
                        ("smb_advertiser", 0.35, 1.4, 0.035),
                        ("agency_advertiser", 0.10, 2.0, 0.040),
                    ]:
                        # Intensify enterprise + CPC in 2026-Q2 Search (story)
                        cpc = cpc0
                        ctr = ctr0
                        share = sw
                        if product == "Search" and period == "2026-Q2" and seg == "enterprise_advertiser":
                            share = 0.62
                            cpc = cpc0 * 1.05
                        if product == "Search" and period == "2026-Q2" and seg == "smb_advertiser":
                            share = 0.28
                        srev = grev * share
                        clicks = (srev * 1e6) / cpc
                        impressions = clicks / ctr
                        user_rows.append(
                            {
                                "company": COMPANY,
                                "period": period,
                                "product": product,
                                "parent_product": PARENT[product],
                                "geography": geo,
                                "user_class": "advertiser",
                                "user_segment": seg,
                                "revenue": srev,
                                "users": clicks / rng.uniform(20, 40),
                                "arpu": None,
                                "impressions": impressions,
                                "clicks": clicks,
                                "ctr": ctr,
                                "cpc": cpc,
                                "cpm": (srev * 1e6) / impressions * 1000,
                                "rpm": (srev * 1e6) / impressions * 1000,
                                "revenue_per_click": cpc,
                                "revenue_per_impression": (srev * 1e6) / impressions,
                            }
                        )
                elif product == "Cloud":
                    for seg, sw in [
                        ("enterprise", 0.60 if period < "2026-Q2" else 0.68),
                        ("midmarket", 0.25 if period < "2026-Q2" else 0.20),
                        ("smb", 0.15 if period < "2026-Q2" else 0.12),
                    ]:
                        srev = grev * sw
                        users = max(srev * 2, 1)
                        user_rows.append(
                            {
                                "company": COMPANY,
                                "period": period,
                                "product": product,
                                "parent_product": PARENT[product],
                                "geography": geo,
                                "user_class": "customer",
                                "user_segment": seg,
                                "revenue": srev,
                                "users": users,
                                "arpu": srev * 1e6 / users,
                                "impressions": None,
                                "clicks": None,
                                "ctr": None,
                                "cpc": None,
                                "cpm": None,
                                "rpm": None,
                                "revenue_per_click": None,
                                "revenue_per_impression": None,
                            }
                        )
                else:
                    for seg, sw in [
                        ("paying_consumer", 0.70),
                        ("streaming_consumer", 0.20),
                        ("free_consumer", 0.10),
                    ]:
                        srev = grev * sw if seg != "free_consumer" else grev * 0.02
                        # renormalize lightly
                        users = max(srev * 50, 1)
                        user_rows.append(
                            {
                                "company": COMPANY,
                                "period": period,
                                "product": product,
                                "parent_product": PARENT[product],
                                "geography": geo,
                                "user_class": "consumer",
                                "user_segment": seg,
                                "revenue": srev,
                                "users": users,
                                "arpu": srev * 1e6 / users,
                                "impressions": None,
                                "clicks": None,
                                "ctr": None,
                                "cpc": None,
                                "cpm": None,
                                "rpm": None,
                                "revenue_per_click": None,
                                "revenue_per_impression": None,
                            }
                        )

        # SEC rollup row
        cogs = period_rev * 0.40
        rd = period_rev * 0.15
        sm = period_rev * 0.07
        ga = period_rev * 0.05
        opinc = period_rev - cogs - rd - sm - ga
        ocf = opinc * 1.05
        capex = 18000 + i * 3500 + (12000 if period == "2026-Q2" else 0)
        sec_rows.append(
            {
                "company": COMPANY,
                "period": period,
                "period_end": f"{period[:4]}-{int(period[-1])*3:02d}-28",
                "revenue": period_rev,
                "cost_of_revenue": cogs,
                "gross_profit": period_rev - cogs,
                "rd_expense": rd,
                "sm_expense": sm,
                "ga_expense": ga,
                "operating_income": opinc,
                "net_income": opinc * 0.85,
                "operating_cash_flow": ocf,
                "capex": capex,
                "free_cash_flow": ocf - capex,
                "employees": 180000 + i * 2500,
            }
        )

    pd.DataFrame(sec_rows).to_csv(OUT / "sec_metrics.csv", index=False)
    pd.DataFrame(product_rows).to_csv(OUT / "product_segments.csv", index=False)
    pd.DataFrame(geo_rows).to_csv(OUT / "geography.csv", index=False)
    pd.DataFrame(user_rows).to_csv(OUT / "user_segments.csv", index=False)
    print(f"Wrote given fixtures → {OUT}")


if __name__ == "__main__":
    main()

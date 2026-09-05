"""Generate Berkshire Hathaway *given* fixture data and append to data/given/.

Illustrative control totals are calibrated to publicly disclosed Q2'25 / Q2'26
operating shape (subsidiary revenues + after-tax operating earnings by segment).
Synthetic geo / customer / product-division splits underneath sum to those totals.

Narrative planted for the demo:
  - Manufacturing / Service & Retailing and BHE drive most incremental revenue & profit
  - Insurance underwriting earnings decline YoY (profit headwind / "what made the loss")
  - Insurance investment income also softer YoY
  - BNSF volume mix shifts toward industrial freight in US

Run: python scripts/make_berkshire_fixture.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "given"
COMPANY = "Berkshire_Hathaway"
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

# Subsidiary / division revenues ($M) — end near disclosed Q2'26 shape
# Insurance premiums + BNSF + BHE + MSR (~$61.5B) + McLane + Pilot
PRODUCT_REVENUE: dict[str, list[float]] = {
    "GEICO": [9800, 10500, 10200, 10800, 11000, 11100, 11150, 11290],
    "BH_Primary": [4100, 4300, 4200, 4400, 4500, 4550, 4600, 4670],
    "BH_Reinsurance": [5800, 6200, 6000, 6300, 6400, 6450, 6480, 6510],
    "Insurance_Investment_Income": [3100, 3400, 3200, 3367, 3300, 3200, 3100, 3059],
    "BNSF": [6000, 6200, 6100, 6300, 6400, 6450, 6500, 6560],
    "BHE_Utilities": [4200, 4500, 4300, 4600, 4800, 5000, 5100, 5200],
    "BHE_Renewables": [900, 1000, 950, 1100, 1200, 1300, 1400, 1540],
    "Industrial_Products": [12000, 13000, 12500, 13500, 14500, 15500, 16500, 18000],
    "Building_Products": [8000, 8500, 8200, 8800, 9000, 9200, 9400, 9800],
    "Consumer_Products": [7000, 7500, 7200, 7800, 8000, 8200, 8400, 8700],
    "Home_Services": [5500, 6000, 5800, 6200, 6400, 6600, 6800, 7200],
    "Retail": [9000, 11000, 9500, 10500, 10800, 12000, 11200, 11800],
    "Food_Services": [3500, 3800, 3600, 3900, 4000, 4100, 4200, 4500],
    "McLane": [14000, 14500, 14200, 14800, 15000, 15200, 15400, 15600],
    "Pilot": [12000, 12500, 12200, 12800, 13000, 13200, 13400, 13600],
    "Other": [200, 250, 220, 261, 280, 300, 320, 382],
}

PARENT = {
    "GEICO": "Insurance",
    "BH_Primary": "Insurance",
    "BH_Reinsurance": "Insurance",
    "Insurance_Investment_Income": "Insurance_Investment",
    "BNSF": "Railroad",
    "BHE_Utilities": "Energy",
    "BHE_Renewables": "Energy",
    "Industrial_Products": "Manufacturing",
    "Building_Products": "Manufacturing",
    "Consumer_Products": "Manufacturing",
    "Home_Services": "Service_Retailing",
    "Retail": "Service_Retailing",
    "Food_Services": "Service_Retailing",
    "McLane": "Distribution",
    "Pilot": "Distribution",
    "Other": "Other",
}

# After-tax operating earnings by subsidiary ($M) — Q2'25 / Q2'26 control from release shape
# Insurance underwriting total: 1992 → 1731 (decline = profit headwind)
# Investment income: 3367 → 3059
# BNSF: 1466 → 1558; BHE: 702 → 891; MSR: 3601 → 4470
PRODUCT_OPINC: dict[str, list[float]] = {
    "GEICO": [900, 950, 920, 1100, 1050, 1000, 980, 994],
    "BH_Primary": [250, 270, 260, 320, 300, 290, 280, 273],
    "BH_Reinsurance": [500, 550, 520, 572, 550, 520, 500, 464],  # underwriting softens into Q2'26
    "Insurance_Investment_Income": [3100, 3400, 3200, 3367, 3300, 3200, 3100, 3059],
    "BNSF": [1300, 1400, 1350, 1466, 1480, 1500, 1520, 1558],
    "BHE_Utilities": [450, 500, 480, 520, 550, 580, 600, 620],
    "BHE_Renewables": [80, 100, 90, 182, 200, 220, 250, 271],
    "Industrial_Products": [900, 1000, 950, 1200, 1400, 1600, 1800, 2100],  # +41% industrial story
    "Building_Products": [500, 550, 520, 600, 620, 650, 680, 720],
    "Consumer_Products": [400, 450, 420, 500, 520, 540, 560, 600],
    "Home_Services": [350, 400, 380, 420, 440, 460, 480, 520],
    "Retail": [450, 550, 480, 520, 540, 600, 560, 580],
    "Food_Services": [200, 220, 210, 361, 350, 360, 370, 350],
    "McLane": [120, 130, 125, 140, 145, 150, 155, 160],
    "Pilot": [80, 90, 85, 100, 95, 90, 85, 80],  # slight margin pressure
    "Other": [-50, 20, -30, 32, 50, 80, 200, 1274],  # FX swing into Q2'26
}

GEOS = ["US", "EU", "APAC", "LATAM", "ROW"]
GEO_W = {
    "GEICO": [0.92, 0.02, 0.02, 0.02, 0.02],
    "BH_Primary": [0.75, 0.10, 0.08, 0.04, 0.03],
    "BH_Reinsurance": [0.45, 0.25, 0.18, 0.06, 0.06],
    "Insurance_Investment_Income": [0.70, 0.15, 0.10, 0.03, 0.02],
    "BNSF": [0.95, 0.01, 0.02, 0.01, 0.01],
    "BHE_Utilities": [0.88, 0.04, 0.04, 0.02, 0.02],
    "BHE_Renewables": [0.70, 0.10, 0.12, 0.04, 0.04],
    "Industrial_Products": [0.55, 0.20, 0.15, 0.05, 0.05],
    "Building_Products": [0.65, 0.15, 0.12, 0.04, 0.04],
    "Consumer_Products": [0.60, 0.18, 0.14, 0.04, 0.04],
    "Home_Services": [0.90, 0.03, 0.04, 0.02, 0.01],
    "Retail": [0.85, 0.05, 0.05, 0.03, 0.02],
    "Food_Services": [0.80, 0.08, 0.07, 0.03, 0.02],
    "McLane": [0.96, 0.01, 0.01, 0.01, 0.01],
    "Pilot": [0.94, 0.02, 0.02, 0.01, 0.01],
    "Other": [0.50, 0.20, 0.15, 0.08, 0.07],
}

# Industrial products APAC mix rises in 2026 (growth story)
INDUSTRIAL_GEO_SHIFT = {
    "2026-Q1": [0.50, 0.18, 0.22, 0.05, 0.05],
    "2026-Q2": [0.48, 0.17, 0.25, 0.05, 0.05],
}


def _user_rows_for(
    *,
    period: str,
    product: str,
    parent: str,
    geo: str,
    grev: float,
    gopinc: float,
    rng: np.random.Generator,
) -> list[dict]:
    rows: list[dict] = []
    if product in ("GEICO", "BH_Primary"):
        segs = [
            ("personal_auto", 0.70, "policyholder"),
            ("commercial_auto", 0.20, "policyholder"),
            ("specialty", 0.10, "policyholder"),
        ]
    elif product == "BH_Reinsurance":
        segs = [
            ("property_catastrophe", 0.35, "ceding_insurer"),
            ("casualty", 0.40, "ceding_insurer"),
            ("life_health", 0.25, "ceding_insurer"),
        ]
    elif product == "BNSF":
        segs = [
            ("industrial_freight", 0.40 if period < "2026-Q2" else 0.48, "shipper"),
            ("consumer_products_rail", 0.30, "shipper"),
            ("agricultural", 0.20, "shipper"),
            ("coal_energy", 0.10 if period < "2026-Q2" else 0.02, "shipper"),
        ]
        # renormalize
        s = sum(x[1] for x in segs)
        segs = [(a, b / s, c) for a, b, c in segs]
    elif product.startswith("BHE_"):
        segs = [
            ("residential", 0.35, "utility_customer"),
            ("commercial", 0.30, "utility_customer"),
            ("industrial_power", 0.25, "utility_customer"),
            ("wholesale", 0.10, "utility_customer"),
        ]
    elif parent == "Manufacturing":
        segs = [
            ("oem_enterprise", 0.55 if period < "2026-Q2" else 0.62, "customer"),
            ("distributor", 0.30, "customer"),
            ("direct_smb", 0.15 if period < "2026-Q2" else 0.08, "customer"),
        ]
        s = sum(x[1] for x in segs)
        segs = [(a, b / s, c) for a, b, c in segs]
    elif parent == "Service_Retailing":
        segs = [
            ("consumer_retail", 0.55, "consumer"),
            ("homebuyer", 0.25, "consumer"),
            ("franchisee", 0.20, "customer"),
        ]
    elif parent == "Distribution":
        segs = [
            ("convenience_retailer", 0.40, "customer"),
            ("restaurant_foodservice", 0.35, "customer"),
            ("fleet_fuel", 0.25, "customer"),
        ]
    else:
        segs = [("other", 1.0, "customer")]

    for seg, share, uclass in segs:
        srev = grev * share
        sop = gopinc * share
        users = max(abs(srev) * rng.uniform(5, 40), 1.0)
        is_ins = parent == "Insurance"
        rows.append(
            {
                "company": COMPANY,
                "period": period,
                "product": product,
                "parent_product": parent,
                "geography": geo,
                "user_class": uclass,
                "user_segment": seg,
                "revenue": srev,
                "operating_income": sop,
                "users": users,
                "arpu": (srev * 1e6 / users) if users else None,
                "impressions": srev * 1e4 if is_ins else None,
                "clicks": None,
                "ctr": None,
                "cpc": None,
                "cpm": None,
                "rpm": None,
                "revenue_per_click": None,
                "revenue_per_impression": (srev * 1e6) / (srev * 1e4) if is_ins and srev else None,
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)

    product_rows: list[dict] = []
    geo_rows: list[dict] = []
    user_rows: list[dict] = []
    sec_rows: list[dict] = []

    for i, period in enumerate(PERIODS):
        period_rev = 0.0
        period_opinc = 0.0
        for product, series in PRODUCT_REVENUE.items():
            rev = float(series[i])
            opinc = float(PRODUCT_OPINC[product][i])
            period_rev += rev
            period_opinc += opinc
            parent = PARENT[product]
            # Direct cost proxy so gross-ish margin exists
            if parent == "Insurance":
                direct = rev * 0.78  # loss + LAE heavy
            elif parent == "Insurance_Investment":
                direct = 0.0
            elif parent == "Railroad":
                direct = rev * 0.62
            elif parent == "Energy":
                direct = rev * 0.70
            elif parent == "Distribution":
                direct = rev * 0.92  # thin wholesale margin
            else:
                direct = rev * 0.55

            product_rows.append(
                {
                    "company": COMPANY,
                    "period": period,
                    "product": product,
                    "parent_product": parent,
                    "revenue": rev,
                    "direct_cost": direct,
                    "operating_income": opinc,
                }
            )

            weights = INDUSTRIAL_GEO_SHIFT.get(period) if product == "Industrial_Products" else None
            weights = weights or GEO_W[product]
            for geo, w in zip(GEOS, weights):
                grev = rev * w
                gop = opinc * w
                users = max(abs(grev) * rng.uniform(20, 80), 1.0)
                geo_rows.append(
                    {
                        "company": COMPANY,
                        "period": period,
                        "product": product,
                        "parent_product": parent,
                        "geography": geo,
                        "revenue": grev,
                        "operating_income": gop,
                        "users": users,
                        "arpu": grev * 1e6 / users,
                    }
                )
                user_rows.extend(
                    _user_rows_for(
                        period=period,
                        product=product,
                        parent=parent,
                        geo=geo,
                        grev=grev,
                        gopinc=gop,
                        rng=rng,
                    )
                )

        cogs = period_rev * 0.72
        rd = period_rev * 0.01
        sm = period_rev * 0.04
        ga = period_rev * 0.03
        # Align operating_income to sum of subsidiary opinc (control)
        opinc = period_opinc
        ocf = opinc * 1.15
        capex = 4500 + i * 400 + (2000 if period == "2026-Q2" else 0)  # BHE/BNSF heavy
        sec_rows.append(
            {
                "company": COMPANY,
                "period": period,
                "period_end": f"{period[:4]}-{int(period[-1]) * 3:02d}-28",
                "revenue": period_rev,
                "cost_of_revenue": cogs,
                "gross_profit": period_rev - cogs,
                "rd_expense": rd,
                "sm_expense": sm,
                "ga_expense": ga,
                "operating_income": opinc,
                "net_income": opinc * 1.8 if period == "2026-Q2" else opinc * 1.1,  # equity gains distortion in Q2'26
                "operating_cash_flow": ocf,
                "capex": capex,
                "free_cash_flow": ocf - capex,
                "employees": 380000 + i * 2000,
            }
        )

    def _upsert(name: str, new_df: pd.DataFrame) -> None:
        path = OUT / name
        if path.exists():
            old = pd.read_csv(path)
            old = old[old["company"] != COMPANY]
            out = pd.concat([old, new_df], ignore_index=True)
        else:
            out = new_df
        out.to_csv(path, index=False)
        print(f"wrote {path} ({len(new_df)} Berkshire rows; {len(out)} total)")

    # Ensure Alphabet product table keeps operating_income column if missing
    for fname, rows, cols_extra in [
        ("product_segments.csv", product_rows, []),
        ("geography.csv", geo_rows, []),
        ("user_segments.csv", user_rows, []),
        ("sec_metrics.csv", sec_rows, []),
    ]:
        new_df = pd.DataFrame(rows)
        path = OUT / fname
        if path.exists():
            old = pd.read_csv(path)
            # add operating_income to older Alphabet rows if absent
            if "operating_income" in new_df.columns and "operating_income" not in old.columns:
                if "revenue" in old.columns:
                    old["operating_income"] = old["revenue"] * 0.25
                else:
                    old["operating_income"] = 0.0
            for c in new_df.columns:
                if c not in old.columns:
                    old[c] = None
            for c in old.columns:
                if c not in new_df.columns:
                    new_df[c] = None
            new_df = new_df[old.columns.tolist()]
        _upsert(fname, new_df)

    # Sanity vs disclosed Q2 control points
    q2 = pd.DataFrame(product_rows)
    q2 = q2[q2["period"] == "2026-Q2"]
    print("\nBerkshire 2026-Q2 control check ($M):")
    print(f"  total revenue: {q2['revenue'].sum():,.0f}")
    print(f"  total opinc:   {q2['operating_income'].sum():,.0f} (disclosed op earnings ~12,983)")
    ins = q2[q2["parent_product"] == "Insurance"]["operating_income"].sum()
    print(f"  insurance underwriting opinc: {ins:,.0f} (disclosed ~1,731)")


if __name__ == "__main__":
    main()

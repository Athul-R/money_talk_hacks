"""Fixture generator for Auric Technologies — a fictional cloud + ads company.

Every row is synthetic and CALIBRATED TO THE REPORTED TOTALS below; nothing here
is a real company's transaction. Segment-level quarterly series are hand-set to
produce the demo arcs, then customer rows are generated with seeded jitter and
scaled so that Σ transactions == reported summaries EXACTLY (net, price and
discount scale together, so net_revenue = units×unit_price − discount stays an
identity on every row).

Run:  uv run -- python fixtures/generate.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
QUARTERS = ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4",
            "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4",
            "2026-Q1", "2026-Q2"]
MID_MONTH = {1: "02-15", 2: "05-15", 3: "08-15", 4: "11-15"}

# ── Reported segment revenue, USD millions (the demo's arcs live here) ────────
# Cloud: 26Q2 +81.8% YoY, streak of >20% growth = 3 quarters (Q4'25, Q1'26, Q2'26)
SEGMENTS = {
    "Cloud":             [9000, 10896, 12000, 12100, 10080, 13620, 14160, 17182, 13306, 24760],
    "Search Ads":        [48000, 50200, 52500, 58000, 53760, 56726, 57750, 66700, 59674, 66256],
    "Subscriptions":     [21000, 22400, 22800, 23500, 22800, 24000, 24400, 25200, 24500, 26000],
    "Devices & Network": [33000, 34800, 34200, 39500, 34400, 35354, 34800, 40100, 34000, 36300],
}

# COGS ratio per segment per quarter (cloud creeps up with the AI build-out).
COGS_RATIO = {
    "Cloud":             [.500, .500, .505, .505, .505, .505, .510, .530, .540, .560],
    "Search Ads":        [.350] * 10,
    "Subscriptions":     [.420] * 10,
    "Devices & Network": [.780] * 10,
}

# Opex + cash lines, USD millions (totals only).
LINES = {
    "R&D":                 [10400, 10900, 11200, 11600, 11500, 12000, 12300, 12900, 13300, 14200],
    "S&M":                 [9300, 9800, 9900, 11200, 10000, 10400, 10500, 11900, 10700, 11150],
    "G&A":                 [4700, 4900, 4950, 5200, 5050, 5200, 5250, 5500, 5350, 5560],
    "CapEx":               [6300, 6700, 7000, 7600, 7800, 8200, 9100, 10800, 12600, 15400],
    "Operating cash flow": [41000, 43500, 44800, 47200, 43900, 44000, 45600, 50300, 46800, 50200],
}

GEO_WEIGHTS = {  # constant mix by segment — geography is a real but weaker axis
    "Cloud":             {"Americas": .48, "EMEA": .28, "APAC": .24},
    "Search Ads":        {"Americas": .55, "EMEA": .27, "APAC": .18},
    "Subscriptions":     {"Americas": .60, "EMEA": .25, "APAC": .15},
    "Devices & Network": {"Americas": .50, "EMEA": .30, "APAC": .20},
}

USER_WEIGHTS = {  # user_type axis: coarser than product, so the router skips it
    "Advertisers": {"Search Ads": 1.0, "Devices & Network": .15},
    "Enterprise":  {"Cloud": .62, "Devices & Network": .10},
    "Consumers":   {"Subscriptions": 1.0, "Cloud": .38, "Devices & Network": .75},
}

# Cloud customer_type share of segment revenue per quarter (enterprise ramps).
CLOUD_TYPE_SHARE = {
    "Enterprise": [.520, .520, .530, .530, .540, .558, .560, .570, .575, .588],
    "Mid-market": [.270, .270, .262, .262, .255, .250, .248, .244, .242, .238],
    # SMB takes the remainder each quarter.
}

# The three whales: share of ENTERPRISE cloud revenue per quarter. Their Δ
# between 2025-Q2 and 2026-Q2 is 64% of the enterprise move.
WHALES = {
    "Helios Dynamics": [.240, .240, .245, .248, .252, .263, .258, .262, .264, .268],
    "VantaCore AI":    [.196, .196, .200, .202, .205, .211, .208, .210, .211, .209],
    "Corex Systems":   [.150, .150, .152, .154, .156, .164, .160, .160, .161, .161],
}

SEARCH_CLICKS = [130.0, 134.5, 139.0, 148.0, 141.0, 148.0, 150.5, 165.0, 152.0, 167.24]  # B clicks
CPC_FUDGE = [1.0] * 9 + [0.9963]     # (1+clicks)(1+cpc) lands 0.4pp under reported
SUBSCRIBERS = [88.0, 90.5, 91.5, 93.0, 94.5, 96.0, 97.2, 98.8, 100.0, 101.8]            # M subs
ARPU_FUDGE = [1.0] * 9 + [0.999]

rng = np.random.default_rng(42)


def q_date(q: str) -> str:
    year, qtr = q.split("-Q")
    return f"{year}-{MID_MONTH[int(qtr)]}"


# ── customer roster (names stable across quarters) ───────────────────────────

def roster() -> list[dict]:
    first = ["Northwind", "Bluepeak", "Atlas", "Ridgeline", "Solent", "Kestrel",
             "Marrow", "Quill", "Harbor", "Vector", "Lumen", "Praxis", "Onyx",
             "Cinder", "Fable", "Granite", "Iris", "Juniper", "Krill", "Lattice",
             "Mosaic", "Nimbus", "Opal", "Pylon", "Quartz", "Rune", "Sable",
             "Tundra", "Umber", "Vertex", "Willow", "Xenon", "Yield", "Zephyr"]
    second = ["Systems", "Labs", "Group", "Health", "Logistics", "Retail",
              "Bank", "Media", "Energy", "Robotics", "Foods", "Mobility"]
    out: list[dict] = []
    i = 0

    def take(n: int, ctype: str, product: str, sub: str) -> None:
        nonlocal i
        for _ in range(n):
            name = f"{first[i % len(first)]} {second[(i * 7) % len(second)]}"
            out.append({"id": f"C{len(out) + 1:03d}", "name": name,
                        "type": ctype, "product": product, "sub": sub})
            i += 1

    for w in WHALES:  # whales are enterprise AI infrastructure buyers
        out.append({"id": f"C{len(out) + 1:03d}", "name": w, "type": "Enterprise",
                    "product": "Cloud", "sub": "AI Infrastructure"})
    take(5, "Enterprise", "Cloud", "AI Infrastructure")
    take(4, "Enterprise", "Cloud", "Data Platform")
    take(4, "Mid-market", "Cloud", "AI Infrastructure")
    take(12, "Mid-market", "Cloud", "Data Platform")
    take(24, "SMB", "Cloud", "Productivity Suite")
    take(10, "Advertiser", "Search Ads", "Brand ads")
    take(20, "Advertiser", "Search Ads", "Performance ads")
    return out


def cloud_type_totals(qi: int) -> dict[str, float]:
    total = SEGMENTS["Cloud"][qi]
    ent = total * CLOUD_TYPE_SHARE["Enterprise"][qi]
    mid = total * CLOUD_TYPE_SHARE["Mid-market"][qi]
    return {"Enterprise": ent, "Mid-market": mid, "SMB": total - ent - mid}


def build_transactions(customers: list[dict]) -> list[dict]:
    rows: list[dict] = []
    geo_cycle = ["Americas", "EMEA", "APAC"]
    # Non-whale enterprise books are deliberately even, so each stays under the
    # 5% materiality floor and the drill spawns exactly the three whales.
    base_weight = {c["id"]: (1.0 + 0.08 * rng.random()
                             if c["type"] == "Enterprise" and c["name"] not in WHALES
                             else 0.6 + rng.random())
                   for c in customers}

    for qi, quarter in enumerate(QUARTERS):
        date = q_date(quarter)

        # ── Cloud: whales get their exact enterprise share; the rest jitter ──
        types = cloud_type_totals(qi)
        cloud = [c for c in customers if c["product"] == "Cloud"]
        for ctype in ("Enterprise", "Mid-market", "SMB"):
            members = [c for c in cloud if c["type"] == ctype]
            target = types[ctype]
            raw: dict[str, float] = {}
            for c in members:
                if c["name"] in WHALES:
                    raw[c["id"]] = target * WHALES[c["name"]][qi]
                else:
                    drift = 1 + 0.05 * np.sin(qi + base_weight[c["id"]] * 7)
                    # AI workloads take share within each customer type from
                    # late 2025 on — the cluster stage should find this, not
                    # be told about it. Enterprise ramps gently (each account
                    # stays under the 5% lane floor; the whales carry that
                    # story), mid-market ramps hard.
                    if c["sub"] == "AI Infrastructure":
                        ramp = ({7: 1.08, 8: 1.14, 9: 1.22} if ctype == "Enterprise"
                                else {7: 1.3, 8: 1.5, 9: 2.1})
                        ai_ramp = ramp.get(qi, 1.0)
                    else:
                        ai_ramp = 1.0
                    raw[c["id"]] = base_weight[c["id"]] * drift * ai_ramp
            whale_total = sum(v for cid, v in raw.items()
                              if next(x for x in members if x["id"] == cid)["name"] in WHALES)
            other_ids = [cid for cid in raw
                         if next(x for x in members if x["id"] == cid)["name"] not in WHALES]
            other_sum = sum(raw[cid] for cid in other_ids) or 1.0
            for cid in other_ids:
                raw[cid] = (target - whale_total) * raw[cid] / other_sum

            for c in members:
                net = raw[c["id"]]
                price = {"Enterprise": 2.05, "Mid-market": 1.45, "SMB": 0.55}[ctype] \
                    * (1 + 0.02 * qi / 10 + 0.10 * (qi >= 8) * (c["sub"] == "AI Infrastructure"))
                disc_rate = {"Enterprise": .04, "Mid-market": .02, "SMB": .0}[ctype]
                gross = net / (1 - disc_rate)
                units = gross / price
                rows.append(_txn(quarter, date, c, "Cloud", units, price,
                                 gross - net, net, COGS_RATIO["Cloud"][qi], geo_cycle))

        # ── Search: 30 advertisers share clicks; cpc uniform per quarter ────
        ads = [c for c in customers if c["product"] == "Search Ads"]
        seg = SEGMENTS["Search Ads"][qi]
        w = np.array([base_weight[c["id"]] * (1 + 0.04 * np.cos(qi + i)) for i, c in enumerate(ads)])
        w = w / w.sum()
        clicks_b = SEARCH_CLICKS[qi]
        for share, c in zip(w, ads):
            net = seg * share
            units = clicks_b * 1000 * share            # M clicks
            price = net / units                        # $M per M clicks == $/click
            rows.append(_txn(quarter, date, c, "Search Ads", units, price,
                             0.0, net, COGS_RATIO["Search Ads"][qi], geo_cycle))

        # ── Subscriptions + Devices: aggregate book-of-business rows ────────
        subs_split = {"Premium tier": .45, "Family tier": .30, "Student tier": .10,
                      "Enterprise seats": .15}
        for j, (tier, share) in enumerate(subs_split.items()):
            net = SEGMENTS["Subscriptions"][qi] * share
            units = SUBSCRIBERS[qi] * 1000 * share     # K subscribers
            rows.append(_txn(quarter, date,
                             {"id": f"S{j + 1:02d}", "name": tier, "type": "Consumer",
                              "sub": tier}, "Subscriptions", units, net / units,
                             0.0, net, COGS_RATIO["Subscriptions"][qi], geo_cycle))
        dev_split = {"Retail channel": .38, "Carrier channel": .30,
                     "Online store": .22, "Wholesale": .10}
        for j, (ch, share) in enumerate(dev_split.items()):
            net = SEGMENTS["Devices & Network"][qi] * share
            units = net / 0.42                          # ~$420 ASP
            rows.append(_txn(quarter, date,
                             {"id": f"D{j + 1:02d}", "name": ch, "type": "Channel",
                              "sub": "Hardware"}, "Devices & Network", units, 0.42,
                             0.0, net, COGS_RATIO["Devices & Network"][qi], geo_cycle))

    # Exact calibration: scale each (quarter, product) group so Σnet == target.
    by_key: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        by_key.setdefault((r["_q"], r["product"]), []).append(r)
    for (q, product), group in by_key.items():
        qi = QUARTERS.index(q)
        target = SEGMENTS[product][qi]
        k = target / sum(r["net_revenue"] for r in group)
        for r in group:
            r["net_revenue"] *= k
            r["unit_price"] *= k
            r["discount"] *= k
            r["cogs"] *= k
    return rows


_seq = 0


def _txn(quarter, date, c, product, units, price, discount, net, cogs_ratio, geo_cycle):
    global _seq
    _seq += 1
    geo = geo_cycle[_seq % 3] if product != "Cloud" else \
        ["Americas", "Americas", "EMEA", "APAC"][_seq % 4]
    return {
        "_q": quarter,
        "date": date, "txn_id": f"T{_seq:05d}", "customer_id": c["id"],
        "customer_name": c["name"], "customer_type": c["type"],
        "product": product, "sub_product": c["sub"], "geography": geo,
        "channel": "direct" if _seq % 3 else "partner",
        "units": units, "unit_price": price, "discount": discount,
        "net_revenue": net, "cogs": net * cogs_ratio,
    }


def build_summaries(txns: list[dict]) -> list[dict]:
    rows: list[dict] = []

    def add(period, metric, dim, segment, value):
        rows.append({"period": period, "metric": metric, "segment_dim": dim,
                     "segment": segment, "value": round(value, 2), "currency": "USD"})

    for qi, q in enumerate(QUARTERS):
        seg_vals = {s: SEGMENTS[s][qi] for s in SEGMENTS}
        revenue = sum(seg_vals.values())
        add(q, "Revenue", "total", "", revenue)
        for s, v in seg_vals.items():
            add(q, "Revenue", "product", s, v)
        for geo in ("Americas", "EMEA", "APAC"):
            add(q, "Revenue", "geography", geo,
                sum(v * GEO_WEIGHTS[s][geo] for s, v in seg_vals.items()))
        for ut, weights in USER_WEIGHTS.items():
            add(q, "Revenue", "user_type", ut,
                sum(seg_vals[s] * w for s, w in weights.items()))

        cogs_by_seg = {s: seg_vals[s] * COGS_RATIO[s][qi] for s in seg_vals}
        cogs = sum(cogs_by_seg.values())
        add(q, "COGS", "total", "", cogs)
        for s, v in cogs_by_seg.items():
            add(q, "COGS", "product", s, v)

        for line, series in LINES.items():
            add(q, line, "total", "", series[qi])

        gross = revenue - cogs
        oi = gross - LINES["R&D"][qi] - LINES["S&M"][qi] - LINES["G&A"][qi]
        add(q, "Gross profit", "total", "", gross)
        add(q, "Operating income", "total", "", oi)
        add(q, "Free cash flow", "total", "",
            LINES["Operating cash flow"][qi] - LINES["CapEx"][qi])
    return rows


def build_kpis() -> list[dict]:
    rows = []
    for qi, q in enumerate(QUARTERS):
        clicks = SEARCH_CLICKS[qi]
        cpc = SEGMENTS["Search Ads"][qi] / clicks / 1000 * CPC_FUDGE[qi]
        rows.append({"period": q, "segment": "Search Ads", "kpi_name": "paid_clicks",
                     "value": round(clicks, 2)})
        rows.append({"period": q, "segment": "Search Ads", "kpi_name": "cpc",
                     "value": round(cpc, 4)})
        subs = SUBSCRIBERS[qi]
        arpu = SEGMENTS["Subscriptions"][qi] / subs * ARPU_FUDGE[qi]
        rows.append({"period": q, "segment": "Subscriptions", "kpi_name": "subscribers",
                     "value": round(subs, 1)})
        rows.append({"period": q, "segment": "Subscriptions", "kpi_name": "arpu",
                     "value": round(arpu, 2)})
    return rows


DIMENSIONS = {
    "hierarchy": {
        "Revenue": ["product", "geography", "user_type"],
        "COGS": ["product"],
    },
    "product_tree": {
        "Cloud": ["AI Infrastructure", "Data Platform", "Productivity Suite"],
        "Search Ads": ["Brand ads", "Performance ads"],
        "Subscriptions": ["Premium tier", "Family tier", "Student tier", "Enterprise seats"],
        "Devices & Network": ["Hardware"],
    },
    "geo_tree": {"Americas": [], "EMEA": [], "APAC": []},
    "user_tree": {
        "Cloud": ["Enterprise", "Mid-market", "SMB"],
        "Search Ads": ["Advertiser"],
        "Subscriptions": ["Consumer"],
        "Devices & Network": ["Channel"],
    },
    "note": "Synthetic dataset for Auric Technologies (fictional). Transaction rows "
            "are calibrated to the reported summary totals; they are not real "
            "company transactions.",
}


def main() -> None:
    customers = roster()
    txns = build_transactions(customers)
    summaries = build_summaries(txns)
    kpis = build_kpis()

    with (OUT / "summaries.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["period", "metric", "segment_dim",
                                          "segment", "value", "currency"])
        w.writeheader()
        w.writerows(summaries)

    with (OUT / "transactions.csv").open("w", newline="") as f:
        cols = ["date", "txn_id", "customer_id", "customer_name", "customer_type",
                "product", "sub_product", "geography", "channel", "units",
                "unit_price", "discount", "net_revenue", "cogs"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in txns:
            w.writerow({c: (round(r[c], 4) if isinstance(r[c], float) else r[c])
                        for c in cols})

    with (OUT / "kpis.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["period", "segment", "kpi_name", "value"])
        w.writeheader()
        w.writerows(kpis)

    (OUT / "dimensions.json").write_text(json.dumps(DIMENSIONS, indent=2))

    # Self-check: totals reconcile, hero arcs are where the demo expects them.
    for qi, q in enumerate(QUARTERS):
        target = sum(SEGMENTS[s][qi] for s in SEGMENTS)
        got = sum(r["net_revenue"] for r in txns if r["_q"] == q)
        assert abs(got - target) < 0.5, f"{q}: txns {got} vs summary {target}"
    cloud_yoy = SEGMENTS["Cloud"][9] / SEGMENTS["Cloud"][5] - 1
    assert 0.80 < cloud_yoy < 0.84, cloud_yoy
    print(f"fixtures written to {OUT}")
    print(f"  {len(summaries)} summary rows · {len(txns)} transactions · {len(kpis)} kpis")
    print(f"  Cloud 2025-Q2→2026-Q2: {cloud_yoy:+.1%} · Revenue "
          f"{sum(SEGMENTS[s][9] for s in SEGMENTS) / sum(SEGMENTS[s][5] for s in SEGMENTS) - 1:+.1%}")


if __name__ == "__main__":
    main()

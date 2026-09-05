"""Load the repo's `data/given/` CSVs (SEC / product / geo / user) into the
same Dataset the engine already runs. No invented transactions — each
user-segment row becomes one book-of-business row so clustering and the
price/volume bridge have something real to chew on.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .normalize import Dataset, Reconciliation, reconcile
from . import periods

SEC_MAP = {
    "revenue": "Revenue",
    "cost_of_revenue": "COGS",
    "rd_expense": "R&D",
    "sm_expense": "S&M",
    "ga_expense": "G&A",
    "operating_income": "Operating income",
    "net_income": "Net income",
    "operating_cash_flow": "Operating cash flow",
    "capex": "CapEx",
    "free_cash_flow": "Free cash flow",
}

PRETTY = {
    "YouTube_Ads": "YouTube Ads",
    "enterprise_advertiser": "Enterprise advertiser",
    "smb_advertiser": "SMB advertiser",
    "agency_advertiser": "Agency advertiser",
    "paying_consumer": "Paying consumer",
    "streaming_consumer": "Streaming consumer",
    "free_consumer": "Free consumer",
}


def pretty(name: str) -> str:
    return PRETTY.get(name, name.replace("_", " "))


def _q_date(period: str) -> str:
    y, q = periods.parse(period)
    return f"{y}-{['02', '05', '08', '11'][q - 1]}-15"


def _add(rows: list[dict], period: str, metric: str, dim: str, segment: str, value: float) -> None:
    rows.append({
        "period": period, "metric": metric, "segment_dim": dim,
        "segment": segment, "value": float(value), "currency": "USD",
    })


def load_given(dir_path: str | Path, company: str = "Alphabet", name: str = "") -> Dataset:
    root = Path(dir_path)
    sec = pd.read_csv(root / "sec_metrics.csv")
    prod = pd.read_csv(root / "product_segments.csv")
    geo = pd.read_csv(root / "geography.csv")
    users = pd.read_csv(root / "user_segments.csv")

    # "Company" is the product-facing neutral label. Resolve it to the actual
    # source value in the uploaded rows before filtering; otherwise every row
    # would be removed from branded ledgers such as the included dataset.
    source_company = company
    if "company" in sec.columns:
        available = [str(value) for value in sec["company"].dropna().unique()]
        if source_company not in available and len(available) == 1:
            source_company = available[0]

    for df in (sec, prod, geo, users):
        if "company" in df.columns:
            df.drop(df[df.company.astype(str) != source_company].index, inplace=True)
        if df.empty:
            raise ValueError("the uploaded CSVs do not contain one shared company")

    summaries: list[dict] = []
    for r in sec.itertuples():
        for col, metric in SEC_MAP.items():
            _add(summaries, str(r.period), metric, "total", "", float(getattr(r, col)))

    for r in prod.itertuples():
        p = pretty(str(r.product))
        _add(summaries, str(r.period), "Revenue", "product", p, float(r.revenue))
        _add(summaries, str(r.period), "COGS", "product", p, float(r.direct_cost))

    geo_tot = geo.groupby(["period", "geography"], as_index=False).revenue.sum()
    for r in geo_tot.itertuples():
        _add(summaries, str(r.period), "Revenue", "geography", str(r.geography), float(r.revenue))

    user_tot = users.groupby(["period", "user_class"], as_index=False).revenue.sum()
    for r in user_tot.itertuples():
        _add(summaries, str(r.period), "Revenue", "user_type", pretty(str(r.user_class)), float(r.revenue))

    txns: list[dict] = []
    for i, r in enumerate(users.itertuples(), start=1):
        product = pretty(str(r.product))
        clicks = float(r.clicks) if pd.notna(r.clicks) else 0.0
        users_n = float(r.users) if pd.notna(r.users) else 0.0
        units = clicks / 1e6 if clicks else users_n / 1e6
        net = float(r.revenue)
        price = (net / units) if units else 0.0
        txns.append({
            "date": _q_date(str(r.period)),
            "txn_id": f"G{i:05d}",
            "customer_id": f"{r.product}:{r.geography}:{r.user_segment}",
            "customer_name": f"{pretty(str(r.user_segment))} · {r.geography}",
            "customer_type": pretty(str(r.user_class)),
            "product": product,
            "sub_product": pretty(str(r.user_segment)),
            "geography": str(r.geography),
            "channel": str(r.user_class),
            "units": units,
            "unit_price": price,
            "discount": 0.0,
            "net_revenue": net,
            "cogs": 0.0,
            "period": str(r.period),
        })

    # Scale each (period, product) book so Σ user-segment revenue == reported
    # product totals. The given files are internally consistent at the product
    # grain; user rows can drift by a few bps of float noise.
    txn_df = pd.DataFrame(txns)
    targets = {(str(r.period), pretty(str(r.product))): float(r.revenue) for r in prod.itertuples()}
    for key, group in txn_df.groupby(["period", "product"]):
        target = targets.get(key)
        got = float(group.net_revenue.sum())
        if target and got and abs(got - target) / max(abs(target), 1) > 1e-6:
            txn_df.loc[group.index, "net_revenue"] *= target / got
            txn_df.loc[group.index, "unit_price"] *= target / got
    txns = txn_df.to_dict("records")

    kpis: list[dict] = []
    search = users[users["product"].isin(["Search", "Search Ads"])]
    if not search.empty:
        g = search.groupby("period").agg(clicks=("clicks", "sum"), revenue=("revenue", "sum"))
        for period, row in g.iterrows():
            clicks_b = float(row.clicks) / 1e9  # billions of clicks, same spirit as fixtures
            kpis.append({"period": str(period), "segment": "Search", "kpi_name": "paid_clicks",
                         "value": round(clicks_b, 2)})
            cpc = (float(row.revenue) / (float(row.clicks) / 1e3)) if row.clicks else 0.0
            kpis.append({"period": str(period), "segment": "Search", "kpi_name": "cpc",
                         "value": round(cpc, 4)})

    dims = {
        "hierarchy": {
            "Revenue": ["product", "geography", "user_type"],
            "COGS": ["product"],
        },
        "note": f"{company} given CSVs — user-segment rows used as the transaction grain.",
    }

    ordered = periods.ordered([str(p) for p in sec.period.unique()])
    ds = Dataset(
        name=name or f"{company.lower()}-given",
        summaries=pd.DataFrame(summaries),
        transactions=pd.DataFrame(txns),
        dims=dims,
        kpis=pd.DataFrame(kpis) if kpis else None,
        periods=ordered,
        reconciliation=Reconciliation(ok=True),
    )
    ds.reconciliation = reconcile(ds)
    return ds

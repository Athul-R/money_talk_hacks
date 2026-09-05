"""Stage 3b: the deterministic driver bridge.

For a branch backed by transactions the delta decomposes exactly:

    retained customers (present both periods, effective price p = net/units):
        price  = Σ units_a · (p_b − p_a)
        volume = Σ p_a · (units_b − units_a)
        mix    = Σ (units_b − units_a) · (p_b − p_a)      (interaction)
    customer = Σ net_b (new customers) − Σ net_a (churned customers)
    fx / geo = 0 unless the dataset carries rates / multi-currency rows
    other    = rounding residual (asserted ≈ 0 in tests)

The bridge SUMS TO THE DELTA by construction — no estimation, no model.
KPI reconciliation checks the operational identity (e.g. (1+clicks)(1+cpc)−1)
against the reported growth and reports the residual instead of hiding it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .metric_graph import KPI_IDENTITIES
from .normalize import Dataset


@dataclass
class Bridge:
    price: float = 0.0
    volume: float = 0.0
    mix: float = 0.0
    customer: float = 0.0
    geo: float = 0.0
    fx: float = 0.0
    other: float = 0.0
    top_driver: str = ""
    per_customer: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        parts = {
            "price": round(self.price, 2), "volume": round(self.volume, 2),
            "mix": round(self.mix, 2), "customer": round(self.customer, 2),
            "geo": round(self.geo, 2), "fx": round(self.fx, 2),
            "other": round(self.other, 2),
        }
        return {**parts, "top_driver": self.top_driver}

    def total(self) -> float:
        return self.price + self.volume + self.mix + self.customer + self.geo + self.fx + self.other


def _per_customer_frame(txns: pd.DataFrame) -> pd.DataFrame:
    """One row per customer: units, net revenue, effective net price."""
    g = txns.groupby("customer_id").agg(
        customer_name=("customer_name", "first"),
        customer_type=("customer_type", "first"),
        sub_product=("sub_product", "first"),
        geography=("geography", "first"),
        units=("units", "sum"),
        net_revenue=("net_revenue", "sum"),
    )
    g["price"] = g.net_revenue / g.units.where(g.units != 0, 1.0)
    return g


def bridge(txns_a: pd.DataFrame, txns_b: pd.DataFrame) -> Bridge:
    """Exact price/volume/mix/customer decomposition of Σnet_b − Σnet_a."""
    a = _per_customer_frame(txns_a)
    b = _per_customer_frame(txns_b)

    retained = a.index.intersection(b.index)
    new = b.index.difference(a.index)
    churned = a.index.difference(b.index)

    out = Bridge()
    per_customer: list[dict] = []

    for cid in retained:
        ua, ub = float(a.units[cid]), float(b.units[cid])
        pa, pb = float(a.price[cid]), float(b.price[cid])
        price = ua * (pb - pa)
        volume = pa * (ub - ua)
        mix = (ub - ua) * (pb - pa)
        out.price += price
        out.volume += volume
        out.mix += mix
        per_customer.append({
            "customer_id": str(cid),
            "customer_name": str(b.customer_name[cid]),
            "customer_type": str(b.customer_type[cid]),
            "sub_product": str(b.sub_product[cid]),
            "geography": str(b.geography[cid]),
            "value_a": round(float(a.net_revenue[cid]), 2),
            "value_b": round(float(b.net_revenue[cid]), 2),
            "delta": round(float(b.net_revenue[cid] - a.net_revenue[cid]), 2),
        })

    for cid in new:
        out.customer += float(b.net_revenue[cid])
        per_customer.append({
            "customer_id": str(cid), "customer_name": str(b.customer_name[cid]),
            "customer_type": str(b.customer_type[cid]),
            "sub_product": str(b.sub_product[cid]), "geography": str(b.geography[cid]),
            "value_a": 0.0, "value_b": round(float(b.net_revenue[cid]), 2),
            "delta": round(float(b.net_revenue[cid]), 2),
        })
    for cid in churned:
        out.customer -= float(a.net_revenue[cid])
        per_customer.append({
            "customer_id": str(cid), "customer_name": str(a.customer_name[cid]),
            "customer_type": str(a.customer_type[cid]),
            "sub_product": str(a.sub_product[cid]), "geography": str(a.geography[cid]),
            "value_a": round(float(a.net_revenue[cid]), 2), "value_b": 0.0,
            "delta": round(-float(a.net_revenue[cid]), 2),
        })

    # Residual = float noise only; the identity above is exact.
    delta = float(b.net_revenue.sum() - a.net_revenue.sum())
    out.other = delta - (out.price + out.volume + out.mix + out.customer)

    magnitudes = {
        "volume": abs(out.volume), "price": abs(out.price), "mix": abs(out.mix),
        "customer": abs(out.customer),
    }
    out.top_driver = max(magnitudes, key=lambda k: magnitudes[k]) if any(magnitudes.values()) else ""
    out.per_customer = sorted(per_customer, key=lambda r: -abs(r["delta"]))
    return out


def kpi_reconciliation(ds: Dataset, segment: str, period_a: str, period_b: str) -> dict | None:
    """(1 + Δvolume%)(1 + Δprice%) − 1 vs the reported growth, residual shown."""
    identity = KPI_IDENTITIES.get(segment)
    if identity is None:
        return None
    vol_name, price_name = identity
    vol = ds.kpi_series(segment, vol_name)
    price = ds.kpi_series(segment, price_name)
    if period_a not in vol or period_b not in vol or period_a not in price or period_b not in price:
        return None

    vol_pct = (vol[period_b] / vol[period_a] - 1) * 100
    price_pct = (price[period_b] / price[period_a] - 1) * 100
    implied_pct = ((1 + vol_pct / 100) * (1 + price_pct / 100) - 1) * 100

    reported = ds.segments("Revenue", "product", period_a).get(segment)
    reported_b = ds.segments("Revenue", "product", period_b).get(segment)
    if not reported or reported_b is None:
        return None
    reported_pct = (reported_b / reported - 1) * 100

    return {
        "identity": f"{vol_name} × {price_name}",
        "volume_kpi": vol_name, "volume_pct": round(vol_pct, 1),
        "price_kpi": price_name, "price_pct": round(price_pct, 1),
        "implied_pct": round(implied_pct, 1),
        "reported_pct": round(reported_pct, 1),
        "residual": round(reported_pct - implied_pct, 1),
    }


def line_item_bridge(items_a: dict[str, tuple[float, float]],
                     items_b: dict[str, tuple[float, float]]) -> list[dict]:
    """Signed contribution of each formula component to a computed metric's Δ.
    ΔOperating income = ΔRevenue − ΔCOGS − … — exact, ranked by |contribution|."""
    out = []
    for name, (va, sign) in items_a.items():
        vb = items_b.get(name, (va, sign))[0]
        out.append({
            "name": name, "sign": sign,
            "value_a": round(va, 2), "value_b": round(vb, 2),
            "delta": round(vb - va, 2),
            "contribution": round(sign * (vb - va), 2),
        })
    return sorted(out, key=lambda r: -abs(r["contribution"]))

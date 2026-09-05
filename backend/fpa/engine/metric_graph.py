"""The metric graph: financial identities the engine understands, so a metric
is never an isolated number. Computed metrics fall back to their formula when
the summaries lack a reported row, and every formula doubles as a deterministic
line-item bridge for the drill (ΔOperating income = ΔRevenue − ΔCOGS − …).

Operational identities (revenue ≈ clicks × CPC, ≈ subscribers × ARPU) live here
too; the drivers stage uses them for KPI reconciliation.
"""

from __future__ import annotations

from .normalize import Dataset

# metric -> [(component, sign)]
IDENTITIES: dict[str, list[tuple[str, float]]] = {
    "Gross profit": [("Revenue", +1), ("COGS", -1)],
    "Operating income": [
        ("Revenue", +1), ("COGS", -1), ("R&D", -1), ("S&M", -1), ("G&A", -1),
    ],
    "Net income": [
        ("Operating income", +1), ("Other income", +1), ("Interest", -1), ("Taxes", -1),
    ],
    "Operating cash flow": [("Net income", +1), ("Non-cash adjustments", +1)],
    "Free cash flow": [("Operating cash flow", +1), ("CapEx", -1)],
}

# segment -> [(kpi_volume, kpi_price)] — revenue ≈ volume × price identities.
KPI_IDENTITIES: dict[str, tuple[str, str]] = {
    "Search Ads": ("paid_clicks", "cpc"),
    "Search": ("paid_clicks", "cpc"),
    "Subscriptions": ("subscribers", "arpu"),
}


def value(ds: Dataset, metric: str, period: str) -> float | None:
    """Reported total if present, else computed through the identity."""
    reported = ds.total(metric, period)
    if reported is not None:
        return reported
    formula = IDENTITIES.get(metric)
    if not formula:
        return None
    total = 0.0
    for component, sign in formula:
        v = value(ds, component, period)
        if v is None:
            return None
        total += sign * v
    return total


def line_items(ds: Dataset, metric: str, period: str) -> dict[str, tuple[float, float]]:
    """Formula components for one period: name -> (raw value, sign)."""
    out: dict[str, tuple[float, float]] = {}
    for component, sign in IDENTITIES.get(metric, []):
        v = value(ds, component, period)
        if v is not None:
            out[component] = (v, sign)
    return out


def is_computed(metric: str) -> bool:
    return metric in IDENTITIES


def identity_residual(ds: Dataset, metric: str, period: str) -> float | None:
    """Reported − computed, when both exist. Small residuals are normal
    (non-cash catch-alls); large ones are a data-quality flag."""
    reported = ds.total(metric, period)
    formula = IDENTITIES.get(metric)
    if reported is None or not formula:
        return None
    computed = 0.0
    for component, sign in formula:
        v = value(ds, component, period)
        if v is None:
            return None
        computed += sign * v
    return reported - computed

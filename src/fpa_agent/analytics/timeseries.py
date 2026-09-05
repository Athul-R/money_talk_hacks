"""Time-series stats: rolling mean/std and Z-scores for metric history."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class SeriesStat:
    metric: str
    period: str
    value: float
    prior_value: float | None
    delta: float | None
    pct_change: float | None
    rolling_mean: float | None
    rolling_std: float | None
    z_score: float | None
    is_material: bool
    history_n: int


def _period_sort_key(period: str) -> tuple[int, int]:
    # Expect YYYY-Qn
    year, q = period.split("-Q")
    return int(year), int(q)


def sort_periods(periods: list[str]) -> list[str]:
    return sorted(periods, key=_period_sort_key)


def zscore_series(
    history: pd.Series,
    *,
    window: int = 8,
    material_z: float = 1.5,
    compare_period: str | None = None,
) -> SeriesStat:
    """Compute delta vs prior period and Z-score vs trailing window (excl. current).

    If compare_period is set, delta/pct use that period instead of the immediate prior.
    Z-score still uses the trailing historical window excluding the current period.
    """
    history = history.dropna().astype(float)
    ordered = sort_periods(list(history.index.astype(str)))
    history = history.reindex(ordered)
    if history.empty:
        raise ValueError("empty history")

    period = str(history.index[-1])
    value = float(history.iloc[-1])

    if compare_period is not None and compare_period in history.index:
        prior = float(history.loc[compare_period])
    else:
        prior = float(history.iloc[-2]) if len(history) >= 2 else None

    delta = (value - prior) if prior is not None else None
    pct = (delta / prior) if prior not in (None, 0.0) else None

    trail = history.iloc[:-1].tail(window)
    if len(trail) >= 2:
        mu = float(trail.mean())
        sigma = float(trail.std(ddof=1))
        z = (value - mu) / sigma if sigma > 1e-12 else 0.0
    else:
        mu, sigma, z = None, None, None

    material = False
    if z is not None and abs(z) >= material_z:
        material = True
    if pct is not None and abs(pct) >= 0.05 and (delta is not None and abs(delta) > 0):
        material = material or abs(pct) >= 0.05

    return SeriesStat(
        metric=str(history.name or "metric"),
        period=period,
        value=value,
        prior_value=prior,
        delta=delta,
        pct_change=pct,
        rolling_mean=mu,
        rolling_std=sigma,
        z_score=z,
        is_material=material,
        history_n=len(history),
    )


def build_metric_history(
    df: pd.DataFrame,
    *,
    value_col: str,
    period_col: str = "period",
    filters: dict[str, str] | None = None,
) -> pd.Series:
    """Aggregate a filtered slice into a period → value series."""
    view = df
    if filters:
        for k, v in filters.items():
            if k in view.columns:
                view = view[view[k] == v]
    if view.empty:
        return pd.Series(dtype=float, name=value_col)

    grouped = view.groupby(period_col, as_index=True)[value_col].sum()
    ordered = sort_periods(list(grouped.index.astype(str)))
    grouped = grouped.reindex(ordered)
    grouped.name = value_col
    return grouped


def kpi_histories(
    df: pd.DataFrame,
    kpi_cols: tuple[str, ...],
    *,
    period_col: str = "period",
    filters: dict[str, str] | None = None,
    weight_col: str | None = "revenue",
) -> dict[str, pd.Series]:
    """Build histories for rate KPIs (weighted where sensible) and volume KPIs (sum)."""
    view = df
    if filters:
        for k, v in filters.items():
            if k in view.columns:
                view = view[view[k] == v]

    out: dict[str, pd.Series] = {}
    volume_like = {"impressions", "clicks", "users", "revenue"}
    for col in kpi_cols:
        if col not in view.columns:
            continue
        if col in volume_like or weight_col is None or weight_col not in view.columns:
            s = view.groupby(period_col)[col].sum()
        else:
            # revenue-weighted average for rates
            tmp = view.dropna(subset=[col, weight_col]).copy()
            if tmp.empty:
                continue
            tmp["_w"] = tmp[weight_col] * tmp[col]
            num = tmp.groupby(period_col)["_w"].sum()
            den = tmp.groupby(period_col)[weight_col].sum().replace(0, np.nan)
            s = num / den
        ordered = sort_periods(list(s.index.astype(str)))
        s = s.reindex(ordered)
        s.name = col
        out[col] = s
    return out

"""Stage 3a arithmetic: deltas, growth series and z-scores.

The z-score is computed on the GROWTH RATE, not the level: for a run comparing
period_a → period_b with gap k quarters, the sample series is g(t) = v(t)/v(t−k) − 1
for every period with a t−k ancestor, and the current growth is scored against
the trailing 4–8 samples before period_b. A YoY gap (k=4) is inherently
seasonality-adjusted; sub-year gaps note the caveat instead of pretending.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import periods

TRAILING_MIN = 4
TRAILING_MAX = 8


@dataclass
class DeltaStats:
    value_a: float
    value_b: float
    delta_abs: float
    delta_pct: float | None
    zscore: float | None
    trailing_mean_pct: float | None
    trailing_std_pct: float | None
    trailing_n: int
    seasonality: str
    growth_series: list[dict]  # [{period, growth_pct}] including the current one
    level_series: list[dict]   # [{period, value}] the drawer's time-series line

    def as_dict(self) -> dict:
        return {
            "value_a": round(self.value_a, 2),
            "value_b": round(self.value_b, 2),
            "delta_abs": round(self.delta_abs, 2),
            "delta_pct": None if self.delta_pct is None else round(self.delta_pct, 1),
            "zscore": None if self.zscore is None else round(self.zscore, 2),
            "trailing_mean_pct": None if self.trailing_mean_pct is None else round(self.trailing_mean_pct, 1),
            "trailing_std_pct": None if self.trailing_std_pct is None else round(self.trailing_std_pct, 1),
            "trailing_n": self.trailing_n,
            "seasonality": self.seasonality,
            "growth_series": self.growth_series,
            "level_series": self.level_series,
        }


def growth_streak(series: dict[str, float], upto: str, threshold_pct: float, k: int = 4) -> int:
    """Consecutive periods (ending at `upto`) with growth above threshold —
    the "3rd consecutive quarter of Cloud > 20% growth" fact, computed, not felt."""
    idx = periods.index(upto)
    streak = 0
    while True:
        cur, prior = periods.label(idx), periods.label(idx - k)
        if cur not in series or prior not in series or series[prior] == 0:
            break
        growth = (series[cur] / series[prior] - 1) * 100
        if growth <= threshold_pct:
            break
        streak += 1
        idx -= 1
    return streak


def delta_stats(series: dict[str, float], period_a: str, period_b: str) -> DeltaStats:
    """All the 3a numbers for one branch. `series` is period -> value."""
    k = periods.gap(period_a, period_b)
    if k <= 0:
        raise ValueError(f"period_b {period_b} must come after period_a {period_a}")

    value_a = series.get(period_a, 0.0)
    value_b = series.get(period_b, 0.0)
    delta_abs = value_b - value_a
    delta_pct = (delta_abs / abs(value_a) * 100) if value_a else None

    ordered = periods.ordered(list(series.keys()))
    level_series = [{"period": p, "value": round(series[p], 2)} for p in ordered]

    # Growth samples at gap k, oldest → newest.
    growth: list[tuple[str, float]] = []
    for p in ordered:
        prior = periods.shift(p, -k)
        if prior in series and series[prior]:
            growth.append((p, (series[p] / series[prior] - 1) * 100))

    growth_series = [{"period": p, "growth_pct": round(g, 1)} for p, g in growth]

    trailing = [g for p, g in growth if periods.index(p) < periods.index(period_b)]
    trailing = trailing[-TRAILING_MAX:]

    zscore = mean = std = None
    if len(trailing) >= TRAILING_MIN and delta_pct is not None:
        mean = sum(trailing) / len(trailing)
        var = sum((g - mean) ** 2 for g in trailing) / (len(trailing) - 1)
        std = var ** 0.5
        if std > 1e-9:
            zscore = (delta_pct - mean) / std

    seasonality = (
        "YoY comparison — seasonality-adjusted by construction" if k % 4 == 0
        else ("trailing window ≥ 8 periods — same-quarter adjusted" if len(trailing) >= 8
              else "sub-year gap with a short history — seasonality not adjusted")
    )

    return DeltaStats(
        value_a=value_a, value_b=value_b, delta_abs=delta_abs, delta_pct=delta_pct,
        zscore=zscore, trailing_mean_pct=mean, trailing_std_pct=std,
        trailing_n=len(trailing), seasonality=seasonality,
        growth_series=growth_series, level_series=level_series,
    )

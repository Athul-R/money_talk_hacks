"""Growth z-scores and streaks — the 3a arithmetic."""

import pytest

from fpa.engine.timeseries import delta_stats, growth_streak


def _series(values: list[float], start_year: int = 2024) -> dict[str, float]:
    out = {}
    for i, v in enumerate(values):
        out[f"{start_year + i // 4}-Q{i % 4 + 1}"] = v
    return out


def test_delta_and_growth_are_exact():
    s = _series([100, 100, 100, 100, 110, 120, 130, 140, 150, 180])
    st = delta_stats(s, "2025-Q2", "2026-Q2")
    assert st.value_a == 120 and st.value_b == 180
    assert st.delta_abs == 60
    assert st.delta_pct == pytest.approx(50.0)


def test_zscore_flags_the_outlier():
    # trailing YoY growths ~10%, current +50% → large positive z
    s = _series([100, 100, 100, 100, 110, 110, 110, 111, 121, 165])
    st = delta_stats(s, "2025-Q2", "2026-Q2")
    assert st.trailing_n >= 4
    assert st.zscore is not None and st.zscore > 2


def test_yoy_gap_marks_seasonality_adjusted():
    s = _series([100] * 10)
    st = delta_stats(s, "2025-Q2", "2026-Q2")
    assert "seasonality-adjusted" in st.seasonality


def test_backwards_periods_raise():
    s = _series([100] * 10)
    with pytest.raises(ValueError):
        delta_stats(s, "2026-Q2", "2025-Q2")


def test_growth_streak_counts_consecutive_only():
    # YoY growths: 25Q1 +10%, 25Q2 +30%, 25Q3 +15%, 25Q4 +25%, 26Q1 +25%, 26Q2 +40%
    s = _series([100, 100, 100, 100, 110, 130, 115, 125, 137.5, 182])
    assert growth_streak(s, "2026-Q2", 20.0, k=4) == 3   # Q4'25, Q1'26, Q2'26... 
    # broken by 25Q3's +15%:
    assert growth_streak(s, "2025-Q3", 20.0, k=4) == 0

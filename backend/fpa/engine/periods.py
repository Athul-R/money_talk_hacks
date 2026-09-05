"""Quarter arithmetic. Periods are strings like "2026-Q2"; internally they map
to a monotone index (year*4 + quarter) so gaps and trailing windows are integer
math, never date math."""

from __future__ import annotations

import re

_PERIOD_RE = re.compile(r"^(\d{4})-Q([1-4])$")


def parse(period: str) -> tuple[int, int]:
    m = _PERIOD_RE.match(period.strip())
    if not m:
        raise ValueError(f"bad period {period!r}, expected e.g. 2026-Q2")
    return int(m.group(1)), int(m.group(2))


def index(period: str) -> int:
    y, q = parse(period)
    return y * 4 + (q - 1)


def label(idx: int) -> str:
    return f"{idx // 4}-Q{idx % 4 + 1}"


def gap(period_a: str, period_b: str) -> int:
    """Number of quarters from a to b (4 = year over year)."""
    return index(period_b) - index(period_a)


def ordered(periods: list[str]) -> list[str]:
    return sorted(set(periods), key=index)


def shift(period: str, quarters: int) -> str:
    return label(index(period) + quarters)


def same_quarter(period_a: str, period_b: str) -> bool:
    return parse(period_a)[1] == parse(period_b)[1]

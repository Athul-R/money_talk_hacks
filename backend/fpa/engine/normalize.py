"""Stage 1 of every run: load the uploaded CSVs, validate their shape, and
reconcile transaction-level rows against reported summary totals.

Values are USD millions throughout. Data is given, not generated — this module
never fabricates a row; it only checks that what was uploaded is coherent
enough to attribute against (control totals within tolerance).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import periods

SUMMARY_COLS = ["period", "metric", "segment_dim", "segment", "value", "currency"]
TXN_COLS = [
    "date", "txn_id", "customer_id", "customer_name", "customer_type",
    "product", "sub_product", "geography", "channel",
    "units", "unit_price", "discount", "net_revenue", "cogs",
]
KPI_COLS = ["period", "segment", "kpi_name", "value"]

RECONCILE_TOLERANCE = 0.005  # 0.5% of the reported total


@dataclass
class Reconciliation:
    ok: bool
    checks: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "checks": self.checks}


@dataclass
class Dataset:
    """Everything one run reads. summaries/transactions/kpis are DataFrames,
    dims is the parsed dimensions.json ontology."""

    name: str
    summaries: pd.DataFrame
    transactions: pd.DataFrame
    dims: dict
    kpis: pd.DataFrame | None
    periods: list[str]
    reconciliation: Reconciliation

    # ── summary lookups ──────────────────────────────────────────────────

    def total(self, metric: str, period: str) -> float | None:
        df = self.summaries
        rows = df[(df.metric == metric) & (df.segment_dim == "total") & (df.period == period)]
        return float(rows.value.iloc[0]) if len(rows) else None

    def segments(self, metric: str, dim: str, period: str) -> dict[str, float]:
        df = self.summaries
        rows = df[(df.metric == metric) & (df.segment_dim == dim) & (df.period == period)]
        return {str(r.segment): float(r.value) for r in rows.itertuples()}

    def series(self, metric: str, dim: str = "total", segment: str = "") -> dict[str, float]:
        """period -> value across every period in the dataset."""
        df = self.summaries
        rows = df[(df.metric == metric) & (df.segment_dim == dim)]
        if dim != "total":
            rows = rows[rows.segment == segment]
        return {str(r.period): float(r.value) for r in rows.itertuples()}

    def axes_for(self, metric: str) -> list[str]:
        """Decomposition axes the summaries actually carry for this metric."""
        wanted = self.dims.get("hierarchy", {}).get(metric, [])
        df = self.summaries
        present = set(df[df.metric == metric].segment_dim.unique()) - {"total"}
        return [a for a in wanted if a in present]

    # ── transaction lookups ──────────────────────────────────────────────

    def txns(self, period: str, **filters: str) -> pd.DataFrame:
        df = self.transactions
        out = df[df.period == period]
        for col, val in filters.items():
            out = out[out[col] == val]
        return out

    def txn_series(self, **filters: str) -> dict[str, float]:
        """period -> Σ net_revenue for the filtered transaction subset."""
        df = self.transactions
        for col, val in filters.items():
            df = df[df[col] == val]
        return {str(p): float(v) for p, v in df.groupby("period").net_revenue.sum().items()}

    def kpi_series(self, segment: str, kpi_name: str) -> dict[str, float]:
        if self.kpis is None:
            return {}
        df = self.kpis
        rows = df[(df.segment == segment) & (df.kpi_name == kpi_name)]
        return {str(r.period): float(r.value) for r in rows.itertuples()}


def _quarter_of(date: str) -> str:
    ts = pd.Timestamp(date)
    return f"{ts.year}-Q{ts.quarter}"


def _require(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name} is missing columns: {missing}")


def load(dir_path: str | Path, name: str = "") -> Dataset:
    """Load summaries.csv / transactions.csv / dimensions.json (+ kpis.csv)."""
    root = Path(dir_path)
    summaries = pd.read_csv(root / "summaries.csv")
    transactions = pd.read_csv(root / "transactions.csv")
    dims = json.loads((root / "dimensions.json").read_text())
    kpis = pd.read_csv(root / "kpis.csv") if (root / "kpis.csv").exists() else None

    _require(summaries, SUMMARY_COLS, "summaries.csv")
    _require(transactions, TXN_COLS, "transactions.csv")
    if kpis is not None:
        _require(kpis, KPI_COLS, "kpis.csv")

    for p in summaries.period.unique():
        periods.parse(str(p))  # raises on malformed periods

    # Transactions carry dates; derive the quarter each row belongs to.
    transactions = transactions.copy()
    transactions["period"] = transactions["date"].map(_quarter_of)

    ordered = periods.ordered([str(p) for p in summaries.period.unique()])
    ds = Dataset(
        name=name or root.name,
        summaries=summaries,
        transactions=transactions,
        dims=dims,
        kpis=kpis,
        periods=ordered,
        reconciliation=Reconciliation(ok=True),
    )
    ds.reconciliation = reconcile(ds)
    return ds


def reconcile(ds: Dataset) -> Reconciliation:
    """Control totals: transactions must roll up to the reported summaries.
    Two checks per period — the Revenue total, and each product segment."""
    checks: list[dict] = []
    ok = True

    txn_by_period = ds.transactions.groupby("period").net_revenue.sum()
    for period in ds.periods:
        reported = ds.total("Revenue", period)
        if reported is None:
            continue
        computed = float(txn_by_period.get(period, 0.0))
        diff = abs(computed - reported)
        passed = diff <= RECONCILE_TOLERANCE * abs(reported)
        ok = ok and passed
        checks.append({
            "period": period, "scope": "Revenue total",
            "reported": round(reported, 2), "computed": round(computed, 2),
            "ok": passed,
        })

    txn_by_seg = ds.transactions.groupby(["period", "product"]).net_revenue.sum()
    for period in ds.periods:
        for segment, reported in ds.segments("Revenue", "product", period).items():
            computed = float(txn_by_seg.get((period, segment), 0.0))
            passed = abs(computed - reported) <= RECONCILE_TOLERANCE * max(abs(reported), 1.0)
            ok = ok and passed
            checks.append({
                "period": period, "scope": f"Revenue · {segment}",
                "reported": round(reported, 2), "computed": round(computed, 2),
                "ok": passed,
            })

    return Reconciliation(ok=ok, checks=checks)

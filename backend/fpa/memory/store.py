"""Recall + write for company memory rows.

kinds: seasonality | normal_range | recurring_driver | concentration |
       known_event | anomaly | explanation

Promotion mirrors the scheduler's soft → hard preference ladder: an anomaly
observed again in a later run stops being an anomaly and becomes a
recurring_driver, with both run ids kept as evidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..engine import periods
from ..engine.normalize import Dataset
from ..engine.timeseries import growth_streak

STREAK_THRESHOLD_PCT = 20.0
ANOMALY_Z = 2.5
CONCENTRATION_FLAG = 0.35
MEMORY_MAX_DEPTH = 1  # customer-level rows would drown the useful patterns


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """In-memory row set with a pluggable persistence hook. LocalStore and the
    Supabase writer both consume the same row dicts."""

    def __init__(self, rows: list[dict] | None = None):
        self.rows: list[dict] = rows or []

    def for_company(self, company_id: str) -> list[dict]:
        return [r for r in self.rows if r["company_id"] == company_id]

    def get(self, company_id: str, kind: str, key: str) -> dict | None:
        for r in self.rows:
            if r["company_id"] == company_id and r["kind"] == kind and r["key"] == key:
                return r
        return None

    def upsert(self, company_id: str, kind: str, key: str, value: dict,
               run_id: str) -> dict:
        row = self.get(company_id, kind, key)
        if row is None:
            row = {
                "id": str(uuid.uuid4()), "company_id": company_id,
                "kind": kind, "key": key, "value": value,
                "evidence_run_ids": [run_id], "updated_at": _now(),
            }
            self.rows.append(row)
        else:
            row["value"] = value
            if run_id not in row["evidence_run_ids"]:
                row["evidence_run_ids"].append(run_id)
            row["updated_at"] = _now()
        return row

    def promote(self, row: dict, run_id: str) -> dict:
        """anomaly → recurring_driver, evidence preserved."""
        row["kind"] = "recurring_driver"
        row["value"] = {**row["value"], "promoted_from": "anomaly"}
        if run_id not in row["evidence_run_ids"]:
            row["evidence_run_ids"].append(run_id)
        row["updated_at"] = _now()
        return row


def humanize(row: dict) -> str:
    """One plain sentence per memory row — what the explain pip renders."""
    v = row["value"]
    kind, key = row["kind"], row["key"]
    if kind == "recurring_driver" and "streak" in v:
        return (f"{v['segment']} growth has exceeded {v['threshold_pct']:.0f}% for "
                f"{v['streak']} consecutive periods")
    if kind == "recurring_driver" and v.get("promoted_from") == "anomaly":
        return f"{v.get('note', key)} — seen in {len(row['evidence_run_ids'])} runs, now treated as recurring"
    if kind == "normal_range":
        return (f"{v['segment']} normally grows {v['mean_pct']:+.0f}% ± {v['std_pct']:.0f}pp "
                f"({v['n']} periods)")
    if kind == "concentration":
        return (f"top {v['top_n']} {v['segment']} accounts have carried "
                f"{v['share']:.0%} of segment growth")
    if kind == "seasonality":
        return f"{v['segment']} shows a Q{v['quarter']} seasonal lift (~{v['lift_pct']:+.0f}pp)"
    if kind == "anomaly":
        return v.get("note", key)
    if kind == "explanation":
        return (f"{v['metric']} Δ for {v['period_a']} → {v['period_b']} was explained "
                f"in a prior run ({v.get('headline', '')})".rstrip("( )"))
    if kind == "known_event":
        return v.get("note", key)
    return key


def recall(store: MemoryStore, company_id: str, metric: str,
           segment_names: list[str]) -> list[dict]:
    """Rows relevant to this run: metric-wide explanations plus anything keyed
    to a segment the router is about to rank. Pure filtering — microseconds."""
    hits = []
    names = {metric, *segment_names}
    for row in store.for_company(company_id):
        v = row["value"]
        related = (
            v.get("segment") in names
            or v.get("metric") in names
            or any(n.lower() in row["key"].lower() for n in names)
        )
        if related:
            hits.append({**row, "text": humanize(row)})
    return hits


def learn(store: MemoryStore, company_id: str, run_id: str, ds: Dataset,
          metric: str, period_a: str, period_b: str,
          branches: list[dict], headline: str) -> dict:
    """The write path, run once per completed run. Deterministic compilation of
    this run's evidence into rows; returns {learned, promoted} for the event."""
    learned: list[dict] = []
    promoted: list[dict] = []

    def note(row: dict) -> None:
        learned.append({"kind": row["kind"], "key": row["key"], "text": humanize(row)})

    top_level = [b for b in branches if b["depth"] == 0]

    for b in top_level:
        seg = b["name"]
        series = ds.series(metric, b["dimension"], seg) if b["dimension"] != "line_item" \
            else ds.series(seg, "total")
        if not series:
            continue

        # normal_range: trailing growth stats become the next run's context.
        ev = b.get("evidence", {})
        if ev.get("trailing_mean_pct") is not None:
            note(store.upsert(company_id, "normal_range", f"growth:{seg}", {
                "segment": seg, "metric": metric,
                "mean_pct": ev["trailing_mean_pct"],
                "std_pct": ev.get("trailing_std_pct") or 0.0,
                "n": ev.get("trailing_n", 0),
            }, run_id))

        # recurring_driver: growth streaks above the threshold.
        gap = periods.gap(period_a, period_b)
        streak = growth_streak(series, period_b, STREAK_THRESHOLD_PCT, k=gap)
        if streak >= 2:
            note(store.upsert(company_id, "recurring_driver", f"growth_streak:{seg}", {
                "segment": seg, "metric": metric,
                "streak": streak, "threshold_pct": STREAK_THRESHOLD_PCT,
            }, run_id))

        # seasonality: does one quarter systematically outgrow the rest QoQ?
        season = _seasonal_lift(series)
        if season is not None:
            note(store.upsert(company_id, "seasonality", f"season:{seg}", {
                "segment": seg, **season,
            }, run_id))

    # concentration + anomaly promotion from any shallow branch that measured it.
    for b in branches:
        if b["depth"] > MEMORY_MAX_DEPTH:
            continue
        conc = (b.get("evidence") or {}).get("concentration")
        if conc and conc.get("top_n_share"):
            seg = b["name"]
            note(store.upsert(company_id, "concentration", f"concentration:{seg}", {
                "segment": seg, "top_n": conc["top_n"], "share": conc["top_n_share"],
            }, run_id))
            if conc["top_n_share"] >= CONCENTRATION_FLAG:
                key = f"concentration_risk:{seg}"
                existing = store.get(company_id, "anomaly", key)
                if existing and run_id not in existing["evidence_run_ids"]:
                    promoted_row = store.promote(existing, run_id)
                    promoted.append({"kind": "recurring_driver", "key": key,
                                     "text": humanize(promoted_row)})
                elif existing is None:
                    note(store.upsert(company_id, "anomaly", key, {
                        "segment": seg,
                        "note": (f"{seg} growth concentrated: top {conc['top_n']} accounts "
                                 f"= {conc['top_n_share']:.0%} of the move"),
                    }, run_id))

        z = b.get("zscore")
        if z is not None and abs(z) >= ANOMALY_Z:
            key = f"zscore:{metric}:{b['name']}"
            existing = store.get(company_id, "anomaly", key)
            if existing and run_id not in existing["evidence_run_ids"]:
                promoted.append({"kind": "recurring_driver", "key": key,
                                 "text": humanize(store.promote(existing, run_id))})
            elif existing is None:
                note(store.upsert(company_id, "anomaly", key, {
                    "segment": b["name"], "metric": metric,
                    "note": f"{b['name']} moved {abs(z):.1f}σ outside its trailing band",
                }, run_id))

    # the explanation itself — later runs cite it instead of re-drilling.
    note(store.upsert(company_id, "explanation",
                      f"run:{metric}:{period_a}:{period_b}", {
                          "metric": metric, "period_a": period_a, "period_b": period_b,
                          "headline": headline, "run_id": run_id,
                      }, run_id))

    return {"learned": learned, "promoted": promoted}


def _seasonal_lift(series: dict[str, float]) -> dict | None:
    """Mean QoQ growth per quarter position; flag a quarter ≥5pp above the rest."""
    by_quarter: dict[int, list[float]] = {1: [], 2: [], 3: [], 4: []}
    ordered = periods.ordered(list(series.keys()))
    for prev, cur in zip(ordered, ordered[1:]):
        if periods.gap(prev, cur) == 1 and series[prev]:
            q = periods.parse(cur)[1]
            by_quarter[q].append((series[cur] / series[prev] - 1) * 100)
    means = {q: sum(v) / len(v) for q, v in by_quarter.items() if v}
    if len(means) < 4:
        return None
    for q, m in means.items():
        others = [v for k, v in means.items() if k != q]
        lift = m - sum(others) / len(others)
        if lift >= 5.0:
            return {"quarter": q, "lift_pct": round(lift, 1)}
    return None

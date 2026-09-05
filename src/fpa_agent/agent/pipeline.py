"""End-to-end causal FP&A pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from fpa_agent.agent.llm import complete, llm_available
from fpa_agent.agent.prompts import EXEC_WRITER_SYSTEM
from fpa_agent.agent.validator import ValidationResult, validate_summary
from fpa_agent.analytics.attribution import Driver, recursive_attribute
from fpa_agent.analytics.clustering import DriverCluster, cluster_drivers, clusters_to_frame
from fpa_agent.analytics.timeseries import build_metric_history, sort_periods, zscore_series
from fpa_agent.metrics.hierarchy import SEC_COMPANION_METRICS


def _through_period(hist: pd.Series, period: str) -> pd.Series:
    ordered = [p for p in sort_periods(list(hist.index.astype(str))) if _period_key(p) <= _period_key(period)]
    out = hist.reindex(ordered)
    out.name = hist.name
    return out


def _period_key(period: str) -> tuple[int, int]:
    year, q = period.split("-Q")
    return int(year), int(q)


@dataclass
class AnalysisResult:
    company: str
    period: str
    prior_period: str
    revenue_stat: dict[str, Any]
    companion_stats: list[dict[str, Any]]
    drivers: list[Driver]
    clusters: list[DriverCluster]
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    passed: bool | None = None
    agent_loop: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        payload = {
            "company": self.company,
            "period": self.period,
            "prior_period": self.prior_period,
            "revenue_stat": self.revenue_stat,
            "companion_stats": self.companion_stats,
            "drivers": [d.to_dict() for d in self.drivers],
            "clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "label": c.label,
                    "total_delta": c.total_delta,
                    "mean_z": c.mean_z,
                    "dimensions": c.dimensions,
                    "feature_summary": c.feature_summary,
                    "drivers": [d.to_dict() for d in c.drivers],
                }
                for c in self.clusters
            ],
            "summary": self.summary,
            "evidence": self.evidence,
            "validation": self.validation,
            "passed": self.passed,
            "agent_loop": self.agent_loop,
            "llm_used": llm_available(),
        }
        return json.dumps(payload, indent=2, default=str)


def load_tables(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load given CSVs from a directory.

    Expected files (optional but revenue path needs product/geo/user for drill):
      sec_metrics.csv
      product_segments.csv
      geography.csv
      user_segments.csv
    """
    data_dir = Path(data_dir)
    tables: dict[str, pd.DataFrame] = {}
    for name in ("sec_metrics", "product_segments", "geography", "user_segments"):
        path = data_dir / f"{name}.csv"
        if path.exists():
            tables[name] = pd.read_csv(path)
    if "sec_metrics" not in tables and "product_segments" not in tables:
        raise FileNotFoundError(
            f"No input tables found in {data_dir}. "
            "Provide at least sec_metrics.csv or product_segments.csv"
        )
    return tables


def analyze(
    tables: dict[str, pd.DataFrame],
    *,
    company: str,
    period: str,
    prior_period: str,
    root: str = "revenue",
    metric: str = "revenue",
    materiality_share: float = 0.08,
    material_z: float = 1.5,
    max_depth: int = 4,
    validate: bool = False,
    rewrite_on_fail: bool = True,
    agent_loop: bool = False,
    max_loop_rounds: int = 3,
) -> AnalysisResult:
    if metric not in {"revenue", "operating_income"}:
        raise ValueError("metric must be 'revenue' or 'operating_income'")

    sec = tables.get("sec_metrics")
    if sec is not None and "company" in sec.columns:
        sec_c = sec[sec["company"] == company]
    else:
        sec_c = sec

    # North-star time series + z-score (revenue or operating income)
    if sec_c is not None and metric in sec_c.columns:
        north_hist = build_metric_history(sec_c, value_col=metric)
    else:
        prod = tables["product_segments"]
        if "company" in prod.columns:
            prod = prod[prod["company"] == company]
        value_col = metric if metric in prod.columns else "revenue"
        north_hist = build_metric_history(prod, value_col=value_col)

    north_hist = _through_period(north_hist, period)
    north_hist.name = metric
    north_stat = zscore_series(north_hist, material_z=material_z, compare_period=prior_period)

    companion_stats: list[dict[str, Any]] = []
    if sec_c is not None:
        for col in SEC_COMPANION_METRICS:
            if col not in sec_c.columns or col == metric:
                continue
            hist = build_metric_history(sec_c, value_col=col)
            if period not in hist.index or len(hist.dropna()) < 2:
                continue
            hist = _through_period(hist, period)
            hist.name = col
            st = zscore_series(hist, material_z=material_z, compare_period=prior_period)
            companion_stats.append(asdict(st))

    drivers = recursive_attribute(
        tables,
        root,
        period=period,
        prior_period=prior_period,
        company=company,
        materiality_share=materiality_share,
        material_z=material_z,
        max_depth=max_depth,
        metric=metric,
    )
    clusters = cluster_drivers(drivers)

    dollar_clusters = [c for c in clusters if "kpi" not in c.dimensions]
    kpi_clusters = [c for c in clusters if "kpi" in c.dimensions]

    def _pack_cluster(c: DriverCluster) -> dict[str, Any]:
        return {
            "label": c.label,
            "total_delta": c.total_delta,
            "mean_z": c.mean_z,
            "dimensions": c.dimensions,
            "drivers": [
                {
                    "label": d.label,
                    "metric": d.metric,
                    "dimension": d.dimension,
                    "delta": d.delta,
                    "pct_change": d.pct_change,
                    "z_score": d.z_score,
                    "share_of_parent_delta": d.share_of_parent_delta,
                    "path": d.path,
                }
                for d in c.drivers[:8]
            ],
        }

    metric_label = "Revenue" if metric == "revenue" else "Operating income"
    prompt_payload = {
        "company": company,
        "period": period,
        "prior_period": prior_period,
        "north_star_metric": metric,
        "north_star_label": metric_label,
        "baseline": {
            "comparison": f"{prior_period} → {period}",
            "delta_definition": f"value({period}) − value({prior_period})",
            "pct_definition": f"(value({period}) − value({prior_period})) / value({prior_period})",
            "z_score_definition": (
                f"z = (value({period}) − mean of trailing history excluding {period}) "
                "/ std of that history; history is prior periods in the given series"
            ),
            "units": "USD millions unless the metric is a rate/KPI",
        },
        "revenue_delta": north_stat.delta,
        "revenue_pct": north_stat.pct_change,
        "revenue_z": north_stat.z_score,
        "revenue_value": north_stat.value,
        "revenue_prior_value": north_stat.prior_value,
        "dollar_attribution_clusters": [_pack_cluster(c) for c in dollar_clusters],
        "operational_kpi_clusters": [_pack_cluster(c) for c in kpi_clusters],
        "clusters": [_pack_cluster(c) for c in dollar_clusters + kpi_clusters],
        "companion_metrics": [
            {
                "metric": s["metric"],
                "delta": s["delta"],
                "pct_change": s["pct_change"],
                "z_score": s["z_score"],
                "is_material": s["is_material"],
                "value": s.get("value"),
                "prior_value": s.get("prior_value"),
            }
            for s in companion_stats
            if s.get("is_material")
        ],
        "story_hints": {
            "conglomerate": "Berkshire" in company or "Berkshire" in company.replace("_", " "),
            "explain_profit_and_loss": True,
            "note": (
                "If operating income declined in a segment while revenue rose (or vice versa), "
                "state both facts with numbers. Name subsidiaries that drove gains AND those "
                "that drove earnings declines."
            ),
        },
    }

    system = EXEC_WRITER_SYSTEM.format(
        company=company,
        period=period,
        prior_period=prior_period,
    )
    if metric == "operating_income":
        system += (
            "\n\nNORTH STAR FOR THIS RUN: operating income (profit), not revenue. "
            "Explain what increased earnings and what reduced earnings / created a loss drag, "
            "with $ and % vs the prior period. Name subsidiaries explicitly."
        )
    else:
        system += (
            "\n\nIf this is a conglomerate, name subsidiaries/segments (not just abstract clusters). "
            "Also note material profit/loss divergences from companion operating_income evidence."
        )

    loop_meta: dict[str, Any] = {}
    validation: ValidationResult | None = None
    passed: bool | None = None

    if agent_loop:
        from fpa_agent.agent.loop import run_agent_loop

        loop_result = run_agent_loop(prompt_payload, max_rounds=max_loop_rounds)
        summary = loop_result.summary
        validation = loop_result.validation
        passed = loop_result.passed
        loop_meta = {
            "enabled": True,
            "rounds": loop_result.rounds,
            "history": loop_result.history,
            "passed": loop_result.passed,
        }
    else:
        summary = complete(system, json.dumps(prompt_payload, default=str))
        if validate:
            validation = validate_summary(
                summary,
                prompt_payload,
                rewrite_on_fail=rewrite_on_fail,
                max_rounds=1,
            )
            summary = validation.summary_validated
            passed = validation.passed
        loop_meta = {"enabled": False}

    evidence = {
        "driver_table": clusters_to_frame(clusters).to_dict(orient="records"),
        "llm_available": llm_available(),
        "prompt_payload": prompt_payload,
        "metric": metric,
    }
    return AnalysisResult(
        company=company,
        period=period,
        prior_period=prior_period,
        revenue_stat=asdict(north_stat),
        companion_stats=companion_stats,
        drivers=drivers,
        clusters=clusters,
        summary=summary,
        evidence=evidence,
        validation=validation.to_dict() if validation else {},
        passed=passed,
        agent_loop=loop_meta,
    )

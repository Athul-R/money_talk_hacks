"""Recursive variance attribution: which children explain a parent delta."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from fpa_agent.analytics.timeseries import SeriesStat, build_metric_history, kpi_histories, zscore_series
from fpa_agent.metrics.hierarchy import AD_KPI_COLUMNS, HierarchyNode, get_hierarchy


@dataclass
class Driver:
    metric: str
    label: str
    dimension: str
    value: float
    prior_value: float | None
    delta: float
    pct_change: float | None
    share_of_parent_delta: float | None
    z_score: float | None
    is_material: bool
    path: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AttributionResult:
    parent: str
    period: str
    parent_delta: float
    drivers: list[Driver]
    explained_share: float
    residual: float


def _apply_company(df: pd.DataFrame, company: str | None) -> pd.DataFrame:
    if company and "company" in df.columns:
        return df[df["company"] == company]
    return df


def _slice(df: pd.DataFrame, node: HierarchyNode) -> pd.DataFrame:
    view = df
    if node.filter:
        for k, v in node.filter.items():
            if k in view.columns:
                view = view[view[k] == v]
    return view


def _safe_z(hist: pd.Series, name: str, material_z: float = 1.5) -> SeriesStat | None:
    if hist is None or len(hist.dropna()) < 2:
        return None
    hist = hist.copy()
    hist.name = name
    try:
        return zscore_series(hist, material_z=material_z)
    except ValueError:
        return None


def _period_value(view: pd.DataFrame, period: str, value_col: str) -> float:
    if view.empty or value_col not in view.columns:
        return 0.0
    return float(view.loc[view["period"] == period, value_col].sum())


def expand_node_drivers(
    tables: dict[str, pd.DataFrame],
    node_id: str,
    *,
    period: str,
    prior_period: str,
    company: str | None,
    parent_delta: float | None = None,
    material_z: float = 1.5,
    hierarchy: dict[str, HierarchyNode] | None = None,
) -> list[Driver]:
    """Expand a node into drivers via additive children OR group_col / KPI slice."""
    hierarchy = hierarchy or get_hierarchy(company or "Alphabet")
    node = hierarchy[node_id]
    drivers: list[Driver] = []

    if node.children:
        for cid in node.children:
            child = hierarchy[cid]
            table = tables.get(child.table or node.table or "product_segments")
            if table is None:
                continue
            view = _slice(_apply_company(table, company), child)
            cur = _period_value(view, period, child.value_col)
            prv = _period_value(view, prior_period, child.value_col)
            delta = cur - prv
            hist = build_metric_history(view, value_col=child.value_col)
            stat = _safe_z(hist, child.id, material_z=material_z)
            share = (delta / parent_delta) if parent_delta else None
            drivers.append(
                Driver(
                    metric=cid,
                    label=child.label,
                    dimension=child.dimension,
                    value=cur,
                    prior_value=prv,
                    delta=delta,
                    pct_change=(delta / prv) if prv else None,
                    share_of_parent_delta=share,
                    z_score=stat.z_score if stat else None,
                    is_material=bool(stat.is_material) if stat else abs(delta) > 0,
                    path=[node_id, cid],
                    evidence={"additive": True},
                )
            )
        return drivers

    # Leaf dimensional node
    table = tables.get(node.table or "product_segments")
    if table is None:
        return []
    view = _slice(_apply_company(table, company), node)

    if node.dimension == "kpi":
        # Prefer rate KPIs for causal evidence; volumes only if |z| or |pct| large
        rate_kpis = {
            "ctr",
            "cpc",
            "cpm",
            "rpm",
            "arpu",
            "revenue_per_click",
            "revenue_per_impression",
        }
        for kpi, hist in kpi_histories(view, AD_KPI_COLUMNS).items():
            if period not in hist.index:
                continue
            cur = float(hist.get(period, 0.0) or 0.0)
            prv = float(hist.get(prior_period, 0.0) or 0.0) if prior_period in hist.index else 0.0
            delta = cur - prv
            pct = (delta / prv) if prv else None
            stat = _safe_z(hist, kpi, material_z=material_z)
            material = bool(stat.is_material) if stat else False
            if kpi in rate_kpis and pct is not None and abs(pct) >= 0.03:
                material = True
            if kpi not in rate_kpis:
                # volume KPIs: require clear % move AND z; keep as evidence only
                material = bool(
                    pct is not None
                    and abs(pct) >= 0.05
                    and stat is not None
                    and abs(stat.z_score or 0) >= material_z
                )
            drivers.append(
                Driver(
                    metric=f"{node_id}:{kpi}",
                    label=f"{node.label} · {kpi}",
                    dimension="kpi",
                    value=cur,
                    prior_value=prv,
                    delta=delta,
                    pct_change=pct,
                    share_of_parent_delta=None,
                    z_score=stat.z_score if stat else None,
                    is_material=material,
                    path=[node_id, kpi],
                    evidence={"kpi": kpi, "additive": False, "kpi_kind": "rate" if kpi in rate_kpis else "volume"},
                )
            )
        return drivers

    if node.group_col and node.group_col in view.columns:
        for key, g in view.groupby(node.group_col):
            cur = _period_value(g, period, node.value_col)
            prv = _period_value(g, prior_period, node.value_col)
            delta = cur - prv
            hist = g.groupby("period")[node.value_col].sum()
            hist.name = str(key)
            stat = _safe_z(hist, str(key), material_z=material_z)
            share = (delta / parent_delta) if parent_delta else None
            drivers.append(
                Driver(
                    metric=f"{node_id}:{key}",
                    label=f"{node.label} / {key}",
                    dimension=node.dimension,
                    value=cur,
                    prior_value=prv,
                    delta=delta,
                    pct_change=(delta / prv) if prv else None,
                    share_of_parent_delta=share,
                    z_score=stat.z_score if stat else None,
                    is_material=bool(stat.is_material) if stat else abs(delta) > 0,
                    path=[node_id, str(key)],
                    evidence={
                        "group_col": node.group_col,
                        "group_value": str(key),
                        "additive": False,
                    },
                )
            )
    return drivers


def child_contributions(
    tables: dict[str, pd.DataFrame],
    parent_id: str,
    *,
    period: str,
    prior_period: str,
    company: str | None = None,
    material_z: float = 1.5,
    hierarchy: dict[str, HierarchyNode] | None = None,
) -> AttributionResult:
    hierarchy = hierarchy or get_hierarchy(company or "Alphabet")
    parent = hierarchy[parent_id]
    parent_table = tables.get(parent.table or "sec_metrics")
    if parent_table is None:
        raise KeyError(f"missing table for {parent_id}")

    pt = _slice(_apply_company(parent_table, company), parent)
    cur = _period_value(pt, period, parent.value_col)
    prv = _period_value(pt, prior_period, parent.value_col)
    parent_delta = cur - prv

    drivers = expand_node_drivers(
        tables,
        parent_id,
        period=period,
        prior_period=prior_period,
        company=company,
        parent_delta=parent_delta,
        material_z=material_z,
        hierarchy=hierarchy,
    )
    drivers.sort(
        key=lambda d: (abs(d.share_of_parent_delta or 0.0), abs(d.delta), abs(d.z_score or 0.0)),
        reverse=True,
    )
    dollar = [d for d in drivers if d.evidence.get("additive") and d.share_of_parent_delta is not None]
    explained = sum(d.delta for d in dollar)
    explained_share = (explained / parent_delta) if parent_delta else 0.0
    return AttributionResult(
        parent=parent_id,
        period=period,
        parent_delta=parent_delta,
        drivers=drivers,
        explained_share=explained_share,
        residual=parent_delta - explained,
    )


def recursive_attribute(
    tables: dict[str, pd.DataFrame],
    root_id: str,
    *,
    period: str,
    prior_period: str,
    company: str,
    materiality_share: float = 0.08,
    material_z: float = 1.5,
    max_depth: int = 4,
    explain_coverage: float = 0.80,
    metric: str = "revenue",
) -> list[Driver]:
    """Top-down additive walk, then dimensional drills on material product nodes."""
    hierarchy = get_hierarchy(company, metric=metric)
    collected: list[Driver] = []

    def is_material(d: Driver, parent_delta: float) -> bool:
        if d.z_score is not None and abs(d.z_score) >= material_z:
            return True
        if d.share_of_parent_delta is not None and abs(d.share_of_parent_delta) >= materiality_share:
            return True
        if parent_delta and abs(d.delta) >= abs(parent_delta) * materiality_share:
            return True
        return bool(d.is_material and abs(d.delta) > 0)

    def drill_dimensions(node_id: str, path: list[str], parent_delta: float) -> None:
        node = hierarchy.get(node_id)
        if not node or not node.drills:
            return
        for drill_id in node.drills:
            if drill_id not in hierarchy:
                continue
            drill_drivers = expand_node_drivers(
                tables,
                drill_id,
                period=period,
                prior_period=prior_period,
                company=company,
                parent_delta=parent_delta,
                material_z=material_z,
                hierarchy=hierarchy,
            )
            for d in drill_drivers:
                if not is_material(d, parent_delta):
                    continue
                d.path = path + d.path
                d.evidence = {**d.evidence, "drill_of": node_id}
                collected.append(d)

    def walk(node_id: str, depth: int, path: list[str]) -> None:
        if depth > max_depth or node_id not in hierarchy:
            return
        result = child_contributions(
            tables,
            node_id,
            period=period,
            prior_period=prior_period,
            company=company,
            material_z=material_z,
            hierarchy=hierarchy,
        )
        if not result.drivers:
            drill_dimensions(node_id, path, result.parent_delta)
            return

        covered = 0.0
        selected: list[Driver] = []
        for d in result.drivers:
            if not is_material(d, result.parent_delta):
                continue
            d.path = path + [d.metric] if not d.path else path + d.path[1:]
            selected.append(d)
            collected.append(d)
            if d.share_of_parent_delta is not None:
                covered += abs(d.share_of_parent_delta)
            if covered >= explain_coverage:
                break

        # Always keep opposite-sign material drivers (e.g. underwriting earnings decline
        # while total operating income rises) so profit/loss drags are not dropped.
        selected_ids = {d.metric for d in selected}
        for d in result.drivers:
            if d.metric in selected_ids:
                continue
            if not is_material(d, result.parent_delta):
                continue
            if result.parent_delta and d.delta * result.parent_delta < 0:
                d.path = path + [d.metric] if not d.path else path + d.path[1:]
                selected.append(d)
                collected.append(d)

        for d in selected:
            base = d.metric.split(":")[0]
            child = hierarchy.get(base)
            if child and child.children:
                walk(base, depth + 1, d.path)
            elif child:
                drill_dimensions(base, d.path, d.delta)

        if hierarchy[node_id].drills and depth > 0:
            drill_dimensions(node_id, path, result.parent_delta)

    walk(root_id, 0, [root_id])
    return collected

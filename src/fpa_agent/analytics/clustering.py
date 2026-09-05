"""Cluster material drivers so the LLM summarizes coherent themes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fpa_agent.analytics.attribution import Driver


@dataclass
class DriverCluster:
    cluster_id: int
    label: str
    drivers: list[Driver]
    total_delta: float
    mean_z: float
    dimensions: list[str]
    feature_summary: dict


def _feature_matrix(drivers: list[Driver]) -> tuple[np.ndarray, list[str]]:
    """Simple numeric features for clustering: delta, pct, z, dimension one-hots."""
    dims = sorted({d.dimension for d in drivers})
    rows = []
    for d in drivers:
        row = [
            float(d.delta or 0.0),
            float(d.pct_change or 0.0),
            float(d.z_score or 0.0),
            float(d.share_of_parent_delta or 0.0),
        ]
        for dim in dims:
            row.append(1.0 if d.dimension == dim else 0.0)
        rows.append(row)
    cols = ["delta", "pct_change", "z_score", "share"] + [f"dim:{d}" for d in dims]
    X = np.asarray(rows, dtype=float)
    # standardize numeric cols
    for i in range(4):
        col = X[:, i]
        mu, sigma = col.mean(), col.std()
        if sigma > 1e-12:
            X[:, i] = (col - mu) / sigma
    return X, cols


def _dollar_delta(d: Driver) -> float:
    """Only product/geo/user revenue deltas count as $ attribution."""
    if d.dimension == "kpi":
        return 0.0
    return float(d.delta or 0.0)


def cluster_drivers(
    drivers: list[Driver],
    *,
    max_clusters: int = 4,
) -> list[DriverCluster]:
    if not drivers:
        return []

    # Cluster $ drivers and KPI evidence separately so impression counts
    # do not dominate revenue attribution themes.
    dollar = [d for d in drivers if d.dimension != "kpi"]
    kpis = [d for d in drivers if d.dimension == "kpi"]

    clusters: list[DriverCluster] = []
    clusters.extend(_cluster_group(dollar, max_clusters=max_clusters, start_id=0))
    clusters.extend(_cluster_group(kpis, max_clusters=min(2, max_clusters), start_id=100))
    clusters.sort(key=lambda c: (0 if "kpi" not in c.dimensions else 1, -abs(c.total_delta)))
    return clusters


def _cluster_group(
    drivers: list[Driver],
    *,
    max_clusters: int,
    start_id: int,
) -> list[DriverCluster]:
    if not drivers:
        return []
    if len(drivers) == 1:
        d = drivers[0]
        return [
            DriverCluster(
                cluster_id=start_id,
                label=_auto_label([d]),
                drivers=[d],
                total_delta=_dollar_delta(d),
                mean_z=float(d.z_score or 0.0),
                dimensions=[d.dimension],
                feature_summary={"n": 1},
            )
        ]

    X, _ = _feature_matrix(drivers)
    k = min(max_clusters, len(drivers))
    labels = _kmeans(X, k=k, seed=7)

    clusters: list[DriverCluster] = []
    for cid in sorted(set(labels)):
        members = [d for d, lab in zip(drivers, labels) if lab == cid]
        total_delta = float(sum(_dollar_delta(d) for d in members))
        zs = [d.z_score for d in members if d.z_score is not None]
        clusters.append(
            DriverCluster(
                cluster_id=start_id + int(cid),
                label=_auto_label(members),
                drivers=sorted(members, key=lambda x: abs(_dollar_delta(x) or x.pct_change or 0.0), reverse=True),
                total_delta=total_delta,
                mean_z=float(np.mean(zs)) if zs else 0.0,
                dimensions=sorted({d.dimension for d in members}),
                feature_summary={
                    "n": len(members),
                    "top_metrics": [
                        d.metric
                        for d in sorted(
                            members,
                            key=lambda x: abs(x.pct_change or 0.0) if x.dimension == "kpi" else abs(x.delta),
                            reverse=True,
                        )[:5]
                    ],
                },
            )
        )
    return clusters


def _auto_label(members: list[Driver]) -> str:
    dims = sorted({d.dimension for d in members})
    net = sum(_dollar_delta(d) for d in members)
    if dims == ["kpi"]:
        pcts = [d.pct_change for d in members if d.pct_change is not None]
        direction = "up" if (pcts and sum(pcts) >= 0) else "down" if pcts else "move"
        return f"KPI {direction}"
    direction = "up" if net >= 0 else "down"
    if dims == ["geography"]:
        return f"Geography {direction}"
    if dims == ["user"]:
        return f"User segment {direction}"
    if dims == ["product"]:
        return f"Product {direction}"
    if "geography" in dims:
        return f"Geography/mix {direction}"
    if "user" in dims:
        return f"User/mix {direction}"
    return f"{'+'.join(dims)} {direction}"


def _kmeans(X: np.ndarray, k: int, seed: int = 0, iters: int = 50) -> list[int]:
    rng = np.random.default_rng(seed)
    # init: pick distant points
    centroids = X[rng.choice(len(X), size=k, replace=False)].copy()
    labels = np.zeros(len(X), dtype=int)
    for _ in range(iters):
        dists = ((X[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
        new_labels = dists.argmin(axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for j in range(k):
            mask = labels == j
            if mask.any():
                centroids[j] = X[mask].mean(axis=0)
    return labels.tolist()


def clusters_to_frame(clusters: list[DriverCluster]) -> pd.DataFrame:
    rows = []
    for c in clusters:
        for d in c.drivers:
            rows.append(
                {
                    "cluster_id": c.cluster_id,
                    "cluster_label": c.label,
                    "metric": d.metric,
                    "label": d.label,
                    "dimension": d.dimension,
                    "delta": d.delta,
                    "pct_change": d.pct_change,
                    "z_score": d.z_score,
                    "share_of_parent_delta": d.share_of_parent_delta,
                    "path": " > ".join(d.path),
                }
            )
    return pd.DataFrame(rows)

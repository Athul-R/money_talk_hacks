"""Stage 3c: group the transaction-level rows that drive a delta.

Deterministic k-means (fixed seed, numpy only) over per-customer features:
standardized Δ$, one-hot customer_type, one-hot sub_product. Labels are the
dominant type · sub_product of each cluster, so "enterprise · AI Infrastructure"
is a description of the data, not a model's opinion.

Concentration is the curve the CFO actually asks about: top-N customers vs
cumulative share of the branch delta.
"""

from __future__ import annotations

import numpy as np


def _one_hot(values: list[str]) -> tuple[np.ndarray, list[str]]:
    cats = sorted(set(values))
    mat = np.zeros((len(values), len(cats)))
    for i, v in enumerate(values):
        mat[i, cats.index(v)] = 1.0
    return mat, cats


def _kmeans(features: np.ndarray, k: int, seed: int = 7, iters: int = 60) -> np.ndarray:
    """Plain k-means with a seeded kmeans++ init; same input ⇒ same clusters."""
    rng = np.random.default_rng(seed)
    n = len(features)
    centers = [features[int(rng.integers(n))]]
    for _ in range(k - 1):
        d2 = np.min([((features - c) ** 2).sum(axis=1) for c in centers], axis=0)
        probs = d2 / d2.sum() if d2.sum() > 0 else np.full(n, 1 / n)
        centers.append(features[int(rng.choice(n, p=probs))])
    centroids = np.array(centers)

    labels = np.zeros(n, dtype=int)
    for _ in range(iters):
        dists = ((features[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
        new_labels = dists.argmin(axis=1)
        if (new_labels == labels).all():
            break
        labels = new_labels
        for j in range(k):
            member = features[labels == j]
            if len(member):
                centroids[j] = member.mean(axis=0)
    return labels


def cluster_customers(per_customer: list[dict], branch_delta: float, k: int = 3) -> list[dict]:
    """per_customer rows come from attribution.bridge(). Returns clusters sorted
    by |Δ| with members, share of the branch delta, and scatter-ready points."""
    rows = [r for r in per_customer if r["delta"] != 0]
    if len(rows) < 2 or branch_delta == 0:
        return []
    k = min(k, len(rows))

    deltas = np.array([r["delta"] for r in rows], dtype=float)
    z = (deltas - deltas.mean()) / (deltas.std() or 1.0)
    types, _ = _one_hot([r["customer_type"] for r in rows])
    subs, _ = _one_hot([r["sub_product"] for r in rows])
    features = np.column_stack([z * 3.0, types, subs])  # Δ$ dominates the distance

    labels = _kmeans(features, k)

    clusters = []
    for j in range(k):
        members = [r for r, l in zip(rows, labels) if l == j]
        if not members:
            continue
        total = sum(r["delta"] for r in members)
        dom_type = max(set(m["customer_type"] for m in members),
                       key=lambda t: sum(abs(m["delta"]) for m in members if m["customer_type"] == t))
        dom_sub = max(set(m["sub_product"] for m in members),
                      key=lambda s: sum(abs(m["delta"]) for m in members if m["sub_product"] == s))
        members_sorted = sorted(members, key=lambda m: -abs(m["delta"]))
        clusters.append({
            "label": f"{dom_type.lower()} · {dom_sub}",
            "delta_abs": round(total, 2),
            "share": round(total / branch_delta, 3),
            "size": len(members),
            "members": [m["customer_name"] for m in members_sorted[:5]],
            "points": [
                {"name": m["customer_name"], "x": m["value_a"], "y": m["value_b"],
                 "delta": m["delta"], "type": m["customer_type"]}
                for m in members_sorted
            ],
        })

    # k-means can split one behavioural group by size alone; identical labels
    # mean identical stories, so merge them before ranking.
    merged: dict[str, dict] = {}
    for c in clusters:
        if c["label"] in merged:
            m = merged[c["label"]]
            m["delta_abs"] = round(m["delta_abs"] + c["delta_abs"], 2)
            m["share"] = round(m["share"] + c["share"], 3)
            m["size"] += c["size"]
            m["points"].extend(c["points"])
            m["members"] = [p["name"] for p in
                            sorted(m["points"], key=lambda p: -abs(p["delta"]))[:5]]
        else:
            merged[c["label"]] = c
    return sorted(merged.values(), key=lambda c: -abs(c["delta_abs"]))


def concentration(per_customer: list[dict], branch_delta: float, top_n: int) -> dict | None:
    """Top-N customers vs cumulative % of the branch delta, plus the full curve."""
    if branch_delta == 0 or not per_customer:
        return None
    same_sign = [r for r in per_customer if r["delta"] * branch_delta > 0]
    ranked = sorted(same_sign, key=lambda r: -abs(r["delta"]))
    if not ranked:
        return None

    curve, cum = [], 0.0
    for i, r in enumerate(ranked[:12], start=1):
        cum += r["delta"]
        curve.append({"n": i, "name": r["customer_name"],
                      "cum_share": round(cum / branch_delta, 3)})

    top = ranked[:top_n]
    top_delta = sum(r["delta"] for r in top)
    return {
        "top_n": min(top_n, len(ranked)),
        "top_n_delta": round(top_delta, 2),
        "top_n_share": round(top_delta / branch_delta, 3),
        "top_names": [r["customer_name"] for r in top],
        "curve": curve,
        "customer_count": len(ranked),
    }

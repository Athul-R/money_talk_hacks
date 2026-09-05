"""Stage 2: the variance router. Decompose the metric along every axis the
summaries carry, score each axis, and rank the winning axis's children by |Δ$|.

Explanatory power = (share of |Δ| captured by the top-3 children) × (1 − 1/n).
The first factor rewards axes whose few branches carry the story; the second
keeps a trivial 2-way split from beating a real segmentation by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import metric_graph
from .attribution import line_item_bridge
from .normalize import Dataset


@dataclass
class Child:
    name: str
    dimension: str
    value_a: float
    value_b: float
    delta_abs: float
    share: float             # signed share of the parent's Δ magnitude budget
    sign: float = 1.0        # line items keep their formula sign for the bridge
    capped: bool = False     # pre-capped aggregates (e.g. "9 smaller accounts")

    def as_dict(self) -> dict:
        return {
            "name": self.name, "dimension": self.dimension,
            "value_a": round(self.value_a, 2), "value_b": round(self.value_b, 2),
            "delta_abs": round(self.delta_abs, 2), "share": round(self.share, 3),
        }


@dataclass
class Routing:
    axis: str
    children: list[Child]
    candidates: list[dict] = field(default_factory=list)  # the scoring table


def _children_shares(pairs: list[tuple[str, float, float, float]], dimension: str) -> list[Child]:
    """pairs = (name, value_a, value_b, sign). Share is |Δ| against the summed
    |Δ| across children, signed by the child's contribution direction."""
    total_abs = sum(abs(sign * (vb - va)) for _, va, vb, sign in pairs) or 1.0
    kids = []
    for name, va, vb, sign in pairs:
        contribution = sign * (vb - va)
        kids.append(Child(
            name=name, dimension=dimension, value_a=va, value_b=vb,
            delta_abs=vb - va,
            share=contribution / total_abs,
            sign=sign,
        ))
    return sorted(kids, key=lambda c: -abs(c.delta_abs))


def route(ds: Dataset, metric: str, period_a: str, period_b: str) -> Routing:
    """Pick the most explanatory axis for this metric and rank its children."""
    # Computed metrics decompose along their own formula — a line-item bridge.
    if metric_graph.is_computed(metric) and not ds.axes_for(metric):
        items = line_item_bridge(
            metric_graph.line_items(ds, metric, period_a),
            metric_graph.line_items(ds, metric, period_b),
        )
        pairs = [(r["name"], r["value_a"], r["value_b"], r["sign"]) for r in items]
        children = _children_shares(pairs, "line_item")
        return Routing(axis="line_item", children=children, candidates=[{
            "axis": "line_item", "power": 1.0, "children": len(children),
            "note": "computed metric — decomposed along its identity",
        }])

    candidates = []
    best: tuple[float, str, list[Child]] | None = None
    for axis in ds.axes_for(metric):
        seg_a = ds.segments(metric, axis, period_a)
        seg_b = ds.segments(metric, axis, period_b)
        names = sorted(set(seg_a) | set(seg_b))
        pairs = [(n, seg_a.get(n, 0.0), seg_b.get(n, 0.0), 1.0) for n in names]
        children = _children_shares(pairs, axis)
        if not children:
            continue
        top3 = sum(abs(c.share) for c in children[:3])
        power = top3 * (1 - 1 / max(len(children), 2))
        candidates.append({
            "axis": axis, "power": round(power, 3), "top3_capture": round(top3, 3),
            "children": len(children),
        })
        if best is None or power > best[0]:
            best = (power, axis, children)

    if best is None:
        raise ValueError(f"no decomposition axis available for {metric}")

    return Routing(axis=best[1], children=best[2],
                   candidates=sorted(candidates, key=lambda c: -c["power"]))


def route_branch(ds: Dataset, parent_dimension: str, parent_name: str,
                 period_a: str, period_b: str) -> Routing | None:
    """Where a drilled branch goes next. The ladder is fixed and deterministic:
    product segment → user_type (customer_type in transactions) → customer.
    line_item components with product coverage (COGS) re-enter at product."""
    if parent_dimension in ("product", "line_item"):
        # line_item children like COGS may carry their own product split.
        if parent_dimension == "line_item":
            seg_a = ds.segments(parent_name, "product", period_a)
            seg_b = ds.segments(parent_name, "product", period_b)
            if seg_a and seg_b:
                names = sorted(set(seg_a) | set(seg_b))
                pairs = [(n, seg_a.get(n, 0.0), seg_b.get(n, 0.0), 1.0) for n in names]
                return Routing(axis="product", children=_children_shares(pairs, "product"))
            return None
        # product branch → customer_type split from transactions
        txn_a = ds.txns(period_a, product=parent_name)
        txn_b = ds.txns(period_b, product=parent_name)
        if txn_a.empty or txn_b.empty:
            return None
        by_type_a = txn_a.groupby("customer_type").net_revenue.sum()
        by_type_b = txn_b.groupby("customer_type").net_revenue.sum()
        names = sorted(set(by_type_a.index) | set(by_type_b.index))
        if len(names) < 2:
            return None
        pairs = [(n, float(by_type_a.get(n, 0.0)), float(by_type_b.get(n, 0.0)), 1.0)
                 for n in names]
        return Routing(axis="user_type", children=_children_shares(pairs, "user_type"))

    if parent_dimension == "user_type":
        return None  # handled by route_customers (needs the product context)

    return None


def route_customers(ds: Dataset, product: str, customer_type: str,
                    period_a: str, period_b: str, min_share: float) -> Routing | None:
    """user_type branch → individual customers. Only customers above the
    materiality floor get their own lane; the tail collapses into one capped
    "N smaller accounts" branch so the graph stays readable."""
    txn_a = ds.txns(period_a, product=product, customer_type=customer_type)
    txn_b = ds.txns(period_b, product=product, customer_type=customer_type)
    if txn_a.empty and txn_b.empty:
        return None

    a = txn_a.groupby("customer_id").agg(name=("customer_name", "first"),
                                         net=("net_revenue", "sum"))
    b = txn_b.groupby("customer_id").agg(name=("customer_name", "first"),
                                         net=("net_revenue", "sum"))
    ids = sorted(set(a.index) | set(b.index))
    pairs = []
    for cid in ids:
        name = str(b.name[cid]) if cid in b.index else str(a.name[cid])
        pairs.append((name,
                      float(a.net[cid]) if cid in a.index else 0.0,
                      float(b.net[cid]) if cid in b.index else 0.0, 1.0))
    children = _children_shares(pairs, "customer")

    majors = [c for c in children if abs(c.share) >= min_share]
    tail = [c for c in children if abs(c.share) < min_share]
    if tail:
        va = sum(c.value_a for c in tail)
        vb = sum(c.value_b for c in tail)
        majors.append(Child(
            name=f"{len(tail)} smaller accounts", dimension="customer",
            value_a=va, value_b=vb, delta_abs=vb - va,
            share=sum(c.share for c in tail),
            capped=True,  # one collapsed lane; individually below the floor
        ))
    return Routing(axis="customer", children=majors)

"""Stage 3d/3x policy: where the recursion stops. Pure decisions, no I/O.

Absolute dollars rank branches, not % growth — a $200M line at +20% outranks a
$10M line at +100%. A branch is capped (red pip, grows no further) when it is
too small to matter or when enough of the parent's variance is already
explained; a processed branch drills only while the running total is still
under the stop threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Materiality


@dataclass
class Decision:
    action: str  # "process" | "cap"
    drill: bool
    reason: str


def decide(
    cfg: Materiality,
    *,
    share: float,
    delta_abs: float,
    parent_delta_abs: float,
    cumulative_explained: float,
    depth: int,
    has_children_data: bool,
) -> Decision:
    """One call per branch, made BEFORE its pips run. `share` is the branch's
    share of parent |variance|; `cumulative_explained` is the running total of
    shares already processed at this level."""
    abs_floor = cfg.min_abs_frac * abs(parent_delta_abs)

    if cumulative_explained >= cfg.stop_at_explained:
        return Decision("cap", False,
                        f"{cumulative_explained:.0%} of the parent Δ already explained")
    if abs(share) < cfg.min_share:
        return Decision("cap", False,
                        f"share {share:.1%} below the {cfg.min_share:.0%} materiality floor")
    if abs(delta_abs) < abs_floor:
        return Decision("cap", False,
                        f"|Δ| below {cfg.min_abs_frac:.0%} of the parent move")

    drill = (
        has_children_data
        and depth < cfg.max_depth
        and (cumulative_explained + max(share, 0.0)) < cfg.stop_at_explained
    )
    reason = ("material — drilling deeper" if drill else
              "material — explained at this level" if depth < cfg.max_depth
              else "max depth reached")
    return Decision("process", drill, reason)

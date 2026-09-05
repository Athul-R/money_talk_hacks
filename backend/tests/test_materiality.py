"""The stop rules: small branches cap, explained-enough caps, drill respects
depth and the running total."""

from fpa.config import Materiality
from fpa.engine.materiality import decide

CFG = Materiality(min_share=0.05, min_abs_frac=0.01, stop_at_explained=0.80,
                  max_depth=4, top_n_customers=3)


def _decide(**kw):
    defaults = dict(share=0.3, delta_abs=300.0, parent_delta_abs=1000.0,
                    cumulative_explained=0.0, depth=0, has_children_data=True)
    return decide(CFG, **{**defaults, **kw})


def test_small_share_caps():
    d = _decide(share=0.04, delta_abs=40.0)
    assert d.action == "cap" and "floor" in d.reason


def test_small_abs_caps_even_with_big_pct():
    # a $10M line at +100% loses to the absolute floor on a $2B parent move
    d = _decide(share=0.06, delta_abs=10.0, parent_delta_abs=2000.0)
    assert d.action == "cap"


def test_explained_enough_caps_the_rest():
    d = _decide(cumulative_explained=0.85)
    assert d.action == "cap" and "explained" in d.reason


def test_drill_when_room_remains():
    d = _decide(share=0.45, cumulative_explained=0.0)
    assert d.action == "process" and d.drill


def test_no_drill_when_this_branch_crosses_the_stop():
    # processing is fine, but drilling would spend effort past the 80% mark
    d = _decide(share=0.40, cumulative_explained=0.45)
    assert d.action == "process" and not d.drill


def test_negative_share_can_still_drill():
    # cost lines have negative contribution; they must remain drillable
    d = _decide(share=-0.30, cumulative_explained=0.60)
    assert d.action == "process" and d.drill


def test_max_depth_stops_drill():
    d = _decide(depth=4)
    assert d.action == "process" and not d.drill


def test_no_children_data_no_drill():
    d = _decide(has_children_data=False)
    assert d.action == "process" and not d.drill

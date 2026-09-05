"""The bridge is an identity, not an estimate: price + volume + mix + customer
(+ residual float noise) must equal the delta exactly, for any input."""

import pandas as pd

from fpa.engine.attribution import bridge, line_item_bridge


def _txns(rows):
    return pd.DataFrame([
        {"customer_id": cid, "customer_name": cid, "customer_type": t,
         "sub_product": "X", "geography": "Americas",
         "units": u, "net_revenue": net}
        for cid, t, u, net in rows
    ])


def test_bridge_sums_exactly_to_delta():
    a = _txns([("c1", "Ent", 100, 200.0), ("c2", "SMB", 50, 55.0), ("c3", "Ent", 10, 30.0)])
    b = _txns([("c1", "Ent", 180, 396.0), ("c2", "SMB", 45, 54.0), ("c4", "Ent", 20, 80.0)])
    out = bridge(a, b)
    delta = b.net_revenue.sum() - a.net_revenue.sum()
    assert abs(out.total() - delta) < 1e-6
    assert abs(out.other) < 1e-6  # identity holds; residual is float noise


def test_new_and_churned_land_in_customer_driver():
    a = _txns([("c1", "Ent", 100, 200.0), ("gone", "SMB", 10, 40.0)])
    b = _txns([("c1", "Ent", 100, 200.0), ("new", "Ent", 5, 90.0)])
    out = bridge(a, b)
    assert out.customer == 90.0 - 40.0
    assert out.price == 0.0 and out.volume == 0.0


def test_pure_volume_move():
    a = _txns([("c1", "Ent", 100, 200.0)])   # price 2.0
    b = _txns([("c1", "Ent", 150, 300.0)])   # price 2.0, units +50
    out = bridge(a, b)
    assert abs(out.volume - 100.0) < 1e-9
    assert abs(out.price) < 1e-9 and abs(out.mix) < 1e-9
    assert out.top_driver == "volume"


def test_pure_price_move():
    a = _txns([("c1", "Ent", 100, 200.0)])   # price 2.0
    b = _txns([("c1", "Ent", 100, 260.0)])   # price 2.6
    out = bridge(a, b)
    assert abs(out.price - 60.0) < 1e-9
    assert abs(out.volume) < 1e-9


def test_line_item_bridge_signs():
    a = {"Revenue": (100.0, +1), "COGS": (40.0, -1)}
    b = {"Revenue": (120.0, +1), "COGS": (52.0, -1)}
    items = line_item_bridge(a, b)
    by_name = {i["name"]: i for i in items}
    assert by_name["Revenue"]["contribution"] == 20.0
    assert by_name["COGS"]["contribution"] == -12.0
    # Δ(GP) = 20 − 12 = 8 — the contributions sum to the computed metric's move
    assert sum(i["contribution"] for i in items) == 8.0
    # ranked by |contribution|
    assert items[0]["name"] == "Revenue"

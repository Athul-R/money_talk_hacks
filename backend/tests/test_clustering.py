"""Clustering is deterministic and concentration curves are exact."""

from fpa.engine.clustering import cluster_customers, concentration


def _rows():
    return [
        {"customer_id": "a", "customer_name": "A", "customer_type": "Enterprise",
         "sub_product": "AI", "geography": "Am", "value_a": 100, "value_b": 300, "delta": 200},
        {"customer_id": "b", "customer_name": "B", "customer_type": "Enterprise",
         "sub_product": "AI", "geography": "Am", "value_a": 90, "value_b": 250, "delta": 160},
        {"customer_id": "c", "customer_name": "C", "customer_type": "SMB",
         "sub_product": "Suite", "geography": "Am", "value_a": 50, "value_b": 60, "delta": 10},
        {"customer_id": "d", "customer_name": "D", "customer_type": "SMB",
         "sub_product": "Suite", "geography": "Am", "value_a": 40, "value_b": 52, "delta": 12},
        {"customer_id": "e", "customer_name": "E", "customer_type": "SMB",
         "sub_product": "Suite", "geography": "Am", "value_a": 45, "value_b": 63, "delta": 18},
    ]


def test_clusters_are_deterministic_and_labeled_from_data():
    delta = sum(r["delta"] for r in _rows())
    first = cluster_customers(_rows(), delta)
    second = cluster_customers(_rows(), delta)
    assert first == second
    assert first[0]["label"] == "enterprise · AI"
    assert first[0]["share"] == round(360 / delta, 3)


def test_cluster_shares_sum_to_one():
    delta = sum(r["delta"] for r in _rows())
    clusters = cluster_customers(_rows(), delta)
    assert abs(sum(c["share"] for c in clusters) - 1.0) < 0.01


def test_concentration_top_n():
    delta = sum(r["delta"] for r in _rows())
    conc = concentration(_rows(), delta, top_n=2)
    assert conc["top_names"] == ["A", "B"]
    assert conc["top_n_delta"] == 360
    assert conc["top_n_share"] == round(360 / delta, 3)
    # the curve is cumulative and monotone
    shares = [p["cum_share"] for p in conc["curve"]]
    assert shares == sorted(shares)

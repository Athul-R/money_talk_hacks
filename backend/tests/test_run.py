"""End-to-end engine runs on the calibrated fixtures — the acceptance story:
reconciliation, append-only lanes, exact bridges, materiality caps, memory
recall + promotion across sequential runs."""

import pytest

from fpa.config import FIXTURES_DIR, Materiality
from fpa.engine.normalize import load
from fpa.engine.run import Runner
from fpa.memory.store import MemoryStore


@pytest.fixture(scope="module")
def ds():
    return load(FIXTURES_DIR, name="auric-test")


@pytest.fixture(scope="module")
def runs(ds):
    """Run 1 (background), run 2 (hero), run 3 (profitability) share memory."""
    memory = MemoryStore()
    bundles = []
    for i, (metric, pa, pb) in enumerate([
        ("Revenue", "2025-Q1", "2026-Q1"),
        ("Revenue", "2025-Q2", "2026-Q2"),
        ("Operating income", "2025-Q2", "2026-Q2"),
    ]):
        r = Runner(ds, company_id="test-co", company_name="Auric",
                   cfg=Materiality(), memory_store=memory)
        bundles.append(r.run(metric, pa, pb))
    return bundles


def test_fixtures_reconcile(ds):
    assert ds.reconciliation.ok
    assert all(c["ok"] for c in ds.reconciliation.checks)


def test_lanes_are_append_only(runs):
    for bundle in runs:
        lanes = [b["lane"] for b in bundle["branches"]]
        assert lanes == sorted(lanes) == list(range(len(lanes)))


def test_top_level_shares_cover_the_move(runs):
    hero = runs[1]
    top = [b for b in hero["branches"] if b["depth"] == 0]
    assert abs(sum(abs(b["share"]) for b in top) - 1.0) < 0.02


def test_hero_run_explains_over_80_percent(runs):
    assert runs[1]["run"]["explained_share"] >= 0.80


def test_materiality_caps_small_lanes(runs):
    hero = runs[1]
    by_name = {b["name"]: b for b in hero["branches"]}
    assert by_name["Devices & Network"]["state"] == "capped"
    assert by_name["Subscriptions"]["state"] == "capped"
    assert by_name["Cloud"]["state"] == "done"


def test_drill_reaches_the_whales(runs):
    hero = runs[1]
    names = {b["name"] for b in hero["branches"]}
    assert {"Enterprise", "Mid-market", "SMB"} <= names
    assert {"Helios Dynamics", "VantaCore AI", "Corex Systems"} <= names


def test_branch_bridge_sums_to_branch_delta(runs):
    hero = runs[1]
    cloud = next(b for b in hero["branches"] if b["name"] == "Cloud")
    a = cloud["evidence"]["attribution"]
    total = a["price"] + a["volume"] + a["mix"] + a["customer"] + a["geo"] + a["fx"] + a["other"]
    assert abs(total - cloud["delta_abs"]) < 1.0  # rounding of the parts only


def test_kpi_reconciliation_reports_residual(runs):
    hero = runs[1]
    search = next(b for b in hero["branches"] if b["name"] == "Search Ads")
    kpi = search["evidence"]["kpi_reconciliation"]
    assert kpi["implied_pct"] == pytest.approx(16.4, abs=0.2)
    assert kpi["reported_pct"] == pytest.approx(16.8, abs=0.2)
    assert abs(kpi["residual"]) < 1.0


def test_memory_recall_and_promotion_across_runs(runs):
    background, hero, profit = runs
    assert background["recalled"] == []          # first run knows nothing
    assert len(hero["recalled"]) > 0             # second run recalls
    streaks = [h for h in hero["recalled"] if "consecutive" in h["text"]]
    assert streaks, "growth streak learned in run 1 must surface in run 2"
    assert hero["promoted"], "repeated concentration anomaly must promote"


def test_prior_explanation_stops_re_drilling(runs):
    profit = runs[2]
    revenue = next(b for b in profit["branches"] if b["name"] == "Revenue")
    assert "prior run" in (revenue["evidence"].get("drill_note") or "")
    # Revenue was NOT re-drilled: no product children under it
    assert not [b for b in profit["branches"]
                if b.get("parent_branch_id") == revenue["id"]]


def test_events_fold_forward_only(runs):
    for bundle in runs:
        beats = [e["payload"]["beat"] for e in bundle["events"]]
        assert beats == sorted(beats)
        ids = [e["id"] for e in bundle["events"]]
        assert ids == sorted(ids)


def test_every_claim_is_tagged(runs):
    tags = {"reported_fact", "calculated_attribution",
            "management_commentary", "agent_inference"}
    for bundle in runs:
        for b in bundle["branches"]:
            for claim in (b.get("evidence") or {}).get("claims", []):
                assert claim["tag"] in tags

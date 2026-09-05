"""Alphabet data/given pack: recon, Search identity, Cloud drill."""

from fpa.config import GIVEN_DIR, Materiality
from fpa.engine.given import load_given
from fpa.engine.router import route_branch
from fpa.engine.run import Runner
from fpa.memory.store import MemoryStore


def test_given_present():
    assert (GIVEN_DIR / "sec_metrics.csv").exists()


def test_given_reconciles():
    ds = load_given(GIVEN_DIR, company="Alphabet", name="t")
    assert ds.reconciliation.ok
    assert "2025-Q2" in ds.periods and "2026-Q2" in ds.periods


def test_cloud_drills_past_single_user_class():
    ds = load_given(GIVEN_DIR, company="Alphabet", name="t")
    routing = route_branch(ds, "product", "Cloud", "2025-Q2", "2026-Q2")
    assert routing is not None
    names = {c.name.lower() for c in routing.children}
    assert names & {"enterprise", "midmarket", "smb"}


def test_given_hero_run_explains():
    ds = load_given(GIVEN_DIR, company="Alphabet", name="t")
    bundle = Runner(
        ds, company_id="t", company_name="Alphabet",
        cfg=Materiality(), memory_store=MemoryStore(),
    ).run("Revenue", "2025-Q2", "2026-Q2")
    assert bundle["run"]["explained_share"] >= 0.80
    names = {b["name"] for b in bundle["branches"]}
    assert "Cloud" in names and "Search" in names
    assert any("enterprise" in n.lower() for n in names)

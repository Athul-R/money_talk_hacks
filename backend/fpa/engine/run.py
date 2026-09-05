"""The run orchestrator — one Run(metric, period_a, period_b) walked to the
materiality floor, streamed out as an append-only event log the console folds
into beats.

Graph contract (shared with the console): a branch is a lane, assigned once at
spawn in rank order and never re-sorted; children spawned by a drill append
BELOW existing lanes, indented one depth to the right. Every pip and event
carries the ids the console needs to grow the picture without re-layout.

The LLM appears exactly twice — narrate_branch and narrate_run — and both only
rephrase numbers the engine already computed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from ..agent import narrator
from ..agent.narrator import fm, pct
from ..config import Materiality
from ..memory import store as memory
from . import metric_graph
from .attribution import bridge as make_bridge
from .attribution import kpi_reconciliation
from .clustering import cluster_customers, concentration
from .materiality import Decision, decide
from .normalize import Dataset
from .router import Child, Routing, route, route_branch, route_customers
from .timeseries import delta_stats

Z_FLAG = 2.0
CONCENTRATION_FLAG = 0.33

STAGES = ["delta_z", "drivers", "cluster", "drill", "explain"]


def _uuid(ns: str, name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fpa:{ns}:{name}"))


class Runner:
    def __init__(self, ds: Dataset, *, company_id: str, company_name: str,
                 cfg: Materiality, memory_store: memory.MemoryStore,
                 run_id: str | None = None, writer=None,
                 started_at: datetime | None = None,
                 webctx: list[dict] | None = None):
        self.webctx = webctx or []  # live runs: sources from the web-search beat
        self.ds = ds
        self.company_id = company_id
        self.company_name = company_name
        self.cfg = cfg
        self.memory = memory_store
        self.writer = writer  # SupabaseWriter-shaped or None
        self.run_id = run_id or str(uuid.uuid4())
        self.clock = started_at or datetime.now(timezone.utc)

        self.branches: list[dict] = []
        self.pips: list[dict] = []
        self.events: list[dict] = []
        self.beat = 0
        self.recalled: list[dict] = []

    # ── plumbing ─────────────────────────────────────────────────────────

    def _tick(self) -> str:
        self.clock += timedelta(milliseconds=450 + (len(self.events) % 3) * 250)
        return self.clock.isoformat()

    def _emit(self, kind: str, *, title: str, detail: str, tag: str,
              caption: str | None = None, branch_id: str | None = None,
              node_id: str | None = None, chain: bool = False, **payload) -> dict:
        """One audit row. chain=True keeps the event inside the current beat."""
        if not chain:
            self.beat += 1
        event = {
            "id": len(self.events) + 1,
            "run_id": self.run_id,
            "branch_id": branch_id,
            "kind": kind,
            "at": self._tick(),
            "payload": {
                "beat": self.beat, "title": title, "detail": detail, "tag": tag,
                **({"caption": caption} if caption else {}),
                **({"node_id": node_id} if node_id else {}),
                **payload,
            },
        }
        self.events.append(event)
        if self.writer:
            self.writer.event(event)
        return event

    def _write_branch(self, row: dict) -> None:
        if self.writer:
            self.writer.branch({k: v for k, v in row.items() if k != "metric_series"})

    def _pip(self, branch: dict, stage: str, state: str, payload: dict) -> dict:
        row = {
            "id": _uuid(self.run_id, f"{branch['id']}:{stage}"),
            "branch_id": branch["id"],
            "stage": stage,
            "stage_idx": STAGES.index(stage) if stage in STAGES else len(STAGES),
            "state": state,
            "payload": payload,
            "at": self.clock.isoformat(),
        }
        self.pips.append(row)
        if self.writer:
            self.writer.pip(row)
        return row

    def _spawn(self, child: Child, parent: dict | None, depth: int) -> dict:
        lane = len(self.branches)
        row = {
            "id": _uuid(self.run_id, f"b{lane}"),
            "run_id": self.run_id,
            "parent_branch_id": parent["id"] if parent else None,
            "depth": depth,
            "dimension": child.dimension,
            "name": child.name,
            "lane": lane,
            "value_a": round(child.value_a, 2),
            "value_b": round(child.value_b, 2),
            "delta_abs": round(child.delta_abs, 2),
            "delta_pct": round((child.delta_abs / abs(child.value_a) * 100), 1)
            if child.value_a else None,
            "share": round(child.share, 3),
            "zscore": None,
            "state": "active",
            "evidence": {},
        }
        self.branches.append(row)
        self._write_branch(row)
        return row

    # ── series lookup per branch ─────────────────────────────────────────

    def _series(self, branch: dict, parent: dict | None, metric: str) -> dict[str, float]:
        dim, name = branch["dimension"], branch["name"]
        if dim == "line_item":
            s = self.ds.series(name, "total")
            if s:
                return s
            return {p: metric_graph.value(self.ds, name, p) or 0.0 for p in self.ds.periods}
        if dim in ("product", "geography", "user_type") and parent is None:
            return self.ds.series(metric, dim, name)
        if dim == "product":  # product split under a line_item (e.g. COGS by product)
            return self.ds.series(parent["name"] if parent else metric, "product", name)
        if dim == "user_type" and parent is not None:
            return self.ds.txn_series(**self._user_slice(parent["name"], name))
        if dim == "customer" and parent is not None:
            grand = self._parent_of(parent)
            product = grand["name"] if grand else parent["name"]
            return self.ds.txn_series(**self._user_slice(product, parent["name"]),
                                      customer_name=name)
        return {}

    def _parent_of(self, branch: dict) -> dict | None:
        pid = branch.get("parent_branch_id")
        return next((b for b in self.branches if b["id"] == pid), None)

    def _txn_filters(self, branch: dict, parent: dict | None) -> dict | None:
        """Transaction subset this branch owns, or None when txns don't apply."""
        dim, name = branch["dimension"], branch["name"]
        if dim == "product" and parent is None:
            return {"product": name}
        if dim == "user_type" and parent is not None:
            return self._user_slice(parent["name"], name)
        if dim == "customer" and parent is not None:
            grand = self._parent_of(parent)
            product = grand["name"] if grand else parent["name"]
            return {**self._user_slice(product, parent["name"]),
                    "customer_name": name}
        return None

    def _user_slice(self, product: str, name: str) -> dict[str, str]:
        """Resolve a user_type lane to the txn column that actually split it.
        Fixtures use customer_type (Enterprise/SMB); given CSVs use sub_product
        (enterprise/midmarket) because each product has one user_class."""
        df = self.ds.transactions
        if df is None or df.empty:
            return {"product": product, "customer_type": name}
        subset = df[df["product"] == product] if "product" in df.columns else df
        for key in ("customer_type", "sub_product", "geography"):
            if key in subset.columns and (subset[key].astype(str) == name).any():
                return {"product": product, key: name}
        return {"product": product, "customer_type": name}

    # ── the run ──────────────────────────────────────────────────────────

    def run(self, metric: str, period_a: str, period_b: str) -> dict:
        ds, cfg = self.ds, self.cfg
        created_at = self.clock.isoformat()

        root_series = ds.series(metric, "total") or {
            p: metric_graph.value(ds, metric, p) or 0.0 for p in ds.periods
        }
        root_stats = delta_stats(root_series, period_a, period_b)

        recon = ds.reconciliation
        self._emit(
            "run_started", node_id="root", tag="router",
            title="Run started",
            detail=f"{metric} · {period_a} → {period_b} · control totals "
                   f"{'✓' if recon.ok else '✗'}",
            caption=f"{metric} {pct(root_stats.delta_pct)} "
                    f"({fm(root_stats.delta_abs)}) — {period_a} → {period_b}",
            run={"id": self.run_id, "metric": metric, "period_a": period_a,
                 "period_b": period_b, "company": self.company_name,
                 "dataset": ds.name},
            root=root_stats.as_dict(),
            reconciliation={"ok": recon.ok, "checks": len(recon.checks)},
        )

        if self.webctx:
            q = self.webctx[0].get("query", f"{self.company_name} {metric} {period_b}")
            live = any(s.get("live") for s in self.webctx)
            self._emit(
                "web_context", node_id="root", tag="web",
                title="Web context gathered",
                detail=f"{len(self.webctx)} sources · "
                       + " · ".join(s["source"][:42] for s in self.webctx[:2]),
                caption=f"Searching the web: “{q}” — "
                        f"{len(self.webctx)} sources"
                        + ("" if live else " (cached index)"),
                sources=self.webctx,
            )

        routing = route(ds, metric, period_a, period_b)
        self._emit(
            "axis_selected", node_id="router", tag="router",
            title="Axis selected",
            detail=f"{routing.axis} — best explanatory power of "
                   f"{len(routing.candidates)} candidate axes",
            caption=f"Variance router: decomposing {metric} by {routing.axis}",
            axis=routing.axis, candidates=routing.candidates,
        )

        self.recalled = memory.recall(self.memory, self.company_id, metric,
                                      [c.name for c in routing.children])
        if self.recalled:
            self._emit(
                "memory_recalled", node_id="router", tag="memory",
                title="Memory recalled",
                detail=f"{len(self.recalled)} patterns from prior runs",
                caption="Recalling company memory — prior ranges, drivers, concentration",
                hits=[{"kind": h["kind"], "key": h["key"], "text": h["text"],
                       "runs": len(h["evidence_run_ids"])} for h in self.recalled],
            )

        rows = [self._spawn(c, None, 0) for c in routing.children]
        self._emit(
            "branch_ranked", node_id="router", tag="router",
            title="Branches ranked",
            detail=" · ".join(f"{r['name']} {r['share']:+.0%}" for r in rows[:4]),
            caption=f"{len(rows)} branches ranked by |Δ$| — absolute dollars, not % growth",
            branches=rows,
        )

        # `cursor` (positive-share running total) drives the stop rule; the
        # REPORTED explained share counts |contributions| so a cost bridge
        # (negative shares) still reports its true coverage.
        cursor = 0.0
        children_of = {c.name: c for c in routing.children}
        for row in rows:
            cursor += self._process(row, None, metric, period_a, period_b,
                                    children_of[row["name"]], cursor)
        explained = min(1.0, sum(abs(b["share"]) for b in self.branches
                                 if b["depth"] == 0 and b["state"] == "done"))

        learned = memory.learn(
            self.memory, self.company_id, self.run_id, ds, metric,
            period_a, period_b, self.branches,
            headline=narrator.headline(self._root_evidence(metric, period_a,
                                                           period_b, root_stats)),
        )
        self._emit(
            "memory_learned", node_id="outcome", tag="memory",
            title="Memory updated",
            detail=f"+{len(learned['learned'])} patterns"
                   + (f" · {len(learned['promoted'])} promoted to recurring"
                      if learned["promoted"] else ""),
            caption="Writing what this run learned back to company memory",
            **learned,
        )

        root_evidence = self._root_evidence(metric, period_a, period_b, root_stats)
        summary_md = narrator.narrate_run(
            {"metric": metric, "period_a": period_a, "period_b": period_b},
            root_evidence,
            self._branch_notes(),
            self.recalled,
            self._watchouts(metric, period_a, period_b),
        )
        outcome_claims = [
            {"text": f"{metric} {pct(root_stats.delta_pct)} ({fm(root_stats.delta_abs)}) "
                     f"from {period_a} to {period_b}.", "tag": "reported_fact"},
            *[{"text": f"{n['name']}: {n['headline']}", "tag": "calculated_attribution"}
              for n in self._branch_notes()[:3]],
        ]
        self._emit(
            "explanation_ready", node_id="outcome", tag="explain",
            title="Leadership summary ready",
            detail=f"{min(explained, 1.0):.0%} of the move explained",
            caption="Composing the leadership summary from the evidence tree",
            outcome=True, text=summary_md, claims=outcome_claims,
            evidence=root_evidence,
        )
        self._emit(
            "run_complete", node_id="outcome", tag="ok", chain=True,
            title="Run complete",
            detail=f"{metric} {period_a} → {period_b} · explained "
                   f"{min(explained, 1.0):.0%} · +{len(learned['learned'])} memories",
            summary_md=summary_md, explained_share=round(min(explained, 1.0), 3),
        )

        bundle = {
            "company": {"id": self.company_id, "name": self.company_name},
            "dataset": {"name": ds.name, "periods": ds.periods,
                        "reconciliation": recon.as_dict()},
            "run": {
                "id": self.run_id, "company": self.company_name, "dataset": ds.name,
                "metric": metric, "period_a": period_a, "period_b": period_b,
                "status": "complete", "summary_md": summary_md,
                "explained_share": round(min(explained, 1.0), 3),
                "thresholds": cfg.as_dict(), "beats": self.beat,
                "memory_delta": len(learned["learned"]),
                "promoted": len(learned["promoted"]),
                "created_at": created_at,
            },
            "branches": self.branches,
            "pips": self.pips,
            "events": self.events,
            "recalled": [{"kind": h["kind"], "text": h["text"]} for h in self.recalled],
            "learned": learned["learned"],
            "promoted": learned["promoted"],
            "memory_after": self.memory.for_company(self.company_id),
        }
        if self.writer:
            self.writer.run({
                "id": self.run_id, "company_id": self.company_id,
                "dataset_id": _uuid("dataset", ds.name), "metric": metric,
                "period_a": period_a, "period_b": period_b, "status": "complete",
                "beat": self.beat, "summary_md": summary_md,
            })
        return bundle

    # ── one branch, recursively ──────────────────────────────────────────

    def _process(self, row: dict, parent: dict | None, metric: str,
                 period_a: str, period_b: str, child: Child,
                 cumulative: float) -> float:
        cfg = self.cfg
        parent_delta = (parent or {"delta_abs": self.branches[0]["delta_abs"]})["delta_abs"]
        series = self._series(row, parent, metric)
        stats = delta_stats(series, period_a, period_b) if series else None

        parent_total = sum(abs(b["delta_abs"]) for b in self.branches
                           if b.get("parent_branch_id") == row.get("parent_branch_id")
                           and b["depth"] == row["depth"]) or 1.0
        if child.capped:
            decision = Decision(
                "cap", False,
                f"aggregate of accounts individually below the "
                f"{cfg.min_share:.0%} floor")
        else:
            decision = decide(
                cfg, share=row["share"], delta_abs=row["delta_abs"],
                parent_delta_abs=parent_total, cumulative_explained=cumulative,
                depth=row["depth"],
                has_children_data=self._can_drill(row, parent),
            )
        if decision.action == "process" and stats is None:
            decision = Decision("cap", False, "no period series available")

        if decision.action == "cap":
            payload = {"reason": decision.reason,
                       **({"stats": stats.as_dict()} if stats else {})}
            pip = self._pip(row, "delta_z", "capped", payload)
            row["state"] = "capped"
            if stats:
                row["zscore"] = payload["stats"]["zscore"]
            self._write_branch(row)
            self._emit(
                "branch_capped", branch_id=row["id"], node_id=pip["id"], tag="capped",
                title="Branch capped",
                detail=f"{row['name']} — {decision.reason}",
                caption=f"{row['name']} capped: {decision.reason}",
                pip=pip, reason=decision.reason,
            )
            return 0.0

        # 3a — delta + z-score
        assert stats is not None
        row["zscore"] = stats.as_dict()["zscore"]
        flagged = stats.zscore is not None and abs(stats.zscore) >= Z_FLAG
        pip = self._pip(row, "delta_z", "done", {**stats.as_dict(), "flagged": flagged})
        self._emit(
            "zscore_flagged", branch_id=row["id"], node_id=pip["id"], tag="z",
            title="Δ measured" + (" — z-score flag" if flagged else ""),
            detail=f"{row['name']}: {fm(stats.delta_abs)} ({pct(stats.delta_pct)})"
                   + (f" · z {stats.zscore:+.1f}" if stats.zscore is not None else ""),
            caption=f"{row['name']}: {pct(stats.delta_pct)} vs trailing mean "
                    f"{pct(stats.trailing_mean_pct)}"
                    + (" — outside the normal band" if flagged else ""),
            pip=pip, flagged=flagged,
        )

        # 3b — driver bridge + KPI reconciliation
        bridge_dict = None
        kpi = None
        per_customer: list[dict] = []
        filters = self._txn_filters(row, parent)
        if filters:
            txn_a = self.ds.txns(period_a, **filters)
            txn_b = self.ds.txns(period_b, **filters)
            if not txn_a.empty or not txn_b.empty:
                b = make_bridge(txn_a, txn_b)
                bridge_dict = b.as_dict()
                per_customer = b.per_customer
        # KPI identities (clicks × cpc, subscribers × arpu) compare against
        # REPORTED REVENUE — only revenue product branches may carry them.
        revenue_context = (parent is None and metric == "Revenue") or (
            parent is not None and parent["name"] == "Revenue")
        if row["dimension"] == "product" and revenue_context:
            kpi = kpi_reconciliation(self.ds, row["name"], period_a, period_b)
        if bridge_dict or kpi:
            payload = {"bridge": bridge_dict, "kpi_reconciliation": kpi,
                       "customers": len(per_customer)}
            pip = self._pip(row, "drivers", "done", payload)
            top = (bridge_dict or {}).get("top_driver", "")
            detail = f"{row['name']}: {top}-led" if top else f"{row['name']}: KPI identity"
            if kpi:
                detail += (f" · implied {pct(kpi['implied_pct'])} vs "
                           f"{pct(kpi['reported_pct'])} reported")
            self._emit(
                "attribution_done", branch_id=row["id"], node_id=pip["id"], tag="drivers",
                title="Drivers attributed", detail=detail,
                caption=f"{row['name']}: price/volume/mix/customer bridge computed",
                pip=pip,
            )

        # 3c — transaction clusters + concentration
        clusters: list[dict] = []
        conc = None
        if len(per_customer) >= 4:
            clusters = cluster_customers(per_customer, row["delta_abs"],
                                         k=min(3, len(per_customer)))
            conc = concentration(per_customer, row["delta_abs"], cfg.top_n_customers)
            pip = self._pip(row, "cluster", "done",
                            {"clusters": clusters, "concentration": conc})
            top_cluster = clusters[0] if clusters else None
            self._emit(
                "cluster_found", branch_id=row["id"], node_id=pip["id"], tag="cluster",
                title="Clusters found",
                detail=(f"{row['name']}: “{top_cluster['label']}” = "
                        f"{top_cluster['share']:.0%} of Δ" if top_cluster
                        else f"{row['name']}: no dominant cluster"),
                caption=f"{row['name']}: grouping the transactions behind the delta",
                pip=pip,
            )
            if conc and abs(conc["top_n_share"]) >= CONCENTRATION_FLAG:
                self._emit(
                    "concentration_flagged", branch_id=row["id"], node_id=pip["id"],
                    tag="cluster", chain=True,
                    title="Concentration flagged",
                    detail=f"top {conc['top_n']} = {conc['top_n_share']:.0%} of "
                           f"{row['name']} Δ ({', '.join(conc['top_names'])})",
                    concentration=conc,
                )

        # 3d — drill (or explain why not)
        memory_hits = [h["text"] for h in self.recalled
                       if h["value"].get("segment") == row["name"]
                       or h["value"].get("metric") == row["name"]]
        drill_note = None
        prior = self.memory.get(self.company_id, "explanation",
                                f"run:{row['name']}:{period_a}:{period_b}")
        should_drill = decision.drill
        if prior is not None:
            should_drill = False
            drill_note = (f"already explained in a prior run "
                          f"({prior['value'].get('headline', 'see memory')})")
            memory_hits.append(memory.humanize(prior))

        if should_drill:
            child_routing = self._drill_routing(row, parent, period_a, period_b)
            if child_routing and child_routing.children:
                child_rows = [self._spawn(c, row, row["depth"] + 1)
                              for c in child_routing.children]
                pip = self._pip(row, "drill", "done", {
                    "axis": child_routing.axis,
                    "children": [{"id": r["id"], "name": r["name"],
                                  "share": r["share"]} for r in child_rows],
                    "reason": decision.reason,
                })
                self._emit(
                    "drill_spawned", branch_id=row["id"], node_id=pip["id"], tag="drill",
                    title="Drill spawned",
                    detail=f"{row['name']} → {child_routing.axis}: "
                           + ", ".join(r["name"] for r in child_rows[:4]),
                    caption=f"Drilling {row['name']} by {child_routing.axis} — "
                            f"share {abs(row['share']):.0%} ≥ floor, depth {row['depth'] + 1}",
                    pip=pip, children=child_rows, axis=child_routing.axis,
                )
                child_cum = 0.0
                kids = {c.name: c for c in child_routing.children}
                for child_row in child_rows:
                    child_cum += self._process(child_row, row, metric,
                                               period_a, period_b,
                                               kids[child_row["name"]], child_cum)
        elif decision.drill is False and drill_note is None and row["depth"] < cfg.max_depth:
            drill_note = decision.reason

        # 3e — explain
        evidence = {
            "metric": metric if parent is None else parent["name"],
            "dimension": row["dimension"], "name": row["name"],
            "period_a": period_a, "period_b": period_b,
            **stats.as_dict(),
            "share_of_parent_variance": row["share"],
            "attribution": bridge_dict,
            "kpi_reconciliation": kpi,
            "clusters": clusters,
            "concentration": conc,
            "memory_hits": memory_hits,
            "drill_note": drill_note,
            "children": [b["id"] for b in self.branches
                         if b.get("parent_branch_id") == row["id"]],
        }
        note = narrator.narrate_branch(evidence, [{"text": t} for t in memory_hits])
        if drill_note:
            note["claims"].append({"text": f"Not drilled further: {drill_note}.",
                                   "tag": "agent_inference"})
        evidence["claims"] = note["claims"]
        row["evidence"] = evidence
        row["state"] = "done"
        self._write_branch(row)
        pip = self._pip(row, "explain", "done", {
            "text": note["text"], "claims": note["claims"],
            "memory_hits": memory_hits, "llm": note["llm"],
        })
        self._emit(
            "explanation_ready", branch_id=row["id"], node_id=pip["id"], tag="explain",
            title="Explanation ready",
            detail=f"{row['name']}: {narrator.headline(evidence)}",
            caption=f"{row['name']} explained — {len(note['claims'])} tagged claims",
            pip=pip, text=note["text"], claims=note["claims"],
            memory_hits=memory_hits,
        )
        return max(row["share"], 0.0)

    # ── helpers ──────────────────────────────────────────────────────────

    def _can_drill(self, row: dict, parent: dict | None) -> bool:
        return self._drill_routing(row, parent, self.ds.periods[0],
                                   self.ds.periods[-1], probe=True) is not None

    def _drill_routing(self, row: dict, parent: dict | None, period_a: str,
                       period_b: str, probe: bool = False) -> Routing | None:
        dim = row["dimension"]
        if dim == "product" and parent is not None and parent["dimension"] == "line_item":
            # A cost line's product split (COGS · Cloud) explains at this level;
            # the transactions carry revenue, not cost, so drilling them would
            # silently swap metrics. Hard stop.
            return None
        if dim in ("product", "line_item"):
            return route_branch(self.ds, dim, row["name"], period_a, period_b)
        if dim == "user_type" and parent is not None:
            return route_customers(self.ds, parent["name"], row["name"],
                                   period_a, period_b, self.cfg.min_share)
        return None

    def _root_evidence(self, metric: str, period_a: str, period_b: str,
                       stats) -> dict:
        top = [b for b in self.branches if b["depth"] == 0]
        return {
            "metric": metric, "dimension": "total", "name": metric,
            "period_a": period_a, "period_b": period_b,
            **stats.as_dict(),
            "share_of_parent_variance": 1.0,
            "waterfall": [{"name": b["name"], "delta": b["delta_abs"],
                           "share": b["share"]} for b in top],
            "children": [b["id"] for b in top],
        }

    def _branch_notes(self) -> list[dict]:
        notes = []
        for b in self.branches:
            if b["depth"] != 0 or b["state"] == "capped":
                continue
            ev = b.get("evidence", {})
            driver_lines = []
            attribution = ev.get("attribution") or {}
            if attribution.get("top_driver"):
                t = attribution["top_driver"]
                driver_lines.append(
                    f"{b['name']}: {t} {fm(attribution.get(t))} of {fm(b['delta_abs'])}")
            kpi = ev.get("kpi_reconciliation")
            if kpi:
                driver_lines.append(
                    f"{b['name']}: {kpi['volume_kpi']} {pct(kpi['volume_pct'])} × "
                    f"{kpi['price_kpi']} {pct(kpi['price_pct'])} ≈ "
                    f"{pct(kpi['implied_pct'])} (reported {pct(kpi['reported_pct'])})")
            conc = ev.get("concentration")
            if conc:
                driver_lines.append(
                    f"{b['name']}: top {conc['top_n']} accounts = "
                    f"{conc['top_n_share']:.0%} of the segment move")
            notes.append({
                "name": b["name"], "share": b["share"], "delta_abs": b["delta_abs"],
                "headline": narrator.headline(ev) if ev else "",
                "driver_lines": driver_lines,
            })
        return notes

    def _watchouts(self, metric: str, period_a: str, period_b: str) -> list[str]:
        out = []
        capex_a = metric_graph.value(self.ds, "CapEx", period_a)
        capex_b = metric_graph.value(self.ds, "CapEx", period_b)
        if capex_a and capex_b and (capex_b / capex_a - 1) > 0.25:
            line = (f"CapEx {pct((capex_b / capex_a - 1) * 100)} to {fm(capex_b)}")
            fcf_a = metric_graph.value(self.ds, "Free cash flow", period_a)
            fcf_b = metric_graph.value(self.ds, "Free cash flow", period_b)
            if fcf_a and fcf_b is not None:
                line += (f"; free cash flow {fm(fcf_b)} "
                         f"({pct((fcf_b / fcf_a - 1) * 100)}) despite the operating move")
            out.append(line)
        for b in self.branches:
            conc = (b.get("evidence") or {}).get("concentration")
            if conc and conc["top_n_share"] >= 0.5:
                out.append(f"{b['name']} growth rides on {conc['top_n']} accounts "
                           f"({conc['top_n_share']:.0%} of the move) — retention risk")
            if b.get("zscore") and abs(b["zscore"]) >= 2.5 and b["state"] != "capped":
                out.append(f"{b['name']} moved {abs(b['zscore']):.1f}σ outside its "
                           f"trailing band — verify durability before annualizing")
        return out[:4]

"""FastAPI for the live console path.

    GET  /health
    GET  /catalog          seeded Alphabet project + past live runs
    POST /datasets         upload sec/product/geo/user CSVs (or summaries pack)
    POST /runs             run the engine, return the same bundle the mock uses
    GET  /runs/{id}        replay a stored live run
    POST /runs/{id}/ask    scoped follow-up (templated unless LLM key is set)
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..agent import narrator, webctx
from ..agent.providers import SESSION_ID
from ..config import GIVEN_DIR, Materiality, STATE_DIR
from ..data.stores import LocalStore
from ..engine.given import load_given
from ..engine.normalize import load as load_pack
from ..engine.run import Runner
from ..memory.store import MemoryStore, humanize
from .. import observe

app = FastAPI(title="Delta Ledger", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

store = LocalStore()
memory = MemoryStore(store.load_memory())
COMPANY_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "fpa:company:alphabet"))
SEED_ID = "alphabet-given"

GIVEN_FILES = ("sec_metrics.csv", "product_segments.csv", "geography.csv", "user_segments.csv")
PACK_FILES = ("summaries.csv", "transactions.csv", "dimensions.json")


def _load_dataset(dataset_id: str):
    if dataset_id == SEED_ID:
        if not (GIVEN_DIR / "sec_metrics.csv").exists():
            raise HTTPException(404, "data/given/ is missing — pull the repo")
        return load_given(GIVEN_DIR, company="Alphabet", name="alphabet-given")
    d = store.dataset_dir(dataset_id)
    if (d / "sec_metrics.csv").exists():
        return load_given(d, company="Alphabet", name=dataset_id)
    if (d / "summaries.csv").exists():
        return load_pack(d, name=dataset_id)
    raise HTTPException(404, f"unknown dataset {dataset_id}")


def _index_run(bundle: dict) -> dict:
    run = bundle["run"]
    return {
        "id": run["id"], "file": run["id"], "metric": run["metric"],
        "period_a": run["period_a"], "period_b": run["period_b"],
        "status": run["status"], "explained_share": run["explained_share"],
        "memory_delta": run.get("memory_delta", 0),
        "recalled": len(bundle.get("recalled") or []),
        "promoted": run.get("promoted", 0),
        "created_at": run["created_at"], "beats": run["beats"],
        "source": "live",
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "given": (GIVEN_DIR / "sec_metrics.csv").exists(),
        "prism": observe.enabled(),
        "llm": bool(__import__("os").getenv("LLM_API_KEY")),
    }


@app.get("/catalog")
def catalog():
    ds = None
    recon = {"ok": False, "checks": []}
    periods = []
    try:
        ds = _load_dataset(SEED_ID)
        recon = ds.reconciliation.as_dict()
        periods = ds.periods
    except HTTPException:
        pass
    runs = []
    for row in store.list_runs():
        bundle = store.load_run(row["id"])
        if bundle:
            runs.append(_index_run(bundle))
    uploaded = store.list_datasets()
    return {
        "company": {"id": COMPANY_ID, "name": "Alphabet"},
        "dataset": {
            "id": SEED_ID, "name": "alphabet-given",
            "periods": periods, "reconciliation": recon,
            "files": list(GIVEN_FILES),
        },
        "datasets": [
            {
                "id": SEED_ID, "name": "Alphabet · given (data/given)",
                "periods": periods, "reconciliation": recon,
                "files": list(GIVEN_FILES), "seed": True,
            },
            *uploaded,
        ],
        "runs": runs,
        "memory": [{**r, "text": r.get("text") or humanize(r)}
                   for r in memory.for_company(COMPANY_ID)],
        "prism": observe.enabled(),
        "metrics": ["Revenue", "Operating income", "Gross profit", "Free cash flow"],
    }


@app.post("/datasets")
async def upload_dataset(
    files: list[UploadFile] = File(...),
    company: str = Form("Alphabet"),
    name: str = Form(""),
):
    dataset_id = str(uuid.uuid4())[:8]
    dest = store.dataset_dir(dataset_id)
    saved = []
    for f in files:
        if not f.filename:
            continue
        path = dest / Path(f.filename).name
        path.write_bytes(await f.read())
        saved.append(path.name)
    names = set(saved)
    if set(GIVEN_FILES) <= names:
        ds = load_given(dest, company=company, name=name or dataset_id)
    elif set(PACK_FILES) <= names:
        ds = load_pack(dest, name=name or dataset_id)
    else:
        shutil.rmtree(dest, ignore_errors=True)
        raise HTTPException(400, f"need {GIVEN_FILES} or {PACK_FILES}; got {saved}")
    meta = {
        "id": dataset_id, "name": ds.name, "company": company,
        "periods": ds.periods, "reconciliation": ds.reconciliation.as_dict(),
        "files": saved,
    }
    (dest / "meta.json").write_text(__import__("json").dumps(meta, indent=2))
    return meta


class RunReq(BaseModel):
    dataset_id: str = SEED_ID
    metric: str = "Revenue"
    period_a: str = "2025-Q2"
    period_b: str = "2026-Q2"
    company: str = "Alphabet"


@app.post("/runs")
def start_run(req: RunReq):
    ds = _load_dataset(req.dataset_id)
    if req.period_a not in ds.periods or req.period_b not in ds.periods:
        raise HTTPException(400, f"periods must be in {ds.periods}")
    run_id = str(uuid.uuid4())
    SESSION_ID.set(run_id)
    sources = webctx.gather(req.company, req.metric, req.period_b, seed=run_id)
    runner = Runner(
        ds, company_id=COMPANY_ID, company_name=req.company,
        cfg=Materiality(), memory_store=memory, run_id=run_id,
        webctx=sources,
    )
    bundle = runner.run(req.metric, req.period_a, req.period_b)
    bundle["run"]["dataset_id"] = req.dataset_id
    store.save_run(bundle)
    store.save_memory(memory.rows)
    observe.trace_run(bundle)
    return bundle


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    bundle = store.load_run(run_id)
    if not bundle:
        raise HTTPException(404, "run not found")
    return bundle


class AskReq(BaseModel):
    branch_id: str
    question: str


@app.post("/runs/{run_id}/ask")
def ask(run_id: str, req: AskReq):
    bundle = store.load_run(run_id)
    if not bundle:
        raise HTTPException(404, "run not found")
    branch = next((b for b in bundle["branches"] if b["id"] == req.branch_id), None)
    if not branch:
        raise HTTPException(404, "branch not found")
    SESSION_ID.set(run_id)
    hits = [{"text": h["text"]} for h in bundle.get("recalled") or []]
    answer = narrator.answer_followup(req.question, branch.get("evidence") or {}, hits)
    return {"branch_id": req.branch_id, "question": req.question, **answer}

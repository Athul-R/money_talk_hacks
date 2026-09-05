# Delta Ledger — Explain the Change

Delta Ledger is a live FP&A analysis agent that answers the question behind
every close: **“Why did this number move?”** Upload a company’s quarterly
books and watch an auditable explanation grow from reported total to business
driver, operating mechanism, account concentration, and leadership memo.

Built for the **Maximor — Money Operations — Explain the Change** track.

## Problem statement

Finance teams spend days reconciling SEC metrics, product tables, geography
splits, and user-level books before they can explain one quarterly movement.
Traditional dashboards show *what* changed but not *why*. Asking a general LLM
to perform the analysis is unsafe: plausible arithmetic can fail to tie back to
reported totals, and leadership cannot audit the answer.

## Our solution

Delta Ledger separates calculation from language:

- A **deterministic evidence engine** owns every number. It validates the
  uploaded schema, reconciles control totals, ranks movers by absolute dollars,
  calculates trailing-band z-scores, builds exact price/volume/mix bridges,
  identifies concentration, and drills until the material movement is covered.
- An **LLM narrator** receives only completed evidence JSON. It can explain the
  findings, but it cannot invent or alter arithmetic.
- A **live lineage console** exposes the decision path. Leaders can start with
  a six-node overview; finance and audit teams can switch to every z-score,
  bridge, cluster, drill, and evidence claim.
- A **structured leadership brief** turns the run into a board-ready readout
  with key metrics, ranked drivers, watch-outs, company memory, and an evidence
  book.

## Key features

- **Upload to analysis:** upload a quarterly company ledger and automatically
  run reconciliation, web context gathering, routing, attribution, drilling,
  narration, memory compilation, and persistence.
- **Two live lineage levels:**
  - **High level:** Reconcile → Context → Router → Top movers → Evidence →
    Explained.
  - **Detailed audit:** every branch and stage, including z-bridge, dollar
    bridge, clustering, materiality decisions, and tagged narration.
- **Explainable materiality:** branches rank by `|Δ$|`, never percentage
  growth. The engine stops at 80% explained, below a 5% share, or at depth 4.
- **Operational identities:** Search revenue is checked against
  `paid clicks × CPC`; formula residuals are shown rather than hidden.
- **Web context:** Tavily retrieves period-relevant earnings commentary.
  External context is labeled and never changes calculated values.
- **Company memory:** prior ranges, streaks, seasonality, explanations, and
  concentration patterns are compiled at write time and recalled on later runs.
- **PRISM observability:** narration calls become traces and each completed
  analysis becomes an agent trajectory for Observe → Improve → Prove.
- **Evidence-scoped follow-ups:** questions on any lineage node can use only
  that node’s computed evidence.
- **Leadership brief:** an in-product board brief plus a secondary Markdown
  export for sharing.

## Tech stack

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, React Flow,
  Recharts, Lucide.
- **Backend:** Python 3.12, FastAPI, pandas, NumPy, httpx, uv.
- **Agent layer:** provider-agnostic OpenAI, Anthropic, or Gemini narration
  with a deterministic text fallback.
- **External context:** Tavily Search.
- **Agent observability:** PRISM through `prismtrace-sdk`.
- **Persistence:** local run and dataset store, compiled memory, optional
  Supabase writer, and a Supabase realtime schema.
- **Development:** GLIDE generative IDE.

## How it works

![Delta Ledger architecture](docs/assets/architecture.png)

### 1. Reconcile — do the books add up?

The uploaded files are normalized into one company dataset. Required columns
are validated and transaction-level revenue is compared with reported totals
at a 0.5% tolerance. The analysis records every control-total check.

### 2. Context — what was happening outside the books?

Tavily gathers period-relevant earnings sources. These sources support
management context in the narrative, but remain isolated from the arithmetic.

### 3. Router — who owns the move?

The engine scores each available decomposition axis. The winning axis is the
one whose largest children capture the movement with useful granularity:

```text
power(axis) = top-3 absolute-share capture × (1 - 1 / max(child_count, 2))
```

Children are permanently ranked by absolute dollar movement.

### 4. Z-bridge — is the move unusual?

Each material branch is compared with its own trailing growth distribution.
A z-score outside ±2 highlights movement outside the historical band.

### 5. Dollar bridge — what mechanically caused it?

The engine decomposes the movement into exact components:

```text
price    = units_A × (price_B - price_A)
volume   = price_A × (units_B - units_A)
mix      = (units_B - units_A) × (price_B - price_A)
customer = new-customer revenue - churned-customer revenue
```

It also computes KPI residuals, transaction clusters, and top-account
concentration.

### 6. Drill — how deep is material?

The lineage proceeds from product to user segment to account or geography.
Branches below materiality are capped and remain visible in the audit trail.

### 7. Narrate, remember, and prove

The engine emits evidence JSON. The narrator rephrases it with one of four
provenance tags: `reported_fact`, `calculated_attribution`,
`management_commentary`, or `agent_inference`. Company memory is compiled,
the run is persisted, and PRISM receives traces plus the completed trajectory.

The end-to-end path is:

```text
Quarterly books
  → FastAPI
  → normalize + reconcile
  → Tavily context
  → route by |Δ$|
  → z-score + exact bridge
  → cluster + materiality drill
  → evidence JSON
  → tagged narration
  → company memory + PRISM
  → executive brief + live lineage
```

For the component-level architecture, see
[docs/architecture.md](docs/architecture.md) or open **Architecture** in the
console.

## How to run

Requirements: Python 3.12, Node.js, npm, and
[uv](https://docs.astral.sh/uv/).

Install:

```bash
make install
```

Start the backend:

```bash
make api
```

Start the console in a second terminal:

```bash
make live
```

Open [http://localhost:5173](http://localhost:5173).

Optional `.env` integrations:

```dotenv
PRISMTRACE_API_KEY=pt-sk-...
PRISMTRACE_PROJECT_ID=<project-uuid>
PRISMTRACE_HOST=https://prism.blockconvey.com

TAVILY_API_KEY=...

LLM_PROVIDER=openai
LLM_API_KEY=...
LLM_MODEL=
```

The calculation engine remains operational without these optional keys.

## How to use it

1. Open the console and upload the company’s quarterly books.
2. Delta Ledger validates and reconciles the dataset.
3. The executive summary appears while the analysis steps are revealed.
4. Open the leadership brief for the board-ready readout.
5. Open the closer and choose:
   - **High level** for the six-step business explanation.
   - **Detailed audit** for every calculation and recursive drill.
6. Click a driver or stage for its charts, evidence, and follow-up question.
7. Open **PRISM** to inspect the agent decision trail and project traces.
8. Select a prior run or start a new metric/period analysis from the run rail.

## Input data

The current company ledger uses four related CSVs:

- `sec_metrics.csv` — reported P&L and cash-flow totals.
- `product_segments.csv` — product revenue and direct cost.
- `geography.csv` — geographic revenue.
- `user_segments.csv` — segment-level revenue and operating KPIs.

The included dataset covers eight quarters and supports Revenue, Operating
income, Gross profit, and Free cash flow analyses.

## Verification and safeguards

- 37 automated tests cover reconciliation, attribution identities,
  materiality gates, z-scores, customer clustering, memory promotion, and
  end-to-end runs.
- The LLM is never invoked inside routing, attribution, materiality, or memory
  compilation.
- Every run stores its thresholds, evidence, branches, pips, and append-only
  events.
- Every visible number comes from the deterministic engine.

Run the checks:

```bash
make test
make build
```

Seed the configured PRISM project with one complete analysis:

```bash
make prism-warmup
```

## Repository structure

```text
backend/
  fpa/api/       dataset upload, runs, prior-run retrieval, follow-ups
  fpa/engine/    reconciliation, router, z-score, bridge, cluster, drill
  fpa/agent/     evidence narrator, LLM providers, Tavily context
  fpa/memory/    recall, compile, and recurring-pattern promotion
  fpa/observe.py PRISM traces and trajectories
  tests/         deterministic engine verification

console/
  src/components/ landing, executive summary, memo, lineage, drawers, PRISM
  src/lib/fold.ts append-only events → visible analysis state
  src/lib/frame.ts high-level and detailed lineage geometry

data/
  given/         company ledger
  schema.sql     optional Supabase persistence and realtime schema

docs/
  architecture.md
  assets/
```

## Core design rules

1. The LLM never performs arithmetic.
2. Absolute dollars rank branches.
3. The graph only grows; a lane never changes position.
4. Memory is compiled at write time and read as plain rows.
5. External context can explain a result but cannot modify it.

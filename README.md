# Causal FP&A Agent

Executive revenue briefs from SEC / product / geography / user-segment data:
time-series Z-scores → delta attribution → driver clusters → LLM summary
(optional LangChain writer↔validator loop).

## Layout

```text
src/fpa_agent/          # installable package
  agent/                # pipeline, LLM, LangChain loop, validator
  analytics/            # z-score, attribution, clustering
  metrics/              # hierarchy + input schemas
data/given/             # input CSVs (assumed provided)
scripts/                # fixture helpers
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env   # set ANTHROPIC_API_KEY
```

## Run

```bash
# Fast path (analytics + executive brief)
fpa-agent --period 2026-Q2 --prior-period 2025-Q2

# LangChain agent loop (passes only if validator succeeds)
fpa-agent --period 2026-Q2 --prior-period 2025-Q2 --agent-loop

# Or module form
python -m fpa_agent --period 2026-Q2 --prior-period 2025-Q2
```

Put given CSVs in `data/given/` (`sec_metrics`, `product_segments`, `geography`, `user_segments`).

# Explain the Change — one command per stage of the demo.
# Backend commands run through uv (https://docs.astral.sh/uv) with Python 3.12.

BACKEND := cd backend && uv run --

.PHONY: install fixtures test mock run-demo console build api live prism-warmup

install:            ## backend venv + console node_modules
	cd backend && uv sync
	cd backend && uv pip install prismtrace-sdk || true
	cd console && npm install

fixtures:           ## regenerate the calibrated fixture CSVs
	$(BACKEND) python fixtures/generate.py

test:               ## engine test suite (attribution math, materiality stops, z-scores)
	$(BACKEND) pytest tests -q

mock:               ## run the engine on fixtures and bake beats into console/src/mock
	$(BACKEND) python scripts/make_mock.py

run-demo: mock      ## mock path: baked beats, no keys
	cd console && npm run dev

api:                ## live FastAPI on :8000 (data/given seeded)
	cd backend && uv run uvicorn fpa.api.main:app --reload --port 8000

live:               ## console only — pair with `make api` in another terminal
	cd console && npm run dev

prism-warmup:       ## one given-data run so PRISM has traces tomorrow
	$(BACKEND) env PYTHONPATH=. python scripts/prism_warmup.py

console:            ## console dev server on :5173
	cd console && npm run dev

build:              ## typecheck + production build of the console
	cd console && npm run build

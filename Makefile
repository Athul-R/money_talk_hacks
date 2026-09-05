# Explain the Change — one command per stage of the demo.
# Backend commands run through uv (https://docs.astral.sh/uv) with Python 3.12.

BACKEND := cd backend && uv run --

.PHONY: install fixtures test mock run-demo console build

install:            ## backend venv + console node_modules
	cd backend && uv sync
	cd console && npm install

fixtures:           ## regenerate the calibrated fixture CSVs
	$(BACKEND) python fixtures/generate.py

test:               ## engine test suite (attribution math, materiality stops, z-scores)
	$(BACKEND) pytest tests -q

mock:               ## run the engine on fixtures and bake beats into console/src/mock
	$(BACKEND) python scripts/make_mock.py

run-demo: mock      ## end-to-end demo without any keys: engine -> beats -> console
	cd console && npm run dev

console:            ## console dev server on :5173
	cd console && npm run dev

build:              ## typecheck + production build of the console
	cd console && npm run build

# BustGuard - make targets (works with GNU make on Linux/macOS and Windows + Git Bash)
#   make fetch          download data (WeatherBench 2 India subset, resumable, byte-capped)
#   make dataset        build the training table          (SOURCE=wb2 | synthetic | open_meteo)
#   make train          train LightGBM + baseline
#   make eval           model vs baseline report -> docs/results*.md
#   make export         API payloads (predictions, reasons, analogs, replay events)
#   make api / web      run the FastAPI backend / React dashboard
#   make demo           export (if needed) and run api + web together
#   make synthetic      full pipeline on clearly-labelled SYNTHETIC data
SOURCE ?= wb2
UV     ?= uv
PY      = cd backend && $(UV) run python

.PHONY: setup fetch fetch-dry dataset train eval export pipeline synthetic api web demo test lint fmt scan

setup:
	cd backend && $(UV) sync --group dev
	cd frontend && npm install

fetch:
	$(PY) -m pipelines.fetch --source $(SOURCE)

fetch-dry:
	$(PY) -m pipelines.fetch --source $(SOURCE) --dry-run

dataset:
	$(PY) -m pipelines.dataset --source $(SOURCE)

train:
	$(PY) -m pipelines.train --source $(SOURCE)

eval:
	$(PY) -m pipelines.evaluate --source $(SOURCE)

export:
	$(PY) -m pipelines.export --source $(SOURCE)

pipeline: dataset train eval export

synthetic:
	$(MAKE) pipeline SOURCE=synthetic

api:
	cd backend && $(UV) run uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

demo:
	$(PY) -m pipelines.demo

test:
	cd backend && $(UV) run pytest -q

lint:
	cd backend && $(UV) run ruff check . && $(UV) run ruff format --check .
	cd frontend && npm run lint

fmt:
	cd backend && $(UV) run ruff check . --fix && $(UV) run ruff format .

scan:
	$(PY) ../scripts/scan_repo.py

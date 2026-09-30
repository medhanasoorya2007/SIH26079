# BustGuard: AI-based forecast bust detection

**SIH26079 · Ministry of Earth Sciences / NCMRWF.** Medium-range forecasts fail most during
fast-evolving systems: monsoon depressions, heavy rainfall, western disturbances, cyclones,
heat waves, and active/break transitions. BustGuard does not forecast the weather again. It
predicts **when an existing NWP forecast is likely to fail**, where, and why.

For each region and lead day (Day 1–10), BustGuard outputs:

1. **Forecast confidence map**: region-wise, per lead day.
2. **Bust probability**: a calibrated per-region probability, plus an operational risk level.
3. **Error-prone areas**: a ranked list of the regions most likely to bust.
4. **Explanations**: the top-3 meteorological reasons, written in plain language.
5. **Dashboard and API**: FastAPI and a React forecaster console with a replay of real past busts.

> **Status:** the pipeline runs end to end. Real WeatherBench 2 data is downloading, and
> results on real data will appear in [`docs/results.md`](docs/results.md).
> [`docs/results_synthetic.md`](docs/results_synthetic.md) is **synthetic** and only
> checks the plumbing.

## How it works

```
 WeatherBench 2 (ECMWF HRES, GraphCast)   ERA5 truth (+ IMD optional)
                 │                               │
                 └────────► training table ◄─────┘  one row per init × region × lead day
                                 │
            bust labels  (lead-specific 95th-percentile error | IMD category flip)
                                 │
   signals (one file each): model disagreement · run-to-run jumps · regime tags
   (depression, cyclone, active/break, WD, heavy rain) · synoptic MSLP + geostrophic
   vorticity · neighbourhood gradients · recent error history · analog search (kNN)
                                 │
     LightGBM (class-weighted, year-based split, isotonic calibration)  vs  baseline
                                 │
          TreeSHAP ─► top-3 plain-English reasons     analogs ─► similar past cases
                                 │
                  FastAPI  ─►  React console (map · drawer · evidence · replay)
```

- **Baseline:** "large disagreement means low confidence", scored as HRES-vs-GraphCast disagreement and calibrated per lead day on the training years. A true ensemble-spread baseline is supported (`baseline.score_column`), but the ENS members were not downloaded (see [`docs/data.md`](docs/data.md)).
- **Headline metric:** the share of busts caught at the same false-alarm rate, on a held-out year.

## Quick start

Requirements: Python 3.11 with [uv](https://docs.astral.sh/uv/), and Node 20+.

```bash
make setup                 # uv sync + npm install
make synthetic             # full pipeline on SYNTHETIC data (no download, ~1 min)
make demo                  # API on :8000 + dashboard on :5173
```

For real data (a resumable download capped by `byte_cap_gb` in `backend/configs/data.yaml`), run:

```bash
make fetch-dry             # plan + size estimate, downloads nothing
make fetch                 # WeatherBench 2 India subset → data/raw/wb2/monthly/*.nc
make pipeline              # dataset → train → eval → export  (SOURCE=wb2 is the default)
make demo
```

Without `make` (for example on plain Windows), run from `backend/`: `uv run python -m pipelines.<fetch|dataset|train|evaluate|export> --source wb2`.

## Repository layout

```
backend/
  app/            FastAPI: api/routes, schemas, services, main.py
  ml/
    data/         weatherbench2.py · open_meteo.py · imd.py · synthetic.py (FAKE, flagged) · wb2_table.py
    labels/       bust definitions (configs/labels.yaml)
    features/     one file per signal + base.py (Signal interface, auto-registry)
    models/       lgbm.py · baseline_spread.py · analogs_knn.py
    explain/      TreeSHAP → plain-English reasons
    eval/         metrics (ROC/PR, recall at fixed false-alarm rate, Brier, reliability) + report
  pipelines/      CLIs: fetch → dataset → train → evaluate → export (+ demo)
  configs/        regions, data sources, labels, model
  tests/
frontend/         React (JSX) + Tailwind + shadcn/ui + MapLibre + Recharts + Framer Motion
data/             raw/ processed/ artifacts/ (git-ignored) · sample/ (committed, < 20 MB)
docs/             architecture.md · bust_definition.md · data.md · results.md
```

## Results

The real-data results table appears in [`docs/results.md`](docs/results.md) once the WeatherBench 2 download completes.

## Team workflow

See [CONTRIBUTING.md](CONTRIBUTING.md). Work happens on `feature/<name>` branches, which merge into `dev` through PRs. `main` holds stable demo builds only.

## Data credits

WeatherBench 2 (Rasp et al., 2024; ECMWF IFS HRES and ERA5 under CC BY 4.0; GraphCast by Google DeepMind), IMD gridded rainfall (Pai et al., 2014) via imdlib, and Open-Meteo (CC BY 4.0).

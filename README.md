# BustGuard: AI-based forecast bust detection

**SIH26079 · Ministry of Earth Sciences / NCMRWF.** Medium-range forecasts fail most in
fast-evolving situations: monsoon depressions, heavy rain, western disturbances, cyclones and
active/break transitions. BustGuard does not forecast the weather again. It predicts **when an
existing NWP rainfall forecast is likely to bust**, where (IMD meteorological subdivisions),
at which lead day (Day 1–10), how likely, and with what associated drivers.

Its outputs:

1. **Confidence map**: bust probability and risk level for 34 IMD subdivisions, Day 1–10.
2. **Bust probability**: calibrated, with its observed reliability.
3. **Error-prone areas**: a ranked list, and blind spots where the spread looks confident but BustGuard flags high risk.
4. **Explanations**: driver families (% share), top reasons, a regime pathway, and "N of M similar past cases busted". The wording is always "associated with".
5. **Dashboard and API**: FastAPI plus a Next.js forecaster console with evidence, scorecard and replay pages.

## Results (held-out test years 2021–2022, never seen in training or calibration)

Forecast: ECMWF HRES (WeatherBench 2). Truth: IMD gridded rainfall, as subdivision area means.
Bust: a missed IMD heavy-rain warning, or a forecast off by at least 2 IMD rainfall classes.
The base rate is 0.84%. Thresholds were frozen on the 2020 calibration year.

| | BustGuard | Lagged-ensemble spread | Logistic (spread + lead) |
|---|---|---|---|
| **PR-AUC (primary)** | **0.292** (95% CI 0.244–0.343) | 0.031 | 0.033 |
| Busts caught at the operating point | 85% (FAR 6.7%) | 36% (FAR 6.8%) | 38% (FAR 7.6%) |
| Busts caught when the spread was low (25 cases) | 88% | 0% | 0% |

Full tables are in [`docs/results.md`](docs/results.md): per lead day, reliability, CSI, Brier score, early warning, cost-loss, the regime × lead scorecard and the ablation. The ablation shows that most of the skill comes from **context**: location, season, lead time, forecast amount and recent verified error. Regime, pressure/wind and upstream features add smaller, consistent gains.

To reproduce these numbers offline from the committed bundle:

```bash
make headline
```

## Quick start

Requirements: Python 3.11 with [uv](https://docs.astral.sh/uv/), and Node 20+.

```bash
make setup        # uv sync + npm install
make demo         # prints the headline (offline), then API :8000 + dashboard :3000
```

`make demo` serves the committed sample in `data/sample/wb2` (14 MB), so no download is needed. With Docker, run `docker compose up --build`; this setup is untested here.

To rebuild from raw data (resumable, byte-capped, about 5.4 GB transfer):

```bash
make fetch-dry && make fetch            # WeatherBench 2 India subset (HRES, ERA5 TCWV)
make fetch SOURCE=imd                   # IMD 0.25° rainfall 2018-2022
make pipeline                           # dataset -> train -> eval -> events -> export (+ sample)
```

Without `make`, run the same modules from `backend/` with `uv run python -m pipelines.<step> --source wb2`.

## Repository layout

```
backend/
  app/          FastAPI (api/routes, schemas, services)
  ml/
    data/       weatherbench2.py · imd.py · wb2_table.py · open_meteo.py · synthetic.py (FAKE, flagged)
    labels/     bust definitions (configs/labels.yaml)
    features/   one file per signal, tagged with a family; base.py = Signal interface + registry
    models/     lgbm.py · baseline_spread.py · analogs_knn.py · confidently_wrong.py
    explain/    reasons, grouped SHAP (families), pathways, serve-time rendering
    eval/       metrics, report, scorecard, early warning, cost-loss, ablation
  pipelines/    fetch · dataset · train · evaluate · check_events · export · demo · check_alignment
  configs/      data · subdivisions · labels · model · pathways · replay_events
  tests/        labels, features (incl. issue-time leakage audit), metrics, CW, explain, API
frontend/       Next.js 14 · TypeScript · Tailwind · shadcn-style neumorphic primitives · MapLibre · Recharts
data/           raw/ processed/ artifacts/ (git-ignored) · sample/ (committed offline bundle + map geometry)
docs/           architecture · data · bust_definition · results · replay_events
```

## Important limitations

- **Spread is a proxy.** It is the lagged-ensemble spread (the last 3 HRES runs), because the 50-member ECMWF ensemble was too costly to download. Day 10 has no spread.
- **No Tmax forecasts in this build.** The Tmax rule exists, but the toggle is disabled.
- **No GraphCast disagreement.** It is out of v2 scope, so the "disagreement" family is empty.
- **No 850 hPa winds.** Circulation comes from MSLP (geostrophic vorticity and wind).
- **Subdivision boundaries are approximate.** They come from the IMD grid, state polygons and anchor cities. An official boundary file can be dropped in to replace them; see [`docs/data.md`](docs/data.md).
- **Some headline counts are small.** There are 25 low-spread busts and 13 confidently-wrong alerts, so treat those figures as indicative.

## Changelog

**v2 (feature/v2-upgrades, feature/neumorphic-ui)**

- **Bust labels:** IMD rainfall-category bust (missed heavy rain, or off by 2 or more classes); Tmax rule kept; v1 labels kept as options.
- **Regions and truth:** 34 IMD subdivisions with area means. IMD gridded rain is the truth; ERA5 is used only for moisture at issue time.
- **Split:** by year into train 2018–19, calibration 2020 and test 2021–22. Replay windows are excluded from fitting, and an issue-time leakage audit test covers every signal.
- **Baselines:** lagged-ensemble spread and logistic (spread + lead), always reported next to the model.
- **Features and explanations:** new signals for recent error, jumpiness, lagged spread, upstream and moisture, tagged into feature families. Grouped SHAP shares, pathways, and analog "N of M" cases.
- **Calibration and alerts:** isotonic calibration on 2020, and a confidently-wrong detector.
- **Evaluation:** PR-AUC primary, CSI, bootstrap CIs, regime × lead scorecard, early-warning lead time, cost-loss presets and family ablation.
- **API:** new /blindspots, /scorecard and /costloss endpoints, and an extended /region.
- **Replay events:** verified against the data. Kerala 2018, Kerala/Karnataka 2019, Konkan 2021 and Assam/Meghalaya 2022 are usable. Chennai 2015, Nisarga 2020 and Gulab 2021 are not, with reasons in [`docs/replay_events.md`](docs/replay_events.md).
- **Frontend:** Next.js neumorphic "instrument panel" with Console, Blind-spots, Scorecard, Evidence and Replay pages.

**v1**

- Scaffold, WeatherBench 2 fetcher, synthetic pipeline, LightGBM with a GraphCast-disagreement baseline, and a first API.

## Team workflow

See [CONTRIBUTING.md](CONTRIBUTING.md). Work happens on `feature/<name>` branches, which merge into `dev` through PRs. `main` holds stable demo builds only.

## Data credits

- WeatherBench 2 (Rasp et al., 2024): ECMWF IFS HRES and ERA5, CC BY 4.0.
- IMD 0.25° gridded rainfall (Pai et al., 2014), India Meteorological Department.
- Natural Earth, public domain.

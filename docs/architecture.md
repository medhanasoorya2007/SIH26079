# Architecture

```
fetch (ml/data)            WeatherBench 2 chunks -> India box -> monthly NetCDF (resumable, byte-capped)
                           IMD yearly grids (imdpune)   ERA5 TCWV at issue time
   │
dataset (pipelines/dataset.py)
   raw table (ml/data/wb2_table.py): run x subdivision x lead day, area means, context fields
   split by year (train 2018-19 | calibration 2020 | test 2021-22), replay windows flagged
   labels (ml/labels/bust.py)       signals (ml/features/*.py, one file each, auto-registered)
   │
train (pipelines/train.py)
   causal analog search (past, verified cases only) -> analog features
   LightGBM on train years, small grid chosen on calibration PR-AUC, isotonic calibration on 2020
   baselines on train+calibration: lagged spread (per-lead isotonic), logistic (spread + lead)
   │
evaluate (pipelines/evaluate.py, ml/eval/*)      test years only; thresholds frozen on calibration
   PR-AUC (primary), ROC, Brier, recall@FAR, CSI, reliability, bootstrap CIs, confidently-wrong,
   regime x lead scorecard, early warning, cost-loss, family ablation -> metrics.json, docs/results.md
   │
check_events -> docs/replay_events.md            export -> serving bundle (out-of-sample rows only)
   │
FastAPI (backend/app)  /regions /geo/subdivisions /confidence /region/{id} /metrics /scorecard
                       /costloss /blindspots /replay /replay/{id} /saved /dates /meta
   │
Next.js 14 (frontend)  Console · Blind-spots · Scorecard · Evidence · Replay (neumorphic UI)
```

## Signal families

| Family | Signals (files in `ml/features/`) |
|---|---|
| spread | `lagged_spread.py`: std of the last three runs, relative spread, departure from the lagged mean |
| drift | `jumpiness.py`: last change, two-run drift, flip-flops |
| pressure_wind | `synoptic.py`: MSLP anomaly, geostrophic vorticity and wind |
| moisture | `moisture.py`: ERA5 TCWV anomaly over and upstream of the region |
| upstream | `upstream.py`: rain/MSLP upstream (ESE), Bay of Bengal / Arabian Sea lows, NW India pressure |
| regime | `regime.py`: depression, cyclone/deep low, active/break, western disturbance, heavy rain |
| context | `lead_and_place.py`, `forecast_intensity.py`, `neighbourhood.py`, `recent_error.py`, analog features |
| disagreement | `model_disagreement.py` (needs a second model; not available in v2) |

## Explanations

* TreeSHAP from LightGBM (`pred_contrib`), identical to `shap.TreeExplainer`.
* Per forecast: top-3 feature sentences (templates live with each signal), family shares
  (`ml/explain/grouped_shap.py`), and a regime pathway filled only with flagged families
  (`configs/pathways.yaml`). All wording is associative ("associated with"), never causal.

## Confidently wrong

`ml/models/confidently_wrong.py`: low spread (lowest third of lagged spread within regime and
month, training-year thresholds) AND HIGH bust risk (calibration-frozen threshold) AND
analogs agree (≥ 25% of analog cases busted).

# Bust definition

Configured in `backend/configs/labels.yaml`; every definition is computed for every forecast
and stored as `bust_<name>`; `default` selects the one used for training, the API and the UI.

## Default (v2): IMD rainfall category bust

IMD 24-hour rainfall categories, applied to the **subdivision area-mean**:

| Class | Name | mm/day |
|---|---|---|
| 0 | Light / Moderate | ≤ 64.4 |
| 1 | Heavy | 64.5 – 115.5 |
| 2 | Very heavy | 115.6 – 204.4 |
| 3 | Extremely heavy | ≥ 204.5 |

A forecast **busts** when

1. the observed class differs from the forecast class by **2 or more classes** (either
   direction), **or**
2. the observed class is **Heavy or worse while the forecast was below Heavy** (missed warning).

In the 2018–2022 data, 99.6% of busts are missed warnings; the bust rate is ~0.9% of
subdivision-day forecasts (heavy area-mean rain is rare, and HRES under-forecasts it).

## Kept as options

* `tmax_error`: |forecast − observed Tmax| ≥ 3 °C (implemented and tested; no Tmax data in
  this build).
* `decision`: any of the above.
* `p95_error` (v1): absolute error above the lead-day-specific 95th percentile of training-year
  errors (floor 10 mm). Also trained and reported in `docs/results.md`.
* `category_flip` (v1): any flip across 64.5 mm.

Thresholds learned from data (p95) are fitted on training years only and frozen.

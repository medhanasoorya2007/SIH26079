# Data

All sources are public. Everything is cached under `data/raw` (git-ignored); the compact
serving bundle that reproduces the headline offline is committed in `data/sample/wb2`.

## Sources used in the v2 build

| Role | Source | Coverage used | Notes |
|---|---|---|---|
| Forecast under test | ECMWF IFS HRES via WeatherBench 2 (`hres/2016-2022-0012-240x121...`) | 00 UTC runs, JJAS 2018–2022, lead Day 1–10 | 1.5° grid. Total precipitation (24 h) Day 1–10; MSLP Day 1–8 |
| Rain truth | IMD 0.25° gridded daily rainfall (Pai et al. 2014), downloaded from imdpune.gov.in | 2018–2022 | Subdivision area means (cos-lat weighted). **ERA5 is never used as rain truth** |
| Atmospheric state at issue time | ERA5 total column water vapour via WeatherBench 2 | 00 UTC of every run, 2018–2022 | Moisture feature family only |
| Subdivision geometry | IMD grid land mask + Natural Earth 50 m admin-1 states | – | See "Subdivisions" below |

Transfer total (metered connection): 5.44 GB (WeatherBench 2 5.31 GB, IMD 0.13 GB, Natural
Earth 2 MB), under the 6 GB cap enforced by `ml/data/weatherbench2.py` (per-process ledgers in
`data/raw/wb2/_ledger*.json`, summed before every request).

### What was deliberately not downloaded (cost)

WeatherBench 2 stores each chunk for the **whole globe**, so an India subset limits what is
kept, not what is transferred.

* **850 hPa winds**: every pressure-level chunk holds all 13 (HRES) or 37 (GraphCast) levels,
  ≈10–28 GB per season. Low-level circulation is diagnosed from MSLP instead (geostrophic
  vorticity and wind).
* **ECMWF 50-member ensemble**: ≈225 MB per run for rainfall alone. Spread is replaced by the
  **lagged-ensemble spread**: the standard deviation of the last three HRES runs for the same
  valid day (runs issued I, I−1, I−2), a classic time-lagged proxy. It covers Day 1–8 fully,
  Day 9 with two members, and is unavailable on Day 10.
* **HRES 2 m temperature**: no Tmax forecasts in this build. The Tmax bust rule is implemented
  and tested; the dashboard shows Tmax as unavailable.

## Alignment of IMD dates

HRES lead day *d* of a 00 UTC run covers 00–24 UTC of the rain day. IMD daily grids close at
03 UTC (08:30 IST). `pipelines/check_alignment.py` correlates HRES Day-1 subdivision rain with
IMD at day offsets −1/0/+1: r = 0.43 / 0.64 / **0.77**, so truth for rain day V = IMD date V+1
(`imd.day_offset: 1`). At a 00 UTC issue on day I the newest verified rain day is therefore
I−2 (`issue_time.verification_lag_days: 2`), which every issue-time feature respects.

## Subdivisions

34 IMD meteorological subdivisions (Lakshadweep and Andaman & Nicobar have no IMD grid cells
and are omitted). Each IMD land cell is assigned to a state (Natural Earth 50 m polygons) and
then to a subdivision; where IMD splits a state, to the subdivision of the nearest anchor
city (`configs/subdivisions.yaml`). Northern cells that the IMD grid includes but the 50 m
polygons do not are assigned to Jammu & Kashmir and Ladakh, following IMD's own data domain.
This approximates the official boundaries; dropping an official file at
`data/raw/shapes/imd_subdivisions.geojson` replaces it. The map outline is the IMD grid itself.

## Other tracks (implemented, not used for the v2 results)

* `ml/data/open_meteo.py`: Open-Meteo Previous Runs (ECMWF/GFS/ICON, lead Day 1–8 from
  `previous_day0..7`; no ensemble history; ECMWF from 2024-03). Throttled, cached.
* `ml/data/synthetic.py`: **synthetic** data, flagged everywhere, for development only.

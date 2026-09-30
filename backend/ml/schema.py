"""Canonical column names of the BustGuard training table.

One row = one forecast: (init_date, region_id, variable, lead_day).
Data builders (``ml/data``) must emit the RAW columns; signals (``ml/features``) add
``sig_*`` feature columns; labels (``ml/labels``) add ``error``/``abs_error``/``bust*``.
"""

from __future__ import annotations

KEYS = ["init_date", "region_id", "variable", "lead_day"]

RAW = [
    *KEYS,
    "valid_date",  # calendar day the forecast is for (rain day)
    "fc",  # forecast under evaluation (ECMWF HRES), mm/day or degC
    "fc_alt",  # independent model for disagreement (GraphCast), may be NaN
    "obs",  # truth (ERA5 / IMD), NaN if not yet verified
    "lat",
    "lon",
    "zone",
    "source",  # e.g. "wb2", "open_meteo", "SYNTHETIC"
    "is_synthetic",  # True for generated demo data -- never report as real results
]

# Optional context columns a builder may provide (signals use them when present).
CONTEXT = [
    "ctx_mslp",  # forecast MSLP at region, hPa (valid-day mean)
    "ctx_geo_vort",  # forecast geostrophic vorticity at region, 1e-5 s^-1
    "ctx_fc_neigh_mean",  # forecast rain, 3x3 grid neighbourhood mean
    "ctx_fc_neigh_std",  # ... standard deviation (sharp gradients)
    "ctx_fc_neigh_max",  # ... maximum
    "ctx_bob_min_mslp",  # forecast min MSLP over Bay of Bengal box (depressions)
    "ctx_arb_min_mslp",  # forecast min MSLP over Arabian Sea box
    "ctx_core_fc",  # forecast mean rain over the monsoon core zone (active/break)
    "ctx_nw_mslp",  # forecast mean MSLP over NW India (western disturbances / heat low)
]

SPLIT_COL = "split"  # "train" | "test"
LABEL_COL = "bust"

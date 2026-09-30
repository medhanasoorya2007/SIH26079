"""Weather-regime tags named in the problem statement.

Tags are diagnosed from the *forecast* (what the forecaster sees at issue time):
monsoon depression, cyclone, heavy rainfall, active / break monsoon, western disturbance,
heat wave (Tmax only). Thresholds live here so they are easy to audit and tune.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register

DEPRESSION_ANOM_HPA = -4.0  # Bay of Bengal min MSLP anomaly for a depression-like low
CYCLONE_MIN_MSLP_HPA = 996.0  # deep low: cyclonic storm range
HEAVY_RAIN_MM = 64.5
ACTIVE_RATIO, BREAK_RATIO = 1.5, 0.5  # core-zone forecast rain vs training climatology
WD_ANOM_HPA = -3.0
HEATWAVE_TMAX_C = 40.0

REGIME_NAMES = {
    "sig_regime_cyclone": "Cyclone / deep low",
    "sig_regime_depression": "Monsoon depression",
    "sig_regime_heavy_rain": "Heavy rainfall",
    "sig_regime_active": "Active monsoon",
    "sig_regime_break": "Break monsoon",
    "sig_regime_wd": "Western disturbance",
    "sig_regime_heatwave": "Heat wave",
}


@register
class Regime(Signal):
    name = "regime"
    description = "Rule-based weather-regime tags diagnosed from the forecast fields."
    requires = ("fc", "valid_date")
    order = 60
    exclude_from_model = ("sig_regime_label",)
    explanations = {
        "sig_regime_depression": "Monsoon-depression regime: depression tracks and rain shields are often misplaced at this range.",
        "sig_regime_cyclone": "A cyclone / deep low is in the forecast: track and landfall errors dominate.",
        "sig_regime_heavy_rain": "Heavy-rainfall regime: extreme amounts are rarely forecast at the right place and time.",
        "sig_regime_active": "Active-monsoon spell: vigorous convection increases rainfall errors.",
        "sig_regime_break": "Break-monsoon spell: the revival timing is notoriously hard to forecast.",
        "sig_regime_wd": "Western-disturbance pattern over NW India: interaction with the monsoon trough is uncertain.",
        "sig_regime_heatwave": "Heat-wave regime: Tmax near record values, where models under- or over-shoot.",
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        n = len(df)
        f = lambda c: df[c].to_numpy(dtype=float) if c in df else np.full(n, np.nan)  # noqa: E731
        is_rain = (df["variable"] == "rain").to_numpy()
        bob_anom, arb_anom = f("sig_bob_low_anom"), f("sig_arb_low_anom")
        bob_min, arb_min = f("ctx_bob_min_mslp"), f("ctx_arb_min_mslp")
        tags = {
            "sig_regime_cyclone": (np.fmin(bob_min, arb_min) < CYCLONE_MIN_MSLP_HPA),
            "sig_regime_depression": (bob_anom <= DEPRESSION_ANOM_HPA)
            | (arb_anom <= DEPRESSION_ANOM_HPA),
            "sig_regime_heavy_rain": is_rain & (f("fc") >= HEAVY_RAIN_MM),
            "sig_regime_wd": (f("sig_nw_mslp_anom") <= WD_ANOM_HPA) & (f("lat") >= 28.0),
            "sig_regime_heatwave": (~is_rain) & (f("fc") >= HEATWAVE_TMAX_C),
        }
        # active / break from forecast core-zone rain relative to training climatology
        if "ctx_core_fc" in df:
            month = pd.to_datetime(df["valid_date"]).dt.month
            fit = ctx.fit_mask & df["ctx_core_fc"].notna()
            clim = df.loc[fit, "ctx_core_fc"].groupby(month[fit]).mean()
            ratio = df["ctx_core_fc"].to_numpy() / np.maximum(
                month.map(clim).to_numpy(dtype=float), 0.1
            )
            tags["sig_regime_active"] = ratio >= ACTIVE_RATIO
            tags["sig_regime_break"] = ratio <= BREAK_RATIO
        out = pd.DataFrame({k: v.astype(float) for k, v in tags.items()}, index=df.index)
        # primary regime label for display (priority = dict order of REGIME_NAMES)
        label = np.full(n, "Normal", dtype=object)
        for col in reversed(list(REGIME_NAMES)):
            if col in out:
                label = np.where(out[col].to_numpy() == 1, REGIME_NAMES[col], label)
        out["sig_regime_label"] = label
        return out

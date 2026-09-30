"""Synoptic state from the forecast pressure field: lows, depressions, low-level vorticity.

850 hPa winds are deliberately not downloaded (WeatherBench 2 stores every pressure level
in one chunk, ~20x the cost of MSLP). Low-level circulation is instead diagnosed as
*geostrophic vorticity* from the Laplacian of MSLP: zeta_g = lap(p) / (rho * f).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register


def _anomaly(df: pd.DataFrame, col: str, ctx: SignalContext, by: list[str]) -> pd.Series:
    """Value minus its training-period mean for the same group (region/month/...)."""
    month = pd.to_datetime(df["valid_date"]).dt.month.rename("_month")
    keys = [df[c] for c in by] + [month]
    fit = ctx.fit_mask & df[col].notna()
    clim = df.loc[fit, col].groupby([k[fit] for k in keys]).mean()
    ref = clim.reindex(pd.MultiIndex.from_arrays(keys)).to_numpy()
    return df[col] - ref


@register
class Synoptic(Signal):
    name = "synoptic"
    description = (
        "Forecast MSLP anomaly at the region, geostrophic vorticity (cyclonic circulation), and "
        "depth of the lowest pressure over the Bay of Bengal / Arabian Sea / NW India. Deep lows "
        "and depressions are where medium-range track and intensity errors concentrate."
    )
    requires = ("ctx_mslp",)
    order = 40
    explanations = {
        "sig_mslp_anom": {
            "low": "Forecast pressure is {value:.1f} hPa below normal at {region}: a low-pressure system is nearby.",
            "high": "Forecast pressure is {value:+.1f} hPa above normal: a suppressed / break-like pattern.",
        },
        "sig_geo_vorticity": {
            "high": "Strong cyclonic circulation forecast near {region} ({value:.1f}e-5 s^-1): system position/intensity is uncertain.",
            "low": "Anticyclonic flow forecast near {region}.",
        },
        "sig_bob_low_anom": "A deep low / depression is forecast over the Bay of Bengal ({value:.1f} hPa below normal): depression tracks are often mis-forecast.",
        "sig_arb_low_anom": "A low is forecast over the Arabian Sea ({value:.1f} hPa below normal): offshore trough / vortex uncertainty.",
        "sig_nw_mslp_anom": "Pressure anomaly over NW India of {value:.1f} hPa: heat-low / western-disturbance interaction.",
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        out = {"sig_mslp_anom": _anomaly(df, "ctx_mslp", ctx, ["region_id"])}
        out["sig_geo_vorticity"] = (
            df["ctx_geo_vort"].astype(float) if "ctx_geo_vort" in df else np.nan
        )
        for col, name in [
            ("ctx_bob_min_mslp", "sig_bob_low_anom"),
            ("ctx_arb_min_mslp", "sig_arb_low_anom"),
            ("ctx_nw_mslp", "sig_nw_mslp_anom"),
        ]:
            out[name] = _anomaly(df, col, ctx, ["lead_day"]) if col in df else np.nan
        return pd.DataFrame(out, index=df.index)

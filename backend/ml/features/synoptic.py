"""Pressure & wind at the region, from the forecast MSLP field (family: pressure_wind).

850 hPa winds are not downloaded (every WeatherBench 2 pressure-level chunk holds all
levels, ~20x the cost of MSLP). Low-level circulation is diagnosed from MSLP instead:
geostrophic vorticity zeta_g = lap(p)/(rho f) and geostrophic wind (u_g, v_g).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register


def anomaly(df: pd.DataFrame, col: str, ctx: SignalContext, by: list[str]) -> pd.Series:
    """Value minus its training-period mean for the same group and calendar month."""
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
        "Forecast MSLP anomaly, geostrophic vorticity and geostrophic wind over the region. "
        "Deep lows, strong cyclonic circulation and wind shifts are associated with position "
        "and intensity errors."
    )
    requires = ("ctx_mslp",)
    order = 40
    family = "pressure_wind"
    explanations = {
        "sig_mslp_anom": {
            "low": "Forecast pressure {value:.1f} hPa below normal over {region}: a low nearby is associated with uncertain rainfall placement.",
            "high": "Forecast pressure {value:+.1f} hPa above normal over {region} (suppressed / break-like flow).",
        },
        "sig_geo_vorticity": {
            "high": "Cyclonic circulation forecast over {region} ({value:.1f}e-5 per s), associated with system position errors.",
            "low": "Anticyclonic flow forecast over {region}.",
        },
        "sig_geo_wind": "Strong pressure gradient over {region} (geostrophic wind {value:.0f} m/s).",
        "sig_geo_u": {
            "high": "Strong westerly monsoon flow forecast over {region} ({value:.0f} m/s).",
            "low": "Weak or easterly low-level flow forecast over {region} ({value:.0f} m/s): a wind shift.",
        },
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        f = lambda c: df[c].astype(float) if c in df else pd.Series(np.nan, index=df.index)  # noqa: E731
        u, v = f("ctx_geo_u"), f("ctx_geo_v")
        return pd.DataFrame(
            {
                "sig_mslp_anom": anomaly(df, "ctx_mslp", ctx, ["region_id"]),
                "sig_geo_vorticity": f("ctx_geo_vort"),
                "sig_geo_wind": np.hypot(u, v),
                "sig_geo_u": u,
            },
            index=df.index,
        )

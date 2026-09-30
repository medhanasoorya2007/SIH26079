"""How extreme is the forecast itself? Heavy-rain forecasts carry the largest errors."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register

HEAVY_RAIN_MM = 64.5  # IMD 'heavy rainfall' 24-h threshold


def imd_rain_category(mm: np.ndarray | pd.Series) -> np.ndarray:
    """IMD 24-h rainfall class: 0 none/very light, 1 light, 2 moderate, 3 heavy,
    4 very heavy, 5 extremely heavy."""
    bins = [2.5, 15.6, 64.5, 115.6, 204.5]
    return np.digitize(np.asarray(mm, dtype=float), bins)


@register
class ForecastIntensity(Signal):
    name = "forecast_intensity"
    description = (
        "Forecast amount and how unusual it is for the region and month (ratio to the "
        "training-period climatology). Intense forecasts have large absolute errors."
    )
    requires = ("fc", "region_id", "valid_date", "variable")
    order = 20
    explanations = {
        "sig_fc": {
            "high": "Forecast is intense ({value:.0f} {unit}): big forecasts carry the largest absolute errors.",
            "low": "Forecast is low ({value:.0f} {unit}) where rain often occurs: a missed event is possible.",
        },
        "sig_fc_clim_ratio": {
            "high": "Forecast is {value:.1f}x the normal for this region and month: unusual events verify poorly.",
            "low": "Forecast is well below normal ({value:.1f}x) for this region and month.",
        },
        "sig_fc_category": "Forecast falls in IMD category {value:.0f} (3 = heavy, 4 = very heavy).",
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        month = pd.to_datetime(df["valid_date"]).dt.month
        key = [df["region_id"], df["variable"], month]
        fit = df.loc[ctx.fit_mask & df["obs"].notna()] if "obs" in df else df.iloc[:0]
        clim = fit.groupby(
            [fit["region_id"], fit["variable"], pd.to_datetime(fit["valid_date"]).dt.month]
        )["obs"].mean()
        idx = pd.MultiIndex.from_arrays(key)
        c = clim.reindex(idx).to_numpy()
        ratio = (df["fc"].to_numpy() + 1.0) / (np.nan_to_num(c, nan=np.nan) + 1.0)
        is_rain = (df["variable"] == "rain").to_numpy()
        return pd.DataFrame(
            {
                "sig_fc": df["fc"].astype(float),
                "sig_fc_clim_ratio": np.where(is_rain, ratio, np.nan),
                "sig_fc_category": np.where(is_rain, imd_rain_category(df["fc"]), np.nan),
            },
            index=df.index,
        )

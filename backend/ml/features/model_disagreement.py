"""Multi-model disagreement (ECMWF HRES vs GraphCast, or any configured second model)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register
from ml.features.forecast_intensity import imd_rain_category


@register
class ModelDisagreement(Signal):
    name = "model_disagreement"
    description = (
        "Absolute and relative difference between the primary forecast and an independent "
        "model. When physically different models disagree, at least one is wrong. This raw "
        "score is also the operational-style baseline BustGuard is compared against."
    )
    requires = ("fc", "fc_alt")
    order = 30
    explanations = {
        "sig_disagreement_abs": "ECMWF and GraphCast disagree by {value:.0f} {unit} here: large model disagreement often precedes a bust.",
        "sig_disagreement_rel": "The two models disagree strongly in relative terms ({value:.0%} of the combined forecast).",
        "sig_disagreement_cat": "The models put the day in different IMD rainfall categories ({value:.0f} class apart).",
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        fc, alt = df["fc"].astype(float), df["fc_alt"].astype(float)
        diff = (fc - alt).abs()
        cat = np.abs(imd_rain_category(fc) - imd_rain_category(alt)).astype(float)
        cat[alt.isna().to_numpy()] = np.nan
        is_rain = (df["variable"] == "rain").to_numpy() if "variable" in df else True
        return pd.DataFrame(
            {
                "sig_disagreement_abs": diff,
                "sig_disagreement_rel": diff / (fc.abs() + alt.abs() + 1.0),
                "sig_disagreement_cat": np.where(is_rain, cat, np.nan),
            },
            index=df.index,
        )

"""Spatial structure of the forecast inside the subdivision (family: context).

Sharp contrasts within a subdivision mean a small displacement of the rain band changes the
area-mean outcome.
"""

from __future__ import annotations

import pandas as pd

from ml.features.base import Signal, SignalContext, register


@register
class Neighbourhood(Signal):
    name = "neighbourhood"
    description = (
        "Spatial standard deviation and peak of forecast rain across the subdivision. Strong "
        "internal gradients are associated with placement errors."
    )
    requires = ("ctx_fc_sub_std", "ctx_fc_sub_max")
    order = 25
    family = "context"
    explanations = {
        "sig_fc_sub_std": "Sharp rainfall contrasts forecast within {region} (spatial spread {value:.0f} {unit}), associated with placement errors.",
        "sig_fc_sub_excess": "Local peaks {value:.0f} {unit} above the area mean are forecast within {region}.",
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "sig_fc_sub_std": df["ctx_fc_sub_std"].astype(float),
                "sig_fc_sub_excess": (df["ctx_fc_sub_max"] - df["fc"]).clip(lower=0).astype(float),
            },
            index=df.index,
        )

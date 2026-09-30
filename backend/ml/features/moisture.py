"""Moisture at issue time (family: moisture).

ERA5 analysis total column water vapour at the initialisation time, over the region and
its upstream box, as anomalies from the training-period climatology (region x month).
ERA5 describes the atmospheric state only; it is never used as rain truth.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register
from ml.features.synoptic import anomaly


@register
class Moisture(Signal):
    name = "moisture"
    description = (
        "Total column water vapour (ERA5 analysis at issue time) over and upstream of the region. "
        "Anomalous moisture loading is associated with under-forecast heavy rain."
    )
    requires = ("ctx_tcwv",)
    order = 44
    family = "moisture"
    explanations = {
        "sig_tcwv_anom": {
            "high": "The atmosphere over {region} is {value:+.0f} kg/m2 moister than normal at issue time, associated with heavy-rain misses.",
            "low": "The atmosphere over {region} is {value:+.0f} kg/m2 drier than normal at issue time.",
        },
        "sig_up_tcwv_anom": "Moisture upstream of {region} is {value:+.0f} kg/m2 above normal, associated with moisture transport into the region.",
        "sig_tcwv": "Column water vapour over {region} is {value:.0f} kg/m2 at issue time.",
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        nan = pd.Series(np.nan, index=df.index)
        return pd.DataFrame(
            {
                "sig_tcwv": df["ctx_tcwv"].astype(float),
                "sig_tcwv_anom": anomaly(df, "ctx_tcwv", ctx, ["region_id"]),
                "sig_up_tcwv_anom": anomaly(df, "ctx_up_tcwv", ctx, ["region_id"])
                if "ctx_up_tcwv" in df
                else nan,
            },
            index=df.index,
        )

"""Upstream and basin-scale systems (family: upstream).

Monsoon lows and depressions travel west-north-west from the Bay of Bengal, so the region's
"upstream" box lies to its east-south-east (ml/data/wb2_table.py). Basin lows over the Bay
of Bengal / Arabian Sea and the NW India pressure anomaly describe the synoptic set-up.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register
from ml.features.synoptic import anomaly


@register
class Upstream(Signal):
    name = "upstream"
    description = (
        "Forecast rain and pressure upstream of the region and the depth of basin-scale lows. "
        "An active system upstream is associated with timing/track errors downstream."
    )
    requires = ("valid_date",)
    order = 42
    family = "upstream"
    explanations = {
        "sig_up_fc": "Heavy rain forecast upstream of {region} ({value:.0f} {unit}): an approaching system's timing is uncertain.",
        "sig_up_mslp_anom": "Low pressure upstream of {region} ({value:.1f} hPa below normal), associated with an approaching disturbance.",
        "sig_bob_low_anom": "A deep low / depression is forecast over the Bay of Bengal ({value:.1f} hPa below normal); depression tracks are often misplaced.",
        "sig_arb_low_anom": "A low is forecast over the Arabian Sea ({value:.1f} hPa below normal), associated with offshore-trough uncertainty.",
        "sig_nw_mslp_anom": "NW India pressure anomaly of {value:.1f} hPa (heat low / western-disturbance interaction).",
    }

    def available(self, df: pd.DataFrame) -> bool:
        return any(c in df and df[c].notna().any() for c in ("ctx_up_fc", "ctx_bob_min_mslp"))

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        nan = pd.Series(np.nan, index=df.index)
        out = {"sig_up_fc": df["ctx_up_fc"].astype(float) if "ctx_up_fc" in df else nan}
        out["sig_up_mslp_anom"] = (
            anomaly(df, "ctx_up_mslp", ctx, ["region_id"]) if "ctx_up_mslp" in df else nan
        )
        for col, name in [
            ("ctx_bob_min_mslp", "sig_bob_low_anom"),
            ("ctx_arb_min_mslp", "sig_arb_low_anom"),
            ("ctx_nw_mslp", "sig_nw_mslp_anom"),
        ]:
            out[name] = anomaly(df, col, ctx, ["lead_day"]) if col in df else nan
        return pd.DataFrame(out, index=df.index)

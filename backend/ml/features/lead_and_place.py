"""Lead time, location and season: the basic 'where/when' predictors of forecast error."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register


@register
class LeadAndPlace(Signal):
    name = "lead_and_place"
    description = (
        "Forecast lead day, region coordinates and season. Error grows with lead time and "
        "some regions (orography, coasts, monsoon trough) are systematically harder."
    )
    requires = ("lead_day", "lat", "lon", "valid_date")
    order = 10
    explanations = {
        "sig_lead_day": {
            "high": "Day-{value:.0f} lead time: rainfall errors grow quickly beyond Day 4 in the monsoon.",
            "low": "Short lead time (Day {value:.0f}), yet other factors still raise the risk.",
        },
        "sig_lat": "{region} sits in a latitude band where this model has historically erred more.",
        "sig_lon": "{region} sits in a longitude band (coast / orography) with historically larger errors.",
        "sig_doy_sin": "Time of season: this part of the monsoon season is historically harder to forecast.",
        "sig_doy_cos": "Time of season: this part of the monsoon season is historically harder to forecast.",
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        doy = pd.to_datetime(df["valid_date"]).dt.dayofyear.to_numpy()
        ang = 2 * np.pi * doy / 365.25
        return pd.DataFrame(
            {
                "sig_lead_day": df["lead_day"].astype(float),
                "sig_lat": df["lat"].astype(float),
                "sig_lon": df["lon"].astype(float),
                "sig_doy_sin": np.sin(ang),
                "sig_doy_cos": np.cos(ang),
            },
            index=df.index,
        )

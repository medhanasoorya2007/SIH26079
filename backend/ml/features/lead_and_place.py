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
    family = "context"
    explanations = {
        "sig_lead_day": {
            "high": "Day-{value:.0f} lead time: longer leads are associated with larger rainfall errors.",
            "low": "Short lead (Day {value:.0f}), but other factors are associated with elevated risk.",
        },
        "sig_lat": "{region}'s location has historically been associated with larger errors at this lead.",
        "sig_lon": "{region}'s location has historically been associated with larger errors at this lead.",
        "sig_doy_sin": "This stage of the monsoon season has historically been associated with more busts.",
        "sig_doy_cos": "This stage of the monsoon season has historically been associated with more busts.",
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

"""Spatial structure of the forecast around the region (sharp gradients = position risk)."""

from __future__ import annotations

import pandas as pd

from ml.features.base import Signal, SignalContext, register


@register
class Neighbourhood(Signal):
    name = "neighbourhood"
    description = (
        "Mean, spread and maximum of forecast rain in the surrounding grid cells. A rain band "
        "or system edge next to the region means a small displacement gives a big point error."
    )
    requires = ("ctx_fc_neigh_mean", "ctx_fc_neigh_std", "ctx_fc_neigh_max")
    order = 25
    explanations = {
        "sig_fc_neigh_std": "Sharp rainfall gradient around {region} (spread {value:.0f} {unit}): a small shift of the rain band changes the outcome.",
        "sig_fc_neigh_excess": "Much heavier rain is forecast just nearby ({value:.0f} {unit} more than at {region}).",
        "sig_fc_neigh_mean": "Widespread forecast rain in the surrounding area ({value:.0f} {unit} on average).",
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "sig_fc_neigh_mean": df["ctx_fc_neigh_mean"].astype(float),
                "sig_fc_neigh_std": df["ctx_fc_neigh_std"].astype(float),
                "sig_fc_neigh_excess": (df["ctx_fc_neigh_max"] - df["fc"])
                .clip(lower=0)
                .astype(float),
            },
            index=df.index,
        )

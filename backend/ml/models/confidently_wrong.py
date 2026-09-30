"""Confidently-wrong detector (v2 #11).

The operational trap: the ensemble (here, the lagged-ensemble spread) looks confident, but
the forecast busts anyway. A CONFIDENTLY-WRONG ALERT is raised when all three hold:

1. low spread: spread in the lowest third for the same regime and season (month),
   thresholds fitted on training years only;
2. high bust probability: BustGuard at or above its "High" operating threshold
   (fixed on the calibration block);
3. analogs agree: the share of busts among the analog cases is >= ``analog_min_rate``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class ConfidentlyWrong:
    spread_col: str = "sig_spread"
    quantile: float = 1 / 3
    group_by: tuple[str, ...] = ("regime", "month")
    min_group_size: int = 30
    analog_min_rate: float = 0.25
    thresholds: dict = field(default_factory=dict)
    month_fallback: dict = field(default_factory=dict)
    global_fallback: float = float("nan")

    @staticmethod
    def _keys(df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "regime": df.get("sig_regime_label", pd.Series("Normal", index=df.index))
                .fillna("Normal")
                .astype(str),
                "month": pd.to_datetime(df["valid_date"]).dt.month,
            },
            index=df.index,
        )

    def fit(self, df: pd.DataFrame) -> ConfidentlyWrong:
        k = self._keys(df)
        s = df[self.spread_col]
        ok = s.notna()
        g = s[ok].groupby([k.loc[ok, c] for c in self.group_by])
        q, n = g.quantile(self.quantile), g.size()
        self.thresholds = {
            tuple(map(_py, key)): float(v) for key, v in q[n >= self.min_group_size].items()
        }
        m = s[ok].groupby(k.loc[ok, "month"])
        self.month_fallback = {int(key): float(v) for key, v in m.quantile(self.quantile).items()}
        self.global_fallback = float(s[ok].quantile(self.quantile)) if ok.any() else float("nan")
        return self

    def spread_threshold(self, df: pd.DataFrame) -> np.ndarray:
        k = self._keys(df)
        out = np.full(len(df), self.global_fallback)
        keys = list(zip(*[k[c] for c in self.group_by], strict=True))
        for i, key in enumerate(keys):
            key = tuple(map(_py, key))
            if key in self.thresholds:
                out[i] = self.thresholds[key]
            else:
                out[i] = self.month_fallback.get(int(k["month"].iat[i]), self.global_fallback)
        return out

    def low_spread(self, df: pd.DataFrame) -> np.ndarray:
        s = df[self.spread_col].to_numpy(dtype=float)
        return np.isfinite(s) & (s <= self.spread_threshold(df))

    def alerts(
        self, df: pd.DataFrame, prob: np.ndarray, high_threshold: float, analog_rate: np.ndarray
    ) -> np.ndarray:
        agree = np.nan_to_num(np.asarray(analog_rate, dtype=float), nan=0.0) >= self.analog_min_rate
        return self.low_spread(df) & (np.asarray(prob) >= high_threshold) & agree


def _py(x):
    return x.item() if hasattr(x, "item") else x

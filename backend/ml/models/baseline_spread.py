"""Operational-style baseline: 'large spread => low confidence'.

The baseline uses ONE raw uncertainty score (configs/model.yaml ``baseline.score_column``):
HRES-vs-GraphCast disagreement for the WeatherBench 2 track, or ensemble / multi-model
spread when available. To compare fairly with the calibrated model, the raw score is
mapped to a bust probability with a lead-day-specific isotonic fit on the TRAINING years
(the same information budget BustGuard gets). Rank metrics (ROC/PR/recall at a fixed
false-alarm rate) are unaffected by this monotone mapping within a lead day.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression


@dataclass
class SpreadBaseline:
    score_column: str
    name: str = "spread baseline"
    by_lead: dict = field(default_factory=dict)
    base_rate: float = 0.05

    def fit(self, df: pd.DataFrame, y: pd.Series) -> SpreadBaseline:
        ok = df[self.score_column].notna() & y.notna()
        self.base_rate = float(y[ok].mean()) if ok.any() else 0.05
        for lead, g in df[ok].groupby("lead_day"):
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            self.by_lead[int(lead)] = iso.fit(
                g[self.score_column].to_numpy(), y[g.index].to_numpy()
            )
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        out = np.full(len(df), self.base_rate)
        score = df[self.score_column].to_numpy(dtype=float)
        leads = df["lead_day"].to_numpy()
        for lead, iso in self.by_lead.items():
            m = (leads == lead) & ~np.isnan(score)
            if m.any():
                out[m] = iso.predict(score[m])
        return out

    def raw(self, df: pd.DataFrame) -> np.ndarray:
        return df[self.score_column].to_numpy(dtype=float)

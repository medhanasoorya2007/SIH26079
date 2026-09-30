"""Operational-style baselines: "large spread => low confidence" (v2 #5).

Both use the lagged-ensemble spread (std of the last 3 HRES runs for the same valid day;
see ml/features/lagged_spread.py). They are fitted on training + calibration years:

* ``spread_isotonic``: spread -> bust probability, one isotonic fit per lead day.
* ``logistic``: logistic regression on (spread, lead day) (+ imputation / scaling).

Rows without a spread value (e.g. Day 10, fewer than 2 lagged runs) get the base rate
(isotonic) or the median-imputed spread (logistic).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class SpreadBaseline:
    score_column: str
    name: str = "Spread (per-lead isotonic)"
    by_lead: dict = field(default_factory=dict)
    base_rate: float = 0.0

    def fit(self, df: pd.DataFrame, y: pd.Series) -> SpreadBaseline:
        ok = df[self.score_column].notna() & y.notna()
        self.base_rate = float(y[y.notna()].mean())
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


@dataclass
class LogisticBaseline:
    columns: list[str]
    name: str = "Logistic regression (spread + lead day)"
    model: object | None = None

    def fit(self, df: pd.DataFrame, y: pd.Series) -> LogisticBaseline:
        ok = y.notna()
        self.model = make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=1000)
        )
        self.model.fit(df.loc[ok, self.columns].astype(float), y[ok].astype(int))
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(df[self.columns].astype(float))[:, 1]

    def coefficients(self) -> dict:
        lr = self.model[-1]
        return {c: float(w) for c, w in zip(self.columns, lr.coef_[0], strict=True)} | {
            "intercept": float(lr.intercept_[0])
        }


def build_baselines(cfg: dict, df: pd.DataFrame, y: pd.Series) -> dict:
    """Instantiate and fit every baseline in configs/model.yaml ``baselines``."""
    out = {}
    for key, spec in cfg.items():
        if spec["kind"] == "spread_isotonic":
            if spec["score_column"] not in df or df[spec["score_column"]].notna().sum() == 0:
                continue
            out[key] = SpreadBaseline(spec["score_column"], spec["name"]).fit(df, y)
        elif spec["kind"] == "logistic":
            if not all(c in df for c in spec["columns"]):
                continue
            out[key] = LogisticBaseline(spec["columns"], spec["name"]).fit(df, y)
        else:
            raise ValueError(f"unknown baseline kind {spec['kind']}")
    return out

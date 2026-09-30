"""Calibrated LightGBM bust classifier.

* Class imbalance: ``class_weight='balanced'`` (busts are ~5% by construction).
* Calibration: out-of-fold raw scores (leave-one-year-out over the training years) are
  mapped to probabilities with isotonic regression, so the class weighting does not
  inflate the probabilities shown to forecasters.
* Explanations: the final booster's native TreeSHAP (``pred_contrib=True``), which
  gives exactly the same values as ``shap.TreeExplainer`` without the numba dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


@dataclass
class BustModel:
    params: dict
    features: list[str] = field(default_factory=list)
    calibration: str = "isotonic"
    booster: lgb.LGBMClassifier | None = None
    calibrator: object | None = None
    feature_medians: dict = field(default_factory=dict)
    oof_raw: np.ndarray | None = None
    label: str = "bust"

    # ------------------------------------------------------------------ training
    def _new(self) -> lgb.LGBMClassifier:
        return lgb.LGBMClassifier(**self.params)

    def fit(self, X: pd.DataFrame, y: pd.Series, groups: pd.Series) -> BustModel:
        """Fit on training rows. ``groups`` (years) define the calibration folds."""
        self.features = list(X.columns)
        X = X.astype(float)
        y = y.astype(int).to_numpy()
        groups = np.asarray(groups)
        oof = np.full(len(X), np.nan)
        uniq = np.unique(groups)
        if len(uniq) >= 2:
            for g in uniq:
                tr, va = groups != g, groups == g
                if y[tr].sum() == 0:
                    continue
                m = self._new().fit(X[tr], y[tr])
                oof[va] = m.predict_proba(X[va], raw_score=True)
        else:  # single training year: calibrate on the last 25% of dates
            cut = int(len(X) * 0.75)
            m = self._new().fit(X.iloc[:cut], y[:cut])
            oof[cut:] = m.predict_proba(X.iloc[cut:], raw_score=True)
        ok = ~np.isnan(oof)
        if self.calibration == "sigmoid":
            self.calibrator = LogisticRegression().fit(oof[ok].reshape(-1, 1), y[ok])
        else:
            self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(
                oof[ok], y[ok]
            )
        self.oof_raw = oof
        self.booster = self._new().fit(X, y)
        self.feature_medians = X.median(numeric_only=True).to_dict()
        return self

    # ---------------------------------------------------------------- inference
    def raw_score(self, X: pd.DataFrame) -> np.ndarray:
        return self.booster.predict_proba(X[self.features].astype(float), raw_score=True)

    def calibrate(self, raw: np.ndarray) -> np.ndarray:
        if isinstance(self.calibrator, LogisticRegression):
            return self.calibrator.predict_proba(np.asarray(raw).reshape(-1, 1))[:, 1]
        return self.calibrator.predict(raw)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.calibrate(self.raw_score(X))

    def contributions(self, X: pd.DataFrame) -> pd.DataFrame:
        """TreeSHAP contributions in log-odds space (last column = expected value)."""
        contrib = self.booster.predict_proba(X[self.features].astype(float), pred_contrib=True)
        return pd.DataFrame(contrib, columns=[*self.features, "_bias"], index=X.index)

    def importance(self) -> pd.Series:
        gain = self.booster.booster_.feature_importance(importance_type="gain")
        return pd.Series(gain, index=self.features).sort_values(ascending=False)

    # ------------------------------------------------------------------ persistence
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path: Path) -> BustModel:
        return joblib.load(path)

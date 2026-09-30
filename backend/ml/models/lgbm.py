"""Calibrated LightGBM bust classifier.

* Fit on the TRAINING years only (class-weighted: busts are rare).
* Calibrated with isotonic regression on the separate CALIBRATION block (v2 #10), so the
  probabilities shown to forecasters are not inflated by the class weighting and the test
  years are never touched.
* Explanations: native TreeSHAP (``pred_contrib=True``) of the booster; identical to
  ``shap.TreeExplainer`` values, without the numba dependency.
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
    label: str = "bust"

    def _new(self) -> lgb.LGBMClassifier:
        return lgb.LGBMClassifier(**self.params)

    def fit(
        self, X: pd.DataFrame, y: pd.Series, X_cal: pd.DataFrame, y_cal: pd.Series
    ) -> BustModel:
        """Booster on (X, y) = training years; calibrator on (X_cal, y_cal) = calibration block."""
        self.features = list(X.columns)
        self.booster = self._new().fit(X.astype(float), y.astype(int).to_numpy())
        raw = self.raw_score(X_cal)
        yc = y_cal.astype(int).to_numpy()
        if self.calibration == "sigmoid":
            self.calibrator = LogisticRegression().fit(raw.reshape(-1, 1), yc)
        else:
            self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(
                raw, yc
            )
        self.feature_medians = X.astype(float).median(numeric_only=True).to_dict()
        return self

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

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path: Path) -> BustModel:
        return joblib.load(path)

"""Analog search: find past forecasts that looked like this one, and see how wrong they were.

One kNN index per (variable, lead_day) over a standardised forecast-pattern vector
(configs/model.yaml ``analogs.features``). Analog-derived features are cross-fitted:
training rows only see analogs from *other* years; test rows only see training years.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors


@dataclass
class AnalogIndex:
    features: list[str]
    k: int = 8
    _fitted: dict = field(default_factory=dict)  # (variable, lead) -> (nn, mean, std, row_ids)

    def fit(self, df: pd.DataFrame) -> AnalogIndex:
        self._fitted = {}
        cols = [c for c in self.features if c in df]
        self.features = cols
        for key, g in df.groupby(["variable", "lead_day"]):
            X = g[cols].to_numpy(dtype=float)
            mu, sd = np.nanmean(X, axis=0), np.nanstd(X, axis=0) + 1e-9
            Z = np.nan_to_num((X - mu) / sd)
            nn = NearestNeighbors(n_neighbors=min(self.k, len(g))).fit(Z)
            self._fitted[key] = (nn, mu, sd, g.index.to_numpy())
        return self

    def query(self, df: pd.DataFrame, k: int | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Return (analog row ids, distances), shape (len(df), k); -1 where no index exists."""
        k = k or self.k
        ids = np.full((len(df), k), -1, dtype=np.int64)
        dist = np.full((len(df), k), np.nan)
        pos = np.arange(len(df))
        for key, g in df.groupby(["variable", "lead_day"]):
            if key not in self._fitted:
                continue
            nn, mu, sd, rows = self._fitted[key]
            Z = np.nan_to_num((g[self.features].to_numpy(dtype=float) - mu) / sd)
            kk = min(k, nn.n_samples_fit_)
            d, i = nn.kneighbors(Z, n_neighbors=kk)
            p = pos[df.index.get_indexer(g.index)]
            ids[p, :kk] = rows[i]
            dist[p, :kk] = d
        return ids, dist


def cross_fitted_analogs(
    df: pd.DataFrame, features: list[str], k: int, year: pd.Series, train_mask: pd.Series
) -> tuple[np.ndarray, np.ndarray]:
    """Analog ids/distances for every row without look-ahead into its own year.

    Training rows: index built on training rows of the other years.
    Test rows: index built on all training rows.
    """
    ids = np.full((len(df), k), -1, dtype=np.int64)
    dist = np.full((len(df), k), np.nan)
    pos = pd.Series(np.arange(len(df)), index=df.index)
    train = df[train_mask]
    for y in sorted(year[train_mask].unique()):
        pool = train[year[train_mask] != y]
        target = df[train_mask & (year == y)]
        if pool.empty or target.empty:
            continue
        i, d = AnalogIndex(features, k).fit(pool).query(target)
        ids[pos[target.index]] = i
        dist[pos[target.index]] = d
    test = df[~train_mask]
    if not test.empty and not train.empty:
        i, d = AnalogIndex(features, k).fit(train).query(test)
        ids[pos[test.index]] = i
        dist[pos[test.index]] = d
    return ids, dist


def analog_features(df: pd.DataFrame, ids: np.ndarray, label_col: str = "bust") -> pd.DataFrame:
    """Mean absolute error and bust rate of each row's analogs."""
    abs_err = df["abs_error"].to_numpy(dtype=float)
    lab = df[label_col].to_numpy(dtype=float)
    idx_pos = df.index.get_indexer(ids.ravel()).reshape(ids.shape) if len(df) else ids
    valid = (ids >= 0) & (idx_pos >= 0)
    safe = np.where(valid, idx_pos, 0)
    ae = np.where(valid, abs_err[safe], np.nan)
    lb = np.where(valid, lab[safe], np.nan)
    with np.errstate(all="ignore"):
        return pd.DataFrame(
            {
                "sig_analog_mae": np.nanmean(ae, axis=1),
                "sig_analog_bust_rate": np.nanmean(lb, axis=1),
            },
            index=df.index,
        )

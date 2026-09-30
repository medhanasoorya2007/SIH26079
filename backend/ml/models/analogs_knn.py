"""Analog search: past forecasts that looked like this one, and how wrong they turned out.

Strictly causal: a forecast issued on day I may only use analogs whose outcome was verified
by then (valid_date <= I - verification_lag_days), from the same variable and lead day, and
never rows inside replay-event windows. Features are standardised with training-year
statistics only. Brute-force kNN (the pool is a date-sorted prefix, so this stays cheap).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def causal_analogs(
    df: pd.DataFrame,
    features: list[str],
    k: int,
    lag_days: int,
    label_col: str,
    pool_mask: pd.Series,
    scale_mask: pd.Series,
) -> tuple[np.ndarray, np.ndarray]:
    """(ids, dist) of shape (len(df), k); ids are df index labels, -1 if fewer analogs exist."""
    feats = [f for f in features if f in df]
    X = df[feats].to_numpy(dtype="float64")
    mu = np.nanmean(X[scale_mask.to_numpy()], axis=0)
    sd = np.nanstd(X[scale_mask.to_numpy()], axis=0) + 1e-9
    Z = np.nan_to_num((X - mu) / sd).astype("float32")
    ids = np.full((len(df), k), -1, dtype=np.int64)
    dist = np.full((len(df), k), np.nan, dtype="float32")
    init = pd.to_datetime(df["init_date"]).to_numpy()
    valid = pd.to_datetime(df["valid_date"]).to_numpy()
    pool_ok = (pool_mask & df[label_col].notna()).to_numpy()
    index = df.index.to_numpy()
    lag = np.timedelta64(lag_days, "D")
    for _, g in df.groupby(["variable", "lead_day"], sort=False):
        pos = df.index.get_indexer(g.index)
        cand = pos[pool_ok[pos]]
        cand = cand[np.argsort(valid[cand], kind="stable")]
        cand_valid = valid[cand]
        Zc = Z[cand]
        sq_c = (Zc**2).sum(1)
        for day in np.unique(init[pos]):
            q = pos[init[pos] == day]
            n = np.searchsorted(cand_valid, day - lag, side="right")
            if n == 0:
                continue
            Zq = Z[q]
            d2 = (Zq**2).sum(1)[:, None] + sq_c[None, :n] - 2.0 * Zq @ Zc[:n].T
            kk = min(k, n)
            part = np.argpartition(d2, kk - 1, axis=1)[:, :kk]
            order = np.take_along_axis(d2, part, 1).argsort(1)
            best = np.take_along_axis(part, order, 1)
            ids[q, :kk] = index[cand[best]]
            dist[q, :kk] = np.sqrt(np.maximum(np.take_along_axis(d2, best, 1), 0))
    return ids, dist


def analog_features(df: pd.DataFrame, ids: np.ndarray, label_col: str = "bust") -> pd.DataFrame:
    """Share of analogs that busted and their mean absolute error."""
    abs_err = df["abs_error"].to_numpy(dtype=float)
    lab = df[label_col].to_numpy(dtype=float)
    idx_pos = df.index.get_indexer(ids.ravel()).reshape(ids.shape)
    valid = (ids >= 0) & (idx_pos >= 0)
    safe = np.where(valid, idx_pos, 0)
    ae = np.where(valid, abs_err[safe], np.nan)
    lb = np.where(valid, lab[safe], np.nan)
    with np.errstate(all="ignore"), np.testing.suppress_warnings() as sup:
        sup.filter(RuntimeWarning)
        return pd.DataFrame(
            {
                "sig_analog_mae": np.nanmean(ae, axis=1),
                "sig_analog_bust_rate": np.nanmean(lb, axis=1),
                "sig_analog_n": valid.sum(1).astype(float),
            },
            index=df.index,
        )

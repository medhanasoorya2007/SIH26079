import numpy as np
import pandas as pd

from ml.features.base import REGISTRY, Signal, SignalContext, compute_signals, discover
from ml.features.error_history import ErrorHistory
from ml.features.model_disagreement import ModelDisagreement
from ml.features.run_to_run import RunToRun


def _grid(n_days=20, leads=(1, 2, 3)):
    rows = []
    for i in range(n_days):
        init = pd.Timestamp("2021-07-01") + pd.Timedelta(days=i)
        for d in leads:
            rows.append(
                {
                    "init_date": init,
                    "valid_date": init + pd.Timedelta(days=d - 1),
                    "lead_day": d,
                    "region_id": "r1",
                    "variable": "rain",
                    "fc": float(10 * d + i),
                    "obs": 10.0,
                    "lat": 20.0,
                    "lon": 80.0,
                }
            )
    return pd.DataFrame(rows)


def test_registry_discovers_signal_modules():
    discover()
    for name in [
        "lead_and_place",
        "forecast_intensity",
        "model_disagreement",
        "run_to_run",
        "regime",
        "error_history",
    ]:
        assert name in REGISTRY
    assert all(issubclass(c, Signal) for c in REGISTRY.values())


def test_disagreement_values():
    df = pd.DataFrame({"fc": [10.0, 70.0], "fc_alt": [4.0, np.nan], "variable": "rain"})
    out = ModelDisagreement().compute(df, SignalContext(fit_mask=pd.Series(True, index=df.index)))
    assert out["sig_disagreement_abs"].iloc[0] == 6.0
    assert np.isnan(out["sig_disagreement_abs"].iloc[1])
    assert np.isnan(out["sig_disagreement_cat"].iloc[1])


def test_run_to_run_compares_with_yesterdays_run_same_valid_day():
    df = _grid()
    out = RunToRun().compute(df, SignalContext(fit_mask=pd.Series(True, index=df.index)))
    # init i lead 1 valid i ; yesterday's run (init i-1) lead 2 also valid i: fc = 20 + (i-1)
    row = df[(df["init_date"] == pd.Timestamp("2021-07-05")) & (df["lead_day"] == 1)].index[0]
    assert out.loc[row, "sig_jump_abs"] == abs((10 + 4) - (20 + 3))
    first = df[(df["init_date"] == pd.Timestamp("2021-07-01"))].index
    assert out.loc[first, "sig_jump_abs"].isna().all()  # no earlier run exists


def test_error_history_is_causal():
    df = _grid()
    ctx = SignalContext(fit_mask=pd.Series(True, index=df.index))
    before = ErrorHistory().compute(df, ctx)
    # make the observation on/after each init absurd: features must not change for earlier inits
    df2 = df.copy()
    target_init = pd.Timestamp("2021-07-10")
    df2.loc[df2["valid_date"] >= target_init, "obs"] = 1e6
    after = ErrorHistory().compute(df2, ctx)
    m = df["init_date"] <= target_init
    pd.testing.assert_frame_equal(before[m], after[m])


def test_compute_signals_only_adds_sig_columns():
    df = _grid()
    df["fc_alt"] = df["fc"] + 1
    out, used = compute_signals(df, SignalContext(fit_mask=pd.Series(True, index=df.index)))
    new = set(out.columns) - set(df.columns)
    assert new and all(c.startswith("sig_") for c in new)
    assert "model_disagreement" in [s.name for s in used]

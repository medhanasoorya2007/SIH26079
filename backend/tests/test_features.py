import numpy as np
import pandas as pd
import pytest

from ml.features.base import (
    FAMILIES,
    REGISTRY,
    Signal,
    SignalContext,
    compute_signals,
    discover,
    feature_families,
)
from ml.features.jumpiness import Jumpiness
from ml.features.lagged_spread import LaggedSpread, lagged_members
from ml.features.model_disagreement import ModelDisagreement
from ml.features.recent_error import RecentError


def _grid(n_days=20, leads=(1, 2, 3, 4), fc=lambda i, d: float(10 * d + i)):
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
                    "fc": fc(i, d),
                    "obs": 10.0,
                    "lat": 20.0,
                    "lon": 80.0,
                }
            )
    return pd.DataFrame(rows)


def _ctx(df, lag=2):
    return SignalContext(fit_mask=pd.Series(True, index=df.index), verification_lag_days=lag)


def test_registry_discovers_v2_signals_with_valid_families():
    discover()
    for name in [
        "lead_and_place",
        "forecast_intensity",
        "lagged_spread",
        "jumpiness",
        "recent_error",
        "synoptic",
        "upstream",
        "moisture",
        "regime",
    ]:
        assert name in REGISTRY
    assert all(issubclass(c, Signal) and c.family in FAMILIES for c in REGISTRY.values())
    for c in REGISTRY.values():  # explanations must never claim causation
        for tpl in c.explanations.values():
            texts = tpl.values() if isinstance(tpl, dict) else [tpl]
            assert all("caused" not in t.lower() for t in texts)


def test_disagreement_values():
    df = pd.DataFrame({"fc": [10.0, 70.0], "fc_alt": [4.0, np.nan], "variable": "rain"})
    out = ModelDisagreement().compute(df, _ctx(df))
    assert out["sig_disagreement_abs"].iloc[0] == 6.0
    assert np.isnan(out["sig_disagreement_abs"].iloc[1])


def test_lagged_members_pick_earlier_runs_for_same_valid_day():
    df = _grid()
    m = lagged_members(df, 3)
    row = df[(df["init_date"] == pd.Timestamp("2021-07-05")) & (df["lead_day"] == 1)].index[0]
    # run I (lead 1): 10+4 ; run I-1 (lead 2): 20+3 ; run I-2 (lead 3): 30+2
    assert m[row].tolist() == [14.0, 23.0, 32.0]
    out = LaggedSpread().compute(df, _ctx(df))
    assert np.isclose(out.loc[row, "sig_spread"], np.std([14.0, 23.0, 32.0]))
    last_lead = df[(df["init_date"] == pd.Timestamp("2021-07-05")) & (df["lead_day"] == 4)].index[0]
    assert np.isnan(out.loc[last_lead, "sig_spread"])  # no lead 5/6 runs -> no spread


def test_jumpiness_last_change_drift_and_flipflop():
    def fc(i, d):  # runs alternate between 40 and 60 mm for every valid day
        return 50.0 + (10.0 if i % 2 else -10.0)

    df = _grid(fc=fc)
    out = Jumpiness().compute(df, _ctx(df))
    row = df[(df["init_date"] == pd.Timestamp("2021-07-06")) & (df["lead_day"] == 1)].index[0]
    assert out.loc[row, "sig_jump_abs"] == 20.0
    assert out.loc[row, "sig_flipflop"] == 1.0
    assert out.loc[row, "sig_drift_2run"] == 0.0


def test_recent_error_respects_verification_lag():
    df = _grid(n_days=25)
    ctx = _ctx(df, lag=2)
    before = RecentError().compute(df, ctx)
    issue = pd.Timestamp("2021-07-15")
    df2 = df.copy()
    # rain days I-1 and later are NOT verified at issue time I: changing them must not matter
    df2.loc[df2["valid_date"] >= issue - pd.Timedelta(days=1), "obs"] = 1e4
    after = RecentError().compute(df2, ctx)
    m = df["init_date"] == issue
    pd.testing.assert_frame_equal(before[m], after[m])
    # ...but day I-2 IS verified and must matter
    df3 = df.copy()
    df3.loc[(df3["valid_date"] == issue - pd.Timedelta(days=2)) & (df3["lead_day"] == 1), "obs"] = (
        1e4
    )
    assert not RecentError().compute(df3, ctx)[m].equals(before[m])


@pytest.mark.slow
def test_no_signal_uses_unverified_observations():
    """Issue-time audit over every registered signal on a synthetic table."""
    from ml.data.synthetic import generate

    raw = generate(years=(2020,), lead_days=range(1, 6))
    issue = pd.Timestamp("2020-07-20")
    lag = 2
    fit = pd.to_datetime(raw["valid_date"]) <= issue - pd.Timedelta(days=lag)
    f1, used = compute_signals(raw, SignalContext(fit_mask=fit, verification_lag_days=lag))
    raw2 = raw.copy()
    raw2.loc[pd.to_datetime(raw2["valid_date"]) > issue - pd.Timedelta(days=lag), "obs"] *= 7.0
    f2, _ = compute_signals(raw2, SignalContext(fit_mask=fit, verification_lag_days=lag))
    m = raw["init_date"] == issue
    cols = [c for c in f1 if c.startswith("sig_")]
    pd.testing.assert_frame_equal(f1.loc[m, cols], f2.loc[m, cols])
    fams = feature_families(f1, used)
    assert set(fams.values()) <= set(FAMILIES) and "spread" in fams.values()


def test_compute_signals_only_adds_sig_columns():
    df = _grid()
    df["fc_alt"] = df["fc"] + 1
    out, used = compute_signals(df, _ctx(df))
    new = set(out.columns) - set(df.columns)
    assert new and all(c.startswith("sig_") for c in new)
    assert {"model_disagreement", "lagged_spread", "jumpiness"} <= {s.name for s in used}

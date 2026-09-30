import numpy as np
import pandas as pd

from ml.labels.bust import add_errors, make_labels

CFG = {
    "default": "p95_error",
    "definitions": {
        "p95_error": {
            "kind": "percentile_error",
            "percentile": 90,
            "group_by": ["variable", "lead_day"],
            "min_abs_error": {"rain": 5.0},
        },
        "category_flip": {
            "kind": "category_flip",
            "variable": "rain",
            "thresholds": [64.5],
            "count": "both",
        },
        "tmax_error": {"kind": "absolute_error", "variable": "tmax", "threshold": 3.0},
        "decision": {"kind": "any_of", "of": ["category_flip", "tmax_error"]},
    },
}


def _df(fc, obs, lead=1, var="rain", split="train"):
    n = len(fc)
    return pd.DataFrame(
        {"fc": fc, "obs": obs, "lead_day": lead, "variable": var, "split": split}, index=range(n)
    )


def test_percentile_threshold_uses_training_rows_only():
    train = _df(np.zeros(100), np.arange(100, dtype=float))  # abs errors 0..99
    test = _df(np.zeros(3), np.array([50.0, 95.0, 1000.0]), split="test")
    df = add_errors(pd.concat([train, test], ignore_index=True))
    res = make_labels(df, df["split"] == "train", CFG)
    thr = res.thresholds["p95_error"]["values"]["rain|1"]
    assert 88 < thr < 91  # 90th percentile of 0..99, unaffected by the 1000 mm test error
    assert res.labels["bust"].iloc[-3:].tolist() == [0.0, 1.0, 1.0]


def test_percentile_floor_prevents_tiny_busts():
    df = add_errors(_df(np.zeros(50), np.linspace(0, 2, 50)))  # all errors <= 2 mm
    res = make_labels(df, df["split"] == "train", CFG)
    assert res.thresholds["p95_error"]["values"]["rain|1"] == 5.0
    assert res.labels["bust"].sum() == 0


def test_category_flip_counts_misses_and_false_alarms():
    df = add_errors(_df(np.array([10.0, 80.0, 70.0, 5.0]), np.array([90.0, 20.0, 100.0, 1.0])))
    lab = make_labels(df, df["split"] == "train", CFG).labels["bust_category_flip"]
    assert lab.tolist() == [1.0, 1.0, 0.0, 0.0]  # miss, false alarm, hit, correct negative


def test_unverified_rows_are_nan_and_any_of_combines():
    df = add_errors(_df(np.array([10.0, 80.0]), np.array([np.nan, 20.0])))
    labs = make_labels(df, df["split"] == "train", CFG).labels
    assert np.isnan(labs["bust_category_flip"].iloc[0])
    assert labs["bust_decision"].iloc[1] == 1.0
    assert np.isnan(labs["bust_tmax_error"]).all()  # not applicable to rain

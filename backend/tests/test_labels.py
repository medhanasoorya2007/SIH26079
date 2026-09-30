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


IMD_CFG = {
    "default": "imd_category",
    "definitions": {
        "imd_category": {
            "kind": "imd_category",
            "variable": "rain",
            "edges": [64.5, 115.6, 204.5],
            "min_category_gap": 2,
            "missed_warning_from": 1,
        },
        "tmax_error": {"kind": "absolute_error", "variable": "tmax", "threshold": 3.0},
    },
}


def test_imd_category_boundaries():
    from ml.labels.bust import imd_category

    assert imd_category([64.4, 64.5, 115.5, 115.6, 204.4, 204.5]).tolist() == [0, 1, 1, 2, 2, 3]


def test_imd_category_bust_rules():
    # fc, obs -> expected
    cases = [
        (10.0, 70.0, 1.0),  # missed warning: obs Heavy, fc below Heavy
        (70.0, 120.0, 0.0),  # Heavy vs Very heavy: 1 class apart, warning was issued
        (70.0, 210.0, 1.0),  # Heavy vs Extremely heavy: 2 classes apart
        (130.0, 20.0, 1.0),  # Very heavy forecast, light observed: 2 classes (false alarm)
        (70.0, 20.0, 0.0),  # Heavy forecast, light observed: 1 class only
        (5.0, 60.0, 0.0),  # both Light/Moderate
    ]
    df = add_errors(_df(np.array([c[0] for c in cases]), np.array([c[1] for c in cases])))
    lab = make_labels(df, df["split"] == "train", IMD_CFG).labels["bust"]
    assert lab.tolist() == [c[2] for c in cases]


def test_tmax_bust_threshold():
    df = add_errors(_df(np.array([40.0, 40.0, 40.0]), np.array([37.0, 37.5, 44.0]), var="tmax"))
    labs = make_labels(df, df["split"] == "train", IMD_CFG).labels
    assert labs["bust_tmax_error"].tolist() == [1.0, 0.0, 1.0]
    assert labs["bust_imd_category"].isna().all()

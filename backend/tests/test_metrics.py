import numpy as np

from ml.eval.metrics import recall_at_far, reliability, score_block


def test_recall_at_far_perfect_and_random():
    y = np.array([0] * 90 + [1] * 10)
    perfect = np.r_[np.zeros(90), np.ones(10)]
    assert recall_at_far(y, perfect, 0.0)["recall"] == 1.0
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 20000)
    r = recall_at_far(y, rng.random(20000), 0.10)
    assert abs(r["recall"] - 0.10) < 0.03 and r["far"] <= 0.10


def test_reliability_bins_cover_all_samples():
    p = np.linspace(0, 1, 101)
    y = (p > 0.5).astype(int)
    rel = reliability(y, p, bins=10)
    assert sum(b["count"] for b in rel) == 101
    assert rel[0]["obs_freq"] == 0.0 and rel[-1]["obs_freq"] == 1.0


def test_score_block_handles_nan_and_brier():
    y = np.array([0, 1, np.nan, 1, 0])
    p = np.array([0.1, 0.9, 0.5, 0.8, np.nan])
    s = score_block(y, p)
    assert s["n"] == 3 and s["n_busts"] == 2
    assert np.isclose(s["brier"], np.mean([(0.1 - 0) ** 2, (0.9 - 1) ** 2, (0.8 - 1) ** 2]))


def test_threshold_at_far_is_fitted_on_given_block_and_operating_point_scores():
    from ml.eval.metrics import operating_point, threshold_at_far

    y = np.array([0] * 90 + [1] * 10)
    p = np.r_[np.linspace(0, 0.5, 90), np.linspace(0.3, 0.9, 10)]
    thr = threshold_at_far(y, p, 0.10)
    op = operating_point(y, p, thr)
    assert op["far"] <= 0.10 + 1e-9
    assert op["tp"] + op["fn"] == 10
    assert np.isclose(op["csi"], op["tp"] / (op["tp"] + op["fp"] + op["fn"]))


def test_relative_value_perfect_and_climatology():
    from ml.eval.costloss import relative_value

    y = np.array([0] * 95 + [1] * 5)
    assert np.isclose(relative_value(y, y.astype(float), 0.2), 1.0)
    assert np.isclose(relative_value(y, np.full(100, 0.05), 0.2), 0.0)  # never acts = climatology


def test_early_warning_counts_continuous_flags_from_day1():
    import pandas as pd

    from ml.eval.early_warning import event_lead_times

    vd = pd.Timestamp("2021-07-10")
    rows = [
        {"region_id": "r", "valid_date": vd, "lead_day": d, "bust": 1 if d == 1 else 0, "p": p}
        for d, p in zip(range(1, 6), [0.9, 0.9, 0.9, 0.1, 0.9], strict=True)
    ]
    ev = event_lead_times(pd.DataFrame(rows), {"m": "p"}, {"m": 0.5})
    assert ev["m"].tolist() == [3]  # Day 4 not flagged breaks the chain; Day 5 does not count


def test_bootstrap_ci_contains_point_estimate():
    from sklearn.metrics import average_precision_score

    from ml.eval.metrics import bootstrap_pr_auc

    rng = np.random.default_rng(1)
    y = rng.random(2000) < 0.05
    s = y * 0.5 + rng.random(2000)
    out = bootstrap_pr_auc(
        y, {"a": s, "b": rng.random(2000)}, np.repeat(np.arange(200), 10), n_boot=100
    )
    lo, hi = out["pr_auc_ci"]["a"]
    assert lo <= average_precision_score(y, s) <= hi
    assert out["diff_vs_first_ci"]["b"][0] > 0

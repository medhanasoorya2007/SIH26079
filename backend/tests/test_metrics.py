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

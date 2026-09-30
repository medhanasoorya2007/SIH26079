import numpy as np
import pandas as pd

from ml.explain.grouped_shap import family_breakdown, family_contributions, family_sentence
from ml.explain.pathways import pathway
from ml.models.confidently_wrong import ConfidentlyWrong


def test_family_contributions_sum_and_share():
    feats = ["a", "b", "c", "d"]
    fams = {"a": "spread", "b": "spread", "c": "drift", "d": "moisture"}
    contrib = np.array([[1.0, 0.5, -0.2, 0.5]])
    sums, pct, names = family_contributions(contrib, feats, fams)
    got = dict(zip(names, sums[0], strict=True))
    assert np.isclose(got["spread"], 1.5) and np.isclose(got["drift"], -0.2)
    share = dict(zip(names, pct[0], strict=True))
    assert (
        np.isclose(share["spread"], 75.0)
        and np.isclose(share["moisture"], 25.0)
        and share["drift"] == 0.0
    )
    bd = family_breakdown(sums[0], pct[0], names)
    assert bd[0]["family"] == "spread" and bd[-1]["direction"] == "lowers"
    text = family_sentence(bd)
    assert "associated with" in text and "caused" not in text.lower()


def test_pathway_uses_only_flagged_families_in_template_order():
    bd = [
        {"family": "moisture", "pct": 40.0, "direction": "raises"},
        {"family": "upstream", "pct": 35.0, "direction": "raises"},
        {"family": "drift", "pct": 5.0, "direction": "raises"},  # below threshold
        {"family": "spread", "pct": 0.0, "direction": "lowers"},
    ]
    steps = pathway("Monsoon depression", bd, "Odisha")
    assert [s["family"] for s in steps] == ["upstream", "moisture", "outcome"]
    assert steps[-1]["text"].endswith("Odisha")
    assert (
        pathway("Normal", [{"family": "context", "pct": 3.0, "direction": "raises"}], "X") is None
    )


def _cw_frame(n=300, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "sig_spread": rng.uniform(0, 30, n),
            "sig_regime_label": np.where(np.arange(n) % 2, "Monsoon depression", "Normal"),
            "valid_date": pd.Timestamp("2019-07-10"),
        }
    )


def test_low_spread_is_lowest_third_within_regime_and_season():
    df = _cw_frame()
    cw = ConfidentlyWrong(min_group_size=30).fit(df)
    low = cw.low_spread(df)
    for reg in df["sig_regime_label"].unique():
        m = (df["sig_regime_label"] == reg).to_numpy()
        assert abs(low[m].mean() - 1 / 3) < 0.02
    # NaN spread is never "low spread"
    df.loc[0, "sig_spread"] = np.nan
    assert not cw.low_spread(df)[0]


def test_alert_requires_low_spread_high_prob_and_analog_agreement():
    df = _cw_frame(n=6)
    df["sig_spread"] = [1.0, 1.0, 1.0, 1.0, 50.0, 1.0]
    cw = ConfidentlyWrong(min_group_size=1, analog_min_rate=0.25)
    cw.thresholds, cw.month_fallback, cw.global_fallback = {}, {7: 5.0}, 5.0
    prob = np.array([0.30, 0.01, 0.30, 0.30, 0.30, np.nan])
    analog = np.array([0.50, 0.50, 0.00, np.nan, 0.50, 0.50])
    got = cw.alerts(df, prob, high_threshold=0.1, analog_rate=analog)
    assert got.tolist() == [True, False, False, False, False, False]

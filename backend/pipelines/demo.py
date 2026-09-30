"""`make demo`: reproduce the headline numbers offline, then start API + dashboard.

    uv run python -m pipelines.demo [--source wb2] [--no-serve]

Reads only cached files (data/artifacts/<SOURCE> or the committed data/sample/<SOURCE>):
recomputes test-year PR-AUC, recall at the calibration-frozen 10% false-alarm threshold and
recall on low-spread busts for BustGuard and both baselines, and checks them against the
exported metrics. No network access.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from app.services.store import available_sources
from ml.config import REPO_DIR
from ml.eval.metrics import operating_point, threshold_at_far


def reproduce(source: str) -> bool:
    avail = available_sources()
    if source not in avail:
        raise SystemExit(f"no cached bundle for {source}; have {list(avail)}")
    folder = avail[source]
    meta = json.loads((folder / "meta.json").read_text())
    df = pd.read_parquet(folder / "serving.parquet")
    cols = meta["method_columns"]
    far = meta["operating_point"]["false_alarm_rate"]
    cal = df[(df["split"] == "calib") & (df["holdout_event"] == "") & df["bust"].notna()]
    te = df[(df["split"] == "test") & df["bust"].notna()]
    for c in cols.values():
        te = te[te[c].notna()]
    head = meta["headline"]
    print(
        f"\nBustGuard headline, reproduced offline from {folder} (test years {head['test_years']}, {len(te):,} forecasts, base rate {te['bust'].mean():.2%})\n"
    )
    print(
        f"{'method':32s} {'PR-AUC':>8s} {'exported':>9s} {'recall@op':>10s} {'FAR':>6s} {'low-spread recall':>18s}"
    )
    ok = True
    low = te["low_spread"].to_numpy() & (te["bust"].to_numpy() == 1)
    for m, c in cols.items():
        pr = average_precision_score(te["bust"], te[c])
        thr = threshold_at_far(cal["bust"], cal[c], far)
        op = operating_point(te["bust"], te[c], thr)
        lr = float((te[c].to_numpy()[low] >= thr).mean()) if low.any() else float("nan")
        exp = head["pr_auc"][m]
        ok &= bool(np.isclose(pr, exp, atol=2e-3))
        print(f"{m:32s} {pr:8.3f} {exp:9.3f} {op['recall']:10.1%} {op['far']:6.1%} {lr:18.1%}")
    print(
        f"\n{'OK: matches exported metrics' if ok else 'MISMATCH with exported metrics'} ({int(low.sum())} low-spread busts)\n"
    )
    return ok


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="wb2")
    ap.add_argument("--no-serve", action="store_true")
    args = ap.parse_args(argv)
    ok = reproduce(args.source)
    if args.no_serve:
        sys.exit(0 if ok else 1)
    env = {**os.environ, "BUSTGUARD_SOURCE": args.source}
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=REPO_DIR / "backend",
        env=env,
    )
    web = subprocess.Popen("npm run dev", cwd=REPO_DIR / "frontend", shell=True)
    print("API: http://localhost:8000/docs   Dashboard: http://localhost:3000   (Ctrl+C to stop)")
    try:
        while api.poll() is None and web.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in (api, web):
            p.terminate()


if __name__ == "__main__":
    main()

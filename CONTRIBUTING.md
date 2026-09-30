# Contributing to BustGuard

## Branches

```
main      stable demo builds only (merged from dev)
dev       integration branch: all feature work lands here first
feature/<name>   your work, branched off dev
```

1. `git checkout dev && git pull`
2. `git checkout -b feature/<short-name>` (e.g. `feature/signal-cape`, `feature/replay-ui`)
3. Commit with **conventional commits**: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`
4. `git push -u origin feature/<short-name>` and open a PR **into `dev`**
5. `dev` -> `main` only for a stable, demo-ready build (tests green, `make demo` works)

## Before you commit

```bash
make lint test            # ruff + pytest (+ eslint for the frontend)
python scripts/scan_repo.py   # staged files: no secrets, nothing > 20 MB
```

`pre-commit install` runs the same checks automatically. Never commit `data/raw`,
`data/processed`, `data/artifacts`, `.env`, or model files; only `data/sample/` (< 20 MB).

## Adding a new signal (one file)

Create `backend/ml/features/<your_signal>.py`:

```python
import pandas as pd
from ml.features.base import Signal, SignalContext, register

@register
class Cape(Signal):
    name = "cape"
    description = "Forecast CAPE: deep convection makes rainfall amounts unpredictable."
    requires = ("ctx_cape",)          # raw/context columns you need
    order = 50                        # run after the signals you depend on
    explanations = {"sig_cape": "High instability forecast (CAPE {value:.0f} J/kg): convective rain is hit-or-miss."}

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        return pd.DataFrame({"sig_cape": df["ctx_cape"]}, index=df.index)
```

It is discovered automatically, used as a model feature, and its sentence appears in the
dashboard whenever it is among the top-3 reasons. Rules:

* output columns must start with `sig_`;
* never use the row's own `obs` (that is the future);
* fit any climatology on `ctx.fit_mask` rows only (training years);
* add a test in `backend/tests/test_features.py`.

## Adding a data source / model

* Data: a builder in `backend/ml/data/` that returns the raw schema in `ml/schema.py`
  (plus any `ctx_*` columns), wired into `pipelines/dataset.py::build_raw`.
* Model: a class in `backend/ml/models/` with `fit` / `predict_proba`; register it in
  `pipelines/train.py` and it is evaluated by `pipelines/evaluate.py` automatically.
* Bust definitions: `backend/configs/labels.yaml` (no code change for the existing kinds).

## Synthetic data

`make synthetic` runs everything on generated data (`source == "SYNTHETIC"`). It exists
for development only; never quote its metrics as results.

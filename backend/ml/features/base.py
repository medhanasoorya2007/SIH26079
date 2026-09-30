"""Signal interface + registry.

A *signal* turns raw forecast/context columns into ``sig_*`` feature columns and knows
how to explain them in plain meteorological language. To add one, drop a new module in
``ml/features/`` with a class decorated by ``@register``; it is discovered automatically:

    from ml.features.base import Signal, SignalContext, register

    @register
    class MySignal(Signal):
        name = "my_signal"
        description = "What this measures and why it predicts busts."
        requires = ("fc",)
        order = 50
        explanations = {"sig_my_value": "Plain-English reason with {value:.1f} units."}

        def compute(self, df, ctx):
            return pd.DataFrame({"sig_my_value": df["fc"] * 2}, index=df.index)

Rules: never use ``obs`` of the row itself (that is the future); fit climatologies only on
``ctx.fit_mask`` rows (training years) to avoid leakage.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import ClassVar

import pandas as pd


@dataclass
class SignalContext:
    """Shared information passed to every signal."""

    fit_mask: pd.Series  # True for rows that may be used to fit climatologies (train years)
    verification_lag_days: int = 2  # newest verified rain day at issue day I is I - lag
    cache: dict = field(default_factory=dict)


class Signal:
    """Base class for all bust-predictive signals."""

    name: ClassVar[str] = "base"
    description: ClassVar[str] = ""
    requires: ClassVar[tuple[str, ...]] = ()
    order: ClassVar[int] = 100  # lower runs first (later signals may use earlier sig_ columns)
    # feature column -> sentence template; {value} is the feature value, {row[col]} any column
    explanations: ClassVar[dict[str, str]] = {}
    # features that should not be used for training (e.g. purely descriptive tags)
    exclude_from_model: ClassVar[tuple[str, ...]] = ()
    # feature family (disagreement, spread, drift, pressure_wind, moisture, upstream, regime,
    # context); ``families`` overrides it per output column
    family: ClassVar[str] = "context"
    families: ClassVar[dict[str, str]] = {}

    def available(self, df: pd.DataFrame) -> bool:
        return all(c in df.columns and df[c].notna().any() for c in self.requires)

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:  # pragma: no cover
        raise NotImplementedError


REGISTRY: dict[str, type[Signal]] = {}


def register(cls: type[Signal]) -> type[Signal]:
    if cls.name in REGISTRY and REGISTRY[cls.name] is not cls:
        raise ValueError(f"signal name clash: {cls.name}")
    REGISTRY[cls.name] = cls
    return cls


def discover() -> dict[str, type[Signal]]:
    """Import every module in ml.features so their @register decorators run."""
    import ml.features as pkg

    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name not in {"base", "registry"}:
            importlib.import_module(f"ml.features.{mod.name}")
    return REGISTRY


def compute_signals(
    df: pd.DataFrame, ctx: SignalContext, only: list[str] | None = None
) -> tuple[pd.DataFrame, list[Signal]]:
    """Run all available signals in order; returns (df with sig_ columns, signals used)."""
    discover()
    used: list[Signal] = []
    out = df.copy()
    for cls in sorted(REGISTRY.values(), key=lambda c: (c.order, c.name)):
        if only and cls.name not in only:
            continue
        sig = cls()
        if not sig.available(out):
            continue
        new = sig.compute(out, ctx)
        bad = [c for c in new.columns if not c.startswith("sig_")]
        if bad:
            raise ValueError(f"signal {sig.name} produced non-sig_ columns: {bad}")
        out = out.drop(columns=[c for c in new.columns if c in out.columns]).join(new)
        sig.outputs = list(new.columns)
        used.append(sig)
    return out, used


def feature_columns(df: pd.DataFrame, signals: list[Signal]) -> list[str]:
    """Model features = all sig_ columns except those signals flag as descriptive."""
    excluded = {c for s in signals for c in s.exclude_from_model}
    return [c for c in df.columns if c.startswith("sig_") and c not in excluded]


FAMILIES = (
    "disagreement",
    "spread",
    "drift",
    "pressure_wind",
    "moisture",
    "upstream",
    "regime",
    "context",
)


def feature_families(df: pd.DataFrame, signals: list[Signal]) -> dict[str, str]:
    """feature column -> family, for every model feature."""
    out: dict[str, str] = {}
    feats = set(feature_columns(df, signals))
    for s in signals:
        for c in getattr(s, "outputs", []):
            if c in feats:
                out[c] = s.families.get(c, s.family)
    for c in feats:  # features added outside signals (e.g. analog features) default to context
        out.setdefault(c, "context")
    bad = {c: f for c, f in out.items() if f not in FAMILIES}
    if bad:
        raise ValueError(f"unknown families: {bad}")
    return out


def explanation_templates(signals: list[Signal]) -> dict[str, str]:
    out: dict[str, str] = {}
    for s in signals:
        out.update(s.explanations)
    return out

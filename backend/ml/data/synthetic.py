"""!!! SYNTHETIC / FAKE DATA GENERATOR !!!

Produces a table with exactly the same schema as the real WeatherBench 2 builder so the
whole pipeline (labels -> signals -> model -> eval -> API -> UI) can be developed and
tested before real data arrives. NOTHING produced here is an observation or a forecast:

* every row has ``source == "SYNTHETIC"`` and ``is_synthetic == True``;
* files are written as ``data/processed/SYNTHETIC_*.parquet``;
* the API and the dashboard show a red "SYNTHETIC DATA" banner when serving it;
* metrics computed on it only prove the plumbing works, not that BustGuard is skilful.

The toy "atmosphere": seasonal cycle x intraseasonal active/break oscillation, Bay of
Bengal depressions moving west-north-west, occasional western disturbances over NW India,
gamma-distributed convective rain. Two toy "models" (HRES-like and GraphCast-like) see
the state with lead-dependent position/intensity errors, partially correlated with
each other, and may miss depressions that form after initialisation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.regions import load_regions

SOURCE = "SYNTHETIC"

# climatological JJAS rain (mm/day) by region id override, else by zone
_ZONE_BASE = {"NE": 14.0, "East": 9.0, "NW": 4.5, "Central": 8.0, "South": 4.0}
_REGION_BASE = {
    "mumbai": 22,
    "ratnagiri": 26,
    "panaji": 26,
    "mangaluru": 28,
    "kozhikode": 22,
    "shillong": 25,
    "gangtok": 18,
    "jalpaiguri": 24,
    "port_blair": 14,
    "jodhpur": 1.8,
    "bikaner": 1.5,
    "barmer": 1.5,
    "bhuj": 2.0,
    "srinagar": 2.0,
    "chennai": 3.0,
    "madurai": 2.0,
    "anantapur": 2.0,
}
_CORE_ZONES = {"Central", "NW"}


@dataclass
class _System:
    genesis: int  # day index
    lat0: float
    lon0: float
    dlat: float  # deg / day
    dlon: float
    life: int  # days
    depth: float  # hPa
    kind: str  # "depression" | "wd"

    def state(self, t: int) -> tuple[float, float, float] | None:
        age = t - self.genesis
        if age < 0 or age >= self.life:
            return None
        env = np.sin(np.pi * (age + 0.5) / self.life)  # grow then decay
        return self.lat0 + self.dlat * age, self.lon0 + self.dlon * age, self.depth * env


def _dist_deg(lat1, lon1, lat2, lon2):
    return np.sqrt((lat1 - lat2) ** 2 + ((lon1 - lon2) * np.cos(np.deg2rad(lat1))) ** 2)


def generate(
    years=(2018, 2019, 2020, 2021, 2022), lead_days=range(1, 11), seed: int = 7
) -> pd.DataFrame:
    """Return a SYNTHETIC raw table (see ml/schema.py for the columns)."""
    rng = np.random.default_rng(seed)
    reg = load_regions().reset_index(drop=True)
    lat, lon = reg["lat"].to_numpy(), reg["lon"].to_numpy()
    base = np.array(
        [_REGION_BASE.get(i, _ZONE_BASE[z]) for i, z in zip(reg["id"], reg["zone"], strict=True)]
    )
    core = reg["zone"].isin(_CORE_ZONES).to_numpy() & (lon > 72)
    nw = (reg["zone"] == "NW").to_numpy()
    ne_like = reg["zone"].isin(["NE"]).to_numpy() | (lat > 29)
    # neighbours within 3.5 degrees (incl. self) for neighbourhood statistics
    dmat = _dist_deg(lat[:, None], lon[:, None], lat[None, :], lon[None, :])
    neigh = dmat <= 3.5
    # "upstream" = regions 2-7 deg to the east-south-east (monsoon systems move WNW)
    dlon = lon[None, :] - lon[:, None]
    dlat = lat[None, :] - lat[:, None]
    upstream = (dlon >= 2) & (dlon <= 7) & (dlat >= -3.5) & (dlat <= 1)
    leads = list(lead_days)
    rows = []

    for year in years:
        n_days = 132  # Jun 1 .. Oct 10
        dates = pd.date_range(f"{year}-06-01", periods=n_days, freq="D")
        t_idx = np.arange(n_days)
        seasonal = 0.55 + 0.45 * np.sin(np.pi * np.clip(t_idx, 0, 122) / 122)
        # intraseasonal oscillation (active > 0, break < 0)
        phase = rng.uniform(0, 2 * np.pi)
        noise = np.zeros(n_days)
        for t in range(1, n_days):
            noise[t] = 0.8 * noise[t - 1] + rng.normal(0, 0.25)
        iso = 0.9 * np.sin(2 * np.pi * t_idx / rng.uniform(35, 48) + phase) + noise

        systems: list[_System] = []
        t = int(rng.integers(0, 6))
        while t < n_days:
            systems.append(
                _System(
                    t,
                    rng.normal(20.5, 1.2),
                    rng.normal(89.0, 1.0),
                    rng.normal(0.45, 0.2),
                    rng.normal(-2.4, 0.6),
                    int(rng.integers(3, 7)),
                    rng.uniform(4, 12),
                    "depression",
                )
            )
            t += int(rng.exponential(11)) + 3
        t = int(rng.integers(0, 20))
        while t < n_days:
            systems.append(
                _System(
                    t,
                    rng.normal(32.5, 1.0),
                    rng.normal(75.5, 1.5),
                    0.0,
                    1.5,
                    2,
                    rng.uniform(3, 6),
                    "wd",
                )
            )
            t += int(rng.exponential(24)) + 8

        def expected(tt, iso_v, sys_states, seasonal=seasonal, n_days=n_days):
            """Expected rain (mm) and MSLP (hPa) for all regions given a (believed) state."""
            mult = np.where(
                core,
                np.exp(0.55 * iso_v),
                np.where(ne_like, np.exp(-0.35 * iso_v), np.exp(0.2 * iso_v)),
            )
            rain = base * seasonal[min(tt, n_days - 1)] * mult
            mslp = 1004.0 - 0.25 * (lat - 15) + 1.5 * (lat < 12) - 0.8 * iso_v * core
            vort = np.zeros_like(lat)
            for slat, slon, depth, kind in sys_states:
                d = _dist_deg(lat, lon, slat, slon)
                w = np.exp(-(d**2) / (2 * (2.6 if kind == "depression" else 2.0) ** 2))
                rain = rain + depth * (7.5 if kind == "depression" else 5.0) * w
                mslp = mslp - depth * np.exp(-(d**2) / (2 * 3.5**2))
                vort = vort + depth * 0.45 * w * (1 - d**2 / (2 * 3.0**2))
            return rain, mslp, vort

        # truth
        truth_rain = np.zeros((n_days, len(reg)))
        truth_states = []
        for tt in range(n_days):
            st = [(*s.state(tt), s.kind) for s in systems if s.state(tt) is not None]
            truth_states.append(st)
            mu, _, _ = expected(tt, iso[tt], st)
            shape = 0.9
            truth_rain[tt] = rng.gamma(shape, np.maximum(mu, 0.05) / shape) * (
                rng.random(len(reg)) > 0.08
            )

        for i in range(122):  # inits Jun 1 .. Sep 30
            # model-specific persistent errors for this init (partially shared between models)
            shared = rng.normal(0, 1, 4)
            for d in leads:
                tt = i + d - 1
                if tt >= n_days:
                    continue
                spread = 0.12 + 0.09 * d
                models = {}
                for mname, rho, smooth in (("fc", 0.55, 1.0), ("fc_alt", 0.55, 0.92)):
                    own = rng.normal(0, 1, 4)
                    e = rho * shared + np.sqrt(1 - rho**2) * own
                    iso_b = iso[tt] + spread * 1.1 * e[0]
                    states = []
                    for s in systems:
                        stt = s.state(tt)
                        if stt is None:
                            continue
                        # systems born after init may be missed entirely
                        if s.genesis > i and rng.random() > np.exp(-(s.genesis - i) / 2.5):
                            continue
                        slat, slon, depth = stt
                        pos_err = 0.55 * d * (1.4 if s.kind == "depression" else 1.0)
                        states.append(
                            (
                                slat + pos_err * 0.6 * e[1],
                                slon + pos_err * e[2],
                                depth * np.exp(0.12 * d * e[3] * 0.5),
                                s.kind,
                            )
                        )
                    if rng.random() < 0.015 * d:  # occasional phantom low at long leads
                        states.append(
                            (
                                rng.normal(21, 1.5),
                                rng.normal(86, 3),
                                rng.uniform(3, 7),
                                "depression",
                            )
                        )
                    rain, mslp, vort = expected(tt, iso_b, states)
                    if mname == "fc":
                        iso_b_primary = iso_b
                    rain = smooth * rain * np.exp(rng.normal(0, 0.12 + 0.03 * d, len(reg)))
                    models[mname] = (rain, mslp + rng.normal(0, 0.4, len(reg)), vort, states)
                fc, mslp, vort, states = models["fc"]
                nb_std = np.array([fc[m].std() for m in neigh])
                nb_max = np.array([fc[m].max() for m in neigh])
                up_fc = np.array([fc[m].mean() if m.any() else np.nan for m in upstream])
                up_mslp = np.array([mslp[m].mean() if m.any() else np.nan for m in upstream])
                # toy moisture at issue time: wetter in active phases and near lows (FAKE)
                tcwv = 48 + 6 * iso[i] * core + 4 * (vort > 1) + rng.normal(0, 2, len(reg))
                bob = [
                    s
                    for s in states
                    if s[3] == "depression" and 80 <= s[1] <= 95 and 10 <= s[0] <= 24
                ]
                bob_min = 1003.5 - (max((s[2] for s in bob), default=0.0)) + rng.normal(0, 0.5)
                arb_min = 1005.0 + rng.normal(0, 0.8) - (rng.random() < 0.03) * rng.uniform(3, 8)
                rows.append(
                    pd.DataFrame(
                        {
                            "init_date": dates[i],
                            "region_id": reg["id"].to_numpy(),
                            "variable": "rain",
                            "lead_day": d,
                            "valid_date": dates[tt],
                            "fc": np.round(fc, 2),
                            "fc_alt": np.round(models["fc_alt"][0], 2),
                            "obs": np.round(truth_rain[tt], 2),
                            "lat": lat,
                            "lon": lon,
                            "zone": reg["zone"].to_numpy(),
                            "source": SOURCE,
                            "is_synthetic": True,
                            "ctx_mslp": np.round(mslp, 2),
                            "ctx_geo_vort": np.round(vort, 3),
                            "ctx_fc_sub_std": nb_std,
                            "ctx_fc_sub_max": nb_max,
                            "ctx_up_fc": up_fc,
                            "ctx_up_mslp": up_mslp,
                            "ctx_geo_u": 6.0
                            + 3.0 * iso_b_primary * core
                            + rng.normal(0, 1.5, len(reg)),
                            "ctx_geo_v": rng.normal(0, 2.0, len(reg)),
                            "ctx_tcwv": tcwv,
                            "ctx_up_tcwv": np.array(
                                [tcwv[m].mean() if m.any() else np.nan for m in upstream]
                            ),
                            "ctx_bob_min_mslp": bob_min,
                            "ctx_arb_min_mslp": arb_min,
                            "ctx_core_fc": fc[core].mean(),
                            "ctx_nw_mslp": mslp[nw].mean(),
                        }
                    )
                )
    out = pd.concat(rows, ignore_index=True)
    out["init_date"] = pd.to_datetime(out["init_date"])
    out["valid_date"] = pd.to_datetime(out["valid_date"])
    return out

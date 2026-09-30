"""IMD meteorological subdivisions: grid-cell partition, area-mean weights, map geometry.

See configs/subdivisions.yaml for how cells are assigned. Everything is cached in
data/processed/subdivisions_grid.npz; the map GeoJSON goes to data/sample/geo/ (committed)
so the dashboard needs no external boundary service.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from ml.config import PROCESSED_DIR, RAW_DIR, SAMPLE_DIR, load_config

GRID_CACHE = PROCESSED_DIR / "subdivisions_grid.npz"
GEOJSON_PATH = SAMPLE_DIR / "geo" / "subdivisions.geojson"
SHAPES_DIR = RAW_DIR / "shapes"


@lru_cache(maxsize=1)
def subdivision_table() -> pd.DataFrame:
    """id, name, zone for every configured subdivision (index = id)."""
    rows = load_config("subdivisions")["subdivisions"]
    df = pd.DataFrame([{k: r[k] for k in ("id", "name", "zone")} for r in rows])
    if df["id"].duplicated().any():
        raise ValueError("duplicate subdivision ids")
    return df.set_index("id", drop=False)


def _cell_polygons_state(lat: np.ndarray, lon: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """State name for every masked cell (nearest polygon within 0.6 deg for coastal cells)."""
    from shapely import STRtree, points
    from shapely.geometry import shape

    cfg = load_config("subdivisions")
    feats = json.loads((SHAPES_DIR / cfg["state_file"]).read_text(encoding="utf-8"))["features"]
    feats = [f for f in feats if f["properties"].get("adm0_a3") == "IND"]
    geoms = [shape(f["geometry"]) for f in feats]
    names = np.array([f["properties"]["name"] for f in feats], dtype=object)
    tree = STRtree(geoms)
    ii, jj = np.where(mask)
    pts = points(lon[jj], lat[ii])
    inside = tree.query(pts, predicate="within")  # (2, n) -> point idx, geom idx
    out = np.full(len(pts), None, dtype=object)
    out[inside[0]] = names[inside[1]]
    miss = np.where(out == None)[0]  # noqa: E711
    if len(miss):
        near, dist = tree.query_nearest(pts[miss], return_distance=True, all_matches=False)
        ok = dist <= 0.6
        out[miss[near[0][ok]]] = names[near[1][ok]]
    grid = np.full(mask.shape, None, dtype=object)
    grid[ii, jj] = out
    return grid


def build_partition(lat: np.ndarray, lon: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Subdivision index (row of subdivision_table) for every IMD cell, -1 outside."""
    cfg = load_config("subdivisions")["subdivisions"]
    table = subdivision_table()
    idx_of = {sid: i for i, sid in enumerate(table.index)}
    official = SHAPES_DIR / load_config("subdivisions")["official_file"]
    assign = np.full(mask.shape, -1, dtype=np.int16)
    ii, jj = np.where(mask)
    if official.exists():  # preferred: official IMD boundaries if the user provides them
        from shapely import STRtree, points
        from shapely.geometry import shape

        feats = json.loads(official.read_text(encoding="utf-8"))["features"]
        by_name = {r["name"]: idx_of[r["id"]] for r in cfg}
        geoms = [shape(f["geometry"]) for f in feats]
        tree = STRtree(geoms)
        hit = tree.query(points(lon[jj], lat[ii]), predicate="within")
        for p, g in zip(*hit, strict=True):
            assign[ii[p], jj[p]] = by_name.get(feats[g]["properties"]["name"], -1)
        return assign
    state = _cell_polygons_state(lat, lon, mask)
    by_state: dict[str, list[dict]] = {}
    for r in cfg:
        for s in r["states"]:
            by_state.setdefault(s, []).append(r)
    for i, j in zip(ii, jj, strict=True):
        st = state[i, j]
        cands = by_state.get(st)
        if not cands:
            continue
        if len(cands) == 1:
            assign[i, j] = idx_of[cands[0]["id"]]
            continue
        best, best_d = None, np.inf
        for r in cands:
            a = np.asarray(r["anchors"], dtype=float)
            d = np.min(
                (a[:, 0] - lat[i]) ** 2 + ((a[:, 1] - lon[j]) * np.cos(np.deg2rad(lat[i]))) ** 2
            )
            if d < best_d:
                best, best_d = r, d
        assign[i, j] = idx_of[best["id"]]
    return _fill_unassigned(assign, mask, lat, lon, idx_of)


def _fill_unassigned(assign, mask, lat, lon, idx_of) -> np.ndarray:
    """IMD land cells outside the Natural Earth state polygons. In the north these are parts
    of Jammu & Kashmir and Ladakh that IMD's grid (India's official extent) includes but the
    50m polygons do not; elsewhere they are coastal slivers -> nearest assigned cell."""
    cfg = load_config("subdivisions")
    north = cfg.get("northern_fallback", {})
    out = assign.copy()
    ii, jj = np.where(mask & (assign < 0))
    ai, aj = np.where(assign >= 0)
    for i, j in zip(ii, jj, strict=True):
        if north and lat[i] >= north["min_lat"] and lon[j] <= north["max_lon"]:
            out[i, j] = idx_of[north["id"]]
            continue
        k = np.argmin((ai - i) ** 2 + (aj - j) ** 2)
        out[i, j] = assign[ai[k], aj[k]]
    return out


def load_partition(rebuild: bool = False) -> dict:
    """{'lat','lon','assign'} for the IMD 0.25 deg grid (cached)."""
    if GRID_CACHE.exists() and not rebuild:
        z = np.load(GRID_CACHE)
        return {k: z[k] for k in z.files}
    from ml.data import imd

    years = [y for y in load_config("data")["imd"]["years"] if imd.year_path(y).exists()]
    if not years:
        raise SystemExit("IMD rainfall not downloaded: run `make fetch SOURCE=imd`")
    mask = imd.land_mask(years[0])
    assign = build_partition(imd.LATS, imd.LONS, mask)
    GRID_CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(GRID_CACHE, lat=imd.LATS, lon=imd.LONS, assign=assign)
    return {"lat": imd.LATS, "lon": imd.LONS, "assign": assign}


def imd_area_means(rain: np.ndarray, assign: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Area-weighted (cos lat) subdivision means of rain[day, lat, lon] -> [day, n_sub]."""
    n = len(subdivision_table())
    w = np.cos(np.deg2rad(lat))[:, None] * np.ones(assign.shape)
    out = np.full((rain.shape[0], n), np.nan, dtype="float32")
    for k in range(n):
        m = assign == k
        if not m.any():
            continue
        vals = rain[:, m]
        ww = w[m]
        ok = np.isfinite(vals)
        out[:, k] = np.where(
            ok.any(1),
            (np.nan_to_num(vals) * ww).sum(1) / np.maximum((ok * ww).sum(1), 1e-9),
            np.nan,
        )
    return out


def grid_weights(part: dict, lat_f: np.ndarray, lon_f: np.ndarray) -> np.ndarray:
    """Weights W[n_sub, n_lat_f * n_lon_f] so that W @ field.ravel() = subdivision area-mean
    of a coarser model field (each IMD cell mapped to its nearest model grid cell)."""
    from ml.regions import nearest_index

    n = len(subdivision_table())
    li = nearest_index(lat_f, part["lat"])
    lo = nearest_index(lon_f, part["lon"])
    W = np.zeros((n, len(lat_f) * len(lon_f)), dtype="float64")
    coslat = np.cos(np.deg2rad(part["lat"]))
    for i, j in zip(*np.where(part["assign"] >= 0), strict=True):
        W[part["assign"][i, j], li[i] * len(lon_f) + lo[j]] += coslat[i]
    s = W.sum(1, keepdims=True)
    return np.divide(W, s, out=np.zeros_like(W), where=s > 0)


def write_geojson(part: dict, simplify_deg: float = 0.03) -> dict:
    """Subdivision polygons (union of IMD cells) + India outline, for the dashboard map."""
    from shapely.geometry import box, mapping
    from shapely.ops import unary_union

    table = subdivision_table()
    h = 0.125
    feats = []
    for k, (sid, row) in enumerate(table.iterrows()):
        ii, jj = np.where(part["assign"] == k)
        if len(ii) == 0:
            continue
        geom = unary_union(
            [
                box(part["lon"][j] - h, part["lat"][i] - h, part["lon"][j] + h, part["lat"][i] + h)
                for i, j in zip(ii, jj, strict=True)
            ]
        )
        geom = geom.simplify(simplify_deg, preserve_topology=True)
        rp = geom.representative_point()
        feats.append(
            {
                "type": "Feature",
                "id": k,
                "properties": {
                    "id": sid,
                    "name": row["name"],
                    "zone": row["zone"],
                    "n_cells": int(len(ii)),
                    "label_lon": round(rp.x, 3),
                    "label_lat": round(rp.y, 3),
                },
                "geometry": _round(mapping(geom)),
            }
        )
    fc = {
        "type": "FeatureCollection",
        "features": feats,
        "attribution": "Subdivisions derived from the IMD 0.25 deg gridded-rainfall land mask; state lines: Natural Earth 50m admin-1.",
    }
    GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEOJSON_PATH.write_text(json.dumps(fc, separators=(",", ":")))
    return fc


def _round(geom: dict, nd: int = 3) -> dict:
    def r(c):
        return (
            [round(c[0], nd), round(c[1], nd)]
            if isinstance(c[0], float | int)
            else [r(x) for x in c]
        )

    return {"type": geom["type"], "coordinates": r(geom["coordinates"])}


def region_centroids() -> pd.DataFrame:
    """Subdivision label points from the GeoJSON (lat/lon for lists and tooltips)."""
    fc = json.loads(GEOJSON_PATH.read_text())
    rows = [
        {
            "id": f["properties"]["id"],
            "lat": f["properties"]["label_lat"],
            "lon": f["properties"]["label_lon"],
            "n_cells": f["properties"]["n_cells"],
        }
        for f in fc["features"]
    ]
    return pd.DataFrame(rows).set_index("id")

"""Polygonize high-scoring grid cells and compare hit rates with random cells."""
from __future__ import annotations

import json
import math
import random
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point, box, mapping
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "data/processed/grid_scores_v2.csv"
OCC = ROOT / "data/raw/known_occurrences.csv"
MINES = ROOT / "data/raw/moil_mines.geojson"
OUT = ROOT / "data/processed"
SEED = 20260929
METHOD = ("Scores sorted descending with stable centroid tie-breaks; select ceil(10%) and ceil(25%). "
          "8-neighbor connected components on regular centroid grid; discard components <2 cells; "
          "polygonize cell rectangles. Rank within threshold using 0.60 mean-score percentile, "
          "0.15 log-area percentile, 0.10 mine-proximity score, 0.15 occurrence-proximity score.")
TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True).transform


def finite_point(lon, lat):
    try:
        lon, lat = float(lon), float(lat)
        return math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90
    except (TypeError, ValueError):
        return False


def components(ids, rowcol):
    remaining = set(ids)
    cell_at = {rc: gid for gid, rc in rowcol.items()}
    result = []
    while remaining:
        start = remaining.pop()
        comp = {start}
        q = deque([start])
        while q:
            cur = q.popleft(); r, c = rowcol[cur]
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nxt = cell_at.get((r + dr, c + dc))
                    if nxt in remaining:
                        remaining.remove(nxt); comp.add(nxt); q.append(nxt)
        result.append(comp)
    return result


def point_set():
    occ_df = pd.read_csv(OCC)
    occ = [(str(r.get("name", "occurrence")), float(r["longitude"]), float(r["latitude"]))
           for r in occ_df.to_dict("records") if finite_point(r.get("longitude"), r.get("latitude"))]
    mines_doc = json.loads(MINES.read_text(encoding="utf-8"))
    mines = []
    for f in mines_doc.get("features", []):
        coords = f.get("geometry", {}).get("coordinates", [])
        if len(coords) >= 2 and finite_point(coords[0], coords[1]):
            mines.append((str(f.get("properties", {}).get("name", "mine")), float(coords[0]), float(coords[1])))
    return occ, mines


def main() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(GRID).dropna(subset=["lat", "lon", "prob_ensemble"]).copy().reset_index(drop=True)
    df["grid_id"] = [f"g_{float(r.lat):.5f}_{float(r.lon):.5f}" for r in df.itertuples()]
    dlat = float(np.median(np.diff(np.sort(df.lat.unique()))))
    dlon = float(np.median(np.diff(np.sort(df.lon.unique()))))
    lat0, lon0 = float(df.lat.min()), float(df.lon.min())
    df["row"] = np.rint((df.lat - lat0) / dlat).astype(int)
    df["col"] = np.rint((df.lon - lon0) / dlon).astype(int)
    rowcol = {r.grid_id: (int(r.row), int(r.col)) for r in df.itertuples()}
    cells = {r.grid_id: box(float(r.lon)-dlon/2, float(r.lat)-dlat/2,
                            float(r.lon)+dlon/2, float(r.lat)+dlat/2)
             for r in df.itertuples()}
    score_by_id = dict(zip(df.grid_id, df.prob_ensemble.astype(float)))
    score_order = sorted(df.grid_id, key=lambda gid: (-score_by_id[gid], gid))
    occ, mines = point_set()
    occurrence_records_total = len(pd.read_csv(OCC))

    features = []
    zone_masks = {}
    for level, frac in [("top_decile", 0.10), ("top_quartile", 0.25)]:
        n = math.ceil(len(df) * frac)
        selected = set(score_order[:n])
        comps = [c for c in components(selected, rowcol) if len(c) >= 2]
        raw = []
        for comp in comps:
            geom_ll = unary_union([cells[gid] for gid in comp])
            geom_m = transform(TO_UTM, geom_ll)
            centroid = geom_ll.centroid
            occ_dist = min((Point(*TO_UTM(lon, lat)).distance(Point(*TO_UTM(centroid.x, centroid.y)))
                            for _, lon, lat in occ), default=float("nan")) / 1000
            mine_dist = min((Point(*TO_UTM(lon, lat)).distance(Point(*TO_UTM(centroid.x, centroid.y)))
                             for _, lon, lat in mines), default=float("nan")) / 1000
            vals = np.array([score_by_id[g] for g in comp])
            raw.append({"comp": comp, "geometry": geom_ll, "area_km2": geom_m.area/1e6,
                        "mean": float(vals.mean()), "median": float(np.median(vals)),
                        "min": float(vals.min()), "max": float(vals.max()), "std": float(vals.std()),
                        "occ_km": occ_dist, "mine_km": mine_dist})
        if not raw:
            zone_masks[level] = set()
            continue
        # Percentile ranks; nearest distances get higher score when nearer.
        for key, values in [("score_pct", [x["mean"] for x in raw]),
                            ("area_pct", [math.log1p(x["area_km2"]) for x in raw])]:
            order = np.argsort(np.argsort(values, kind="stable"), kind="stable")
            for i, x in enumerate(raw):
                x[key] = float(order[i] / max(1, len(raw)-1))
        for prox, field in [("mine_prox", "mine_km"), ("occ_prox", "occ_km")]:
            vals = np.array([x[field] for x in raw], dtype=float)
            finite = np.isfinite(vals)
            lo, hi = (float(vals[finite].min()), float(vals[finite].max())) if finite.any() else (0, 0)
            for x in raw:
                x[prox] = float(1 - (x[field]-lo)/(hi-lo)) if math.isfinite(x[field]) and hi > lo else (1.0 if finite.any() else 0.0)
        for x in raw:
            x["rank_score"] = .60*x["score_pct"] + .15*x["area_pct"] + .10*x["mine_prox"] + .15*x["occ_prox"]
        raw.sort(key=lambda x: (-x["rank_score"], -x["mean"], -x["area_km2"]))
        zone_masks[level] = set()
        for rank, x in enumerate(raw, start=1):
            zone_masks[level].update(x["comp"])
            features.append({"type": "Feature", "id": f"{level}_{rank:03d}",
                "geometry": mapping(x["geometry"]),
                "properties": {"zone_level": level, "rank": rank, "rank_score": x["rank_score"],
                    "cell_count": len(x["comp"]), "grid_ids": sorted(x["comp"]),
                    "score_mean": x["mean"], "score_median": x["median"],
                    "score_min": x["min"], "score_max": x["max"], "score_std": x["std"],
                    "area_km2": x["area_km2"], "nearest_occurrence_km": x["occ_km"],
                    "nearest_mine_km": x["mine_km"], "provenance": "DERIVED",
                    "method": METHOD, "random_seed": SEED,
                    "source_ref": "grid_scores_v2.csv; known_occurrences.csv; moil_mines.geojson"}})

    # Top-ranked zones = top 25% of surviving quartile polygons by composite rank.
    q_features = [f for f in features if f["properties"]["zone_level"] == "top_quartile"]
    n_top_poly = math.ceil(len(q_features)*0.25) if q_features else 0
    top_ids = {gid for f in q_features[:n_top_poly] for gid in f["properties"]["grid_ids"]}
    rng = random.Random(SEED)
    all_ids = list(df.grid_id)
    n_sample_cells = len(top_ids)
    coord_by_id = {r.grid_id: (float(r.lon), float(r.lat)) for r in df.itertuples()}
    occ_cell = {name: min(all_ids, key=lambda gid: (coord_by_id[gid][1]-lat)**2 +
                          (coord_by_id[gid][0]-lon)**2)
                for name, lon, lat in occ}
    mine_cell = {name: min(all_ids, key=lambda gid: (coord_by_id[gid][1]-lat)**2 +
                           (coord_by_id[gid][0]-lon)**2)
                 for name, lon, lat in mines}
    occ_hit = sum(g in top_ids for g in occ_cell.values())
    mine_hit = sum(g in top_ids for g in mine_cell.values())
    trials = 1000
    occ_base, mine_base = [], []
    for _ in range(trials):
        chosen = set(rng.sample(all_ids, min(n_sample_cells, len(all_ids))))
        occ_base.append(sum(g in chosen for g in occ_cell.values()) / max(1, len(occ_cell)))
        mine_base.append(sum(g in chosen for g in mine_cell.values()) / max(1, len(mine_cell)))
    report = {"gap": 4, "status": "COMPLETE", "grid_cells": len(df),
        "threshold_cells": {"top_decile": math.ceil(len(df)*.10), "top_quartile": math.ceil(len(df)*.25)},
        "discarded_single_cell_components": True, "minimum_component_cells": 2,
        "polygon_count": len(features), "occurrence_records_in_file": occurrence_records_total,
        "valid_occurrence_points": len(occ),
        "occurrence_records_missing_coordinates": occurrence_records_total-len(occ),
        "mine_points": len(mines),
        "top_ranked_zone_polygon_count": n_top_poly, "top_ranked_zone_cell_count": n_sample_cells,
        "coverage": {"occurrences_inside_top_zones": occ_hit, "occurrence_denominator": len(occ),
                     "occurrence_fraction": occ_hit/max(1,len(occ)),
                     "mines_inside_top_zones": mine_hit, "mine_denominator": len(mines),
                     "mine_fraction": mine_hit/max(1,len(mines))},
        "random_baseline": {"trials": trials, "seed": SEED,
            "occurrence_mean_fraction": float(np.mean(occ_base)),
            "occurrence_95pct": [float(np.quantile(occ_base,.025)),float(np.quantile(occ_base,.975))],
            "mine_mean_fraction": float(np.mean(mine_base)),
            "mine_95pct": [float(np.quantile(mine_base,.025)),float(np.quantile(mine_base,.975))]},
        "method": METHOD + " Random baseline selects the same number of cells uniformly without replacement.",
        "validation_caveat": "Only occurrence records with coordinates were tested; five of eleven occurrence rows lack coordinates. This is not independent predictive validation because occurrence records may also inform existing training labels.",
        "provenance": "DERIVED", "source_ref": ["grid_scores_v2.csv", "known_occurrences.csv", "moil_mines.geojson"]}
    collection = {"type":"FeatureCollection", "name":"priority_zones",
                  "crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:EPSG::4326"}},
                  "metadata":{"provenance":"DERIVED","method":METHOD,"random_seed":SEED},
                  "features":features}
    (OUT/"priority_zones.geojson").write_text(json.dumps(collection), encoding="utf-8")
    (OUT/"priority_zone_validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))

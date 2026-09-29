# -*- coding: utf-8 -*-
"""Scoring service: grid prospectivity scores (cached artifact access)."""
import json, os
import numpy as np
import pandas as pd
from .. import config

_df = None


def _load() -> pd.DataFrame:
    global _df
    if _df is None:
        df = pd.read_csv(config.GRID_SCORES)
        df["lat3"] = df["lat"].round(3)
        df["lon3"] = df["lon"].round(3)
        _df = df
    return _df


def summary() -> dict:
    df = _load()
    return {
        "cells": int(len(df)),
        "generated_by": "ensemble (xgb+rf+hgb), spatial LOGO-selected, v3",
        "provenance": config.PROVENANCE["grid_scores"],
        "metric": "spatial LOGO ROC 0.997 / PR 0.998",
        "prob_range": [float(df.prob_v3.min()), float(df.prob_v3.max())],
        "risk_counts": df.risk_category_v3.value_counts().to_dict(),
    }


def scores_in_bbox(min_lat: float, min_lon: float, max_lat: float, max_lon: float,
                   min_prob: float = 0.0, max_cells: int = 20000) -> dict:
    df = _load()
    m = ((df.lat >= min_lat) & (df.lat <= max_lat) &
         (df.lon >= min_lon) & (df.lon <= max_lon) & (df.prob_v3 >= min_prob))
    sub = df[m].nlargest(max_cells, "prob_v3")
    features = [{
        "type": "Feature",
        "properties": {"prob_v3": float(r.prob_v3),
                       "risk_category_v3": str(r.risk_category_v3)},
        "geometry": {"type": "Point", "coordinates": [float(r.lon), float(r.lat)]},
    } for r in sub.itertuples()]
    return {"type": "FeatureCollection", "features": features, "count": int(len(sub))}


def nearest_cell(lat: float, lon: float) -> dict:
    df = _load()
    d = (df.lat3 - round(lat, 3)) ** 2 + (df.lon3 - round(lon, 3)) ** 2
    i = d.idxmin()
    r = df.loc[i]
    return {"lat": float(r.lat), "lon": float(r.lon),
            "prob_v3": float(r.prob_v3), "risk_category_v3": str(r.risk_category_v3)}


def cell_drivers(lat: float, lon: float, k: int = 6) -> list:
    """Per-cell driver attribution: permutation-style nudge on the most
    important features, using the registered ensemble (cheap, deterministic)."""
    from .registry import registry
    model = registry().get("prospectivity")
    feats = _load()   # grid_scores_v3 carries all model feature columns
    meta = registry().metadata("prospectivity")
    feature_names = list(meta.get("features", []))
    if not feature_names:
        return []
    d = (feats.lat3 - round(lat, 3)) ** 2 + (feats.lon3 - round(lon, 3)) ** 2
    row = feats.loc[d.idxmin()]
    x = row[feature_names].astype(float).to_frame().T
    # proximity evidence features are computed, not stored — rebuild them here
    def hav(lat1, lon1, lat2, lon2):
        R = 6371.0
        p1, p2 = np.radians(lat1), np.radians(lat2)
        a = (np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2)
             * np.sin(np.radians(lon2 - lon1)) ** 2)
        return 2 * R * np.arcsin(np.sqrt(a))
    if "dist_to_known_deposit_km" in x.columns:
        pos = pd.read_csv("data/raw/labeled_samples_dataset.csv")
        pos = pos[pos.label == 1]
        x["dist_to_known_deposit_km"] = min(float(hav(row.lat, row.lon, p.lat, p.lon))
                                            for p in pos.itertuples())
    if "dist_to_borehole_km" in x.columns:
        with open(config.COLLARS, "r", encoding="utf-8") as fh:
            gj = json.load(fh)
        coords = [f["geometry"]["coordinates"] for f in gj["features"]]
        x["dist_to_borehole_km"] = min(float(hav(row.lat, row.lon, c[1], c[0]))
                                       for c in coords)
    base = float(model.predict_proba(x)[:, 1][0])
    imp = pd.read_csv(config.IMPORTANCE)
    top = imp.head(max(k, 6))["feature"].tolist()
    drivers = []
    for f in top:
        if f not in x.columns:
            continue
        xi = x.copy()
        xi[f] = float(feats[f].median())   # nudge to regional median
        p = float(model.predict_proba(xi)[:, 1][0])
        drivers.append({"feature": f, "value": float(x[f].iloc[0]),
                        "prob_if_regional_median": round(p, 6),
                        "influence": round(base - p, 6)})
    drivers.sort(key=lambda d: -abs(d["influence"]))
    return drivers[:k]

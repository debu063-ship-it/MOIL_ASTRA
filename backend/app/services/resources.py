# -*- coding: utf-8 -*-
"""Volume/grade/borehole/layer services over parsed NGDR + GIS artifacts."""
import json, math, os
import pandas as pd
from .. import config


def _san(o):
    """Convert NaN floats to None so strict JSON encoding never chokes."""
    if isinstance(o, float) and math.isnan(o):
        return None
    if isinstance(o, dict):
        return {k: _san(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_san(v) for v in o]
    return o


def _resources() -> pd.DataFrame:
    return pd.read_csv(config.RESOURCES)


def volume_summary() -> dict:
    r = _resources()
    out = []
    for (block, nuid), g in r.groupby(["block", "nuid"]):
        xs = g[g.method == "cross-section"]
        pp = g[g.method != "cross-section"]
        out.append({
            "block": block, "nuid": nuid,
            "method": "GSI cross-section (as reported)",
            "boreholes": int(g.borehole.nunique()),
            "volume_m3": round(float(xs.volume_m3.sum()), 1),
            "tonnage_t": round(float(xs.tonnage_t.sum()), 1),
            "additional_probable_tonnage_t": round(float(pp.tonnage_t.sum()), 1) if len(pp) else None,
            "avg_mn_pct": round(float(xs.mn_pct.mean()), 2) if xs.mn_pct.notna().any() else None,
            "avg_sg": round(float(g.sg.dropna().iloc[0]), 3) if g.sg.notna().any() else None,
            "category": "Indicated+Inferred (GSI)" if "Ukwa" in block else "Inferred (UNFC 333)",
        })
    return {"blocks": out, "provenance": config.PROVENANCE["resources"],
            "note": "Cross-section totals; the separate probable-partial area (W. Ukwa, 0.21 Mt) "
                    "overlaps the same block and is reported apart to avoid double counting. "
                    "District-wide volume would require the other 49 NUID packages."}


def grade_summary() -> dict:
    a = pd.read_csv(config.ASSAYS)
    a = a[a.mn_pct.notna()]
    ore = a[a.mn_pct >= 15]
    by_block = {}
    for block, g in a.groupby("block"):
        go = g[g.mn_pct >= 15]
        by_block[block] = {
            "samples": int(len(g)), "ore_samples": int(len(go)),
            "mn_min": round(float(g.mn_pct.min()), 2), "mn_max": round(float(g.mn_pct.max()), 2),
            "ore_mean_mn_pct": round(float(go.mn_pct.mean()), 2) if len(go) else None,
            "mean_fe_pct": round(float(go.fe_pct.mean()), 2) if go.fe_pct.notna().any() else None,
            "mean_sio2_pct": round(float(go.sio2_pct.mean()), 2) if go.sio2_pct.notna().any() else None,
            "mean_p_pct": round(float(go.p_pct.mean()), 2) if go.p_pct.notna().any() else None,
            "mean_sg": round(float(go.sg.mean()), 3) if go.sg.notna().any() else None,
        }
    return {"blocks": by_block, "all_samples": int(len(a)),
            "ore_threshold_mn_pct": 15, "provenance": config.PROVENANCE["assays"]}


def boreholes(block: str | None = None) -> dict:
    with open(config.COLLARS, "r", encoding="utf-8") as fh:
        fc = json.load(fh)
    feats = fc["features"]
    if block:
        feats = [f for f in feats if block.lower() in f["properties"].get("block", "").lower()]
    feats = [_san(f) for f in feats]
    return {"type": "FeatureCollection", "features": feats, "count": len(feats)}


def assays(block: str | None = None, min_mn: float | None = None) -> list:
    a = pd.read_csv(config.ASSAYS)
    if block:
        a = a[a.block.str.lower() == block.lower()]
    if min_mn is not None:
        a = a[a.mn_pct >= min_mn]
    a = a.where(pd.notna(a), None)
    return a.to_dict(orient="records")


def structure() -> list:
    s = pd.read_csv(config.STRUCTURE)
    return s.where(pd.notna(s), None).to_dict(orient="records")


_LAYERS = None


def layer_catalog() -> list:
    global _LAYERS
    if _LAYERS is None:
        layers = [
            {"name": "prospectivity_scores", "title": "Mn prospectivity v3 (5,568 cells)",
             "kind": "points", "endpoint": "/api/v1/grid/scores", "provenance": "model output"},
            {"name": "boreholes", "title": "NGDR borehole collars (50, real)",
             "kind": "geojson", "endpoint": "/api/v1/boreholes",
             "file": config.COLLARS, "provenance": "real (NGDR registered download)"},
            {"name": "lithology_polygons", "title": "Mapped lithology polygons (135, real)",
             "kind": "geojson", "endpoint": "/api/v1/layers/lithology_polygons",
             "file": config.LITHO_POLY, "provenance": "real (GSI plates)"},
            {"name": "moil_mines", "title": "MOIL mine boundaries",
             "kind": "geojson", "endpoint": "/api/v1/layers/moil_mines",
             "file": config.MINES_GEOJSON, "provenance": "real (curated)"},
            {"name": "priority_zones", "title": "Priority exploration zones",
             "kind": "geojson", "endpoint": "/api/v1/layers/priority_zones",
             "file": config.PRIORITY_ZONES, "provenance": "model output"},
            {"name": "structure", "title": "Oriented structure measurements (77, real)",
             "kind": "points", "endpoint": "/api/v1/layers/structure",
             "file": config.STRUCTURE, "provenance": "real (GSI plates)"},
        ]
        _LAYERS = [l for l in layers if l.get("endpoint") or os.path.exists(l.get("file", ""))]
    return _LAYERS


def layer_geojson(name: str) -> dict | None:
    cat = {l["name"]: l for l in layer_catalog()}
    l = cat.get(name)
    if not l or not l.get("file") or not os.path.exists(l["file"]):
        return None
    with open(l["file"], "r", encoding="utf-8") as fh:
        return _san(json.load(fh))

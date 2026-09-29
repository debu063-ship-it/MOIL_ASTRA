# -*- coding: utf-8 -*-
import pandas as pd
from fastapi import APIRouter
from .. import config
from ..services import scoring

router = APIRouter(prefix="/xai", tags=["xai"])


@router.get("/importance")
def importance():
    df = pd.read_csv(config.IMPORTANCE)
    df = df.sort_values("model_importance", ascending=False)
    recs = df.where(pd.notna(df), None).to_dict(orient="records")
    import math
    for r in recs:
        for k, v in list(r.items()):
            if isinstance(v, float) and math.isnan(v):
                r[k] = None
    return {"importance": recs,
            "note": "model_importance = ensemble-member mean; perm_importance_no_proxy = "
                    "evidence-only ablation (no proximity features)"}


@router.get("/cell")
def cell_drivers(lat: float, lon: float, k: int = 6):
    s = scoring.nearest_cell(lat, lon)
    drivers = scoring.cell_drivers(lat, lon, k)
    return {"lat": s["lat"], "lon": s["lon"], "prob_v3": s["prob_v3"],
            "top_drivers": drivers,
            "method": "one-at-a-time nudge to regional median on top-importance features"}

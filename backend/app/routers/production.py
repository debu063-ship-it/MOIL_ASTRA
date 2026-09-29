# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, Query
from .. import config
from ..services import forecast

router = APIRouter(prefix="/production", tags=["production"])


@router.get("/mines")
def mines():
    return {"mines": forecast.mine_names()}


@router.get("/history")
def history(mine: str, months: int = Query(24, le=140)):
    try:
        return {"mine": mine, "provenance": config.PROVENANCE["production_forecast"],
                "history": forecast.history(mine, months)}
    except KeyError:
        raise HTTPException(404, f"unknown mine: {mine}")


@router.get("/forecast")
def next_month(mine: str, planned_tonnes: float | None = None):
    try:
        out = forecast.next_month_forecast(mine, planned_tonnes)
        out["provenance"] = config.PROVENANCE["production_forecast"]
        return out
    except KeyError:
        raise HTTPException(404, f"unknown mine: {mine}")
    except Exception as e:
        raise HTTPException(500, f"forecast failed: {e}")

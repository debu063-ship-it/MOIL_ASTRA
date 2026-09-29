# -*- coding: utf-8 -*-
from fastapi import APIRouter, Query
from ..services import dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard (frontend)"])


@router.get("/zones")
def zones():
    """UI 'Exploration Priority Zones' — top v3 cells as UI-contract features."""
    return dashboard.zones_geojson()


@router.get("/boreholes")
def boreholes():
    """UI boreholes with real core-log intervals from NGDR assays."""
    return dashboard.boreholes_geojson()


@router.get("/mines")
def mines():
    return {"mines": dashboard.mines_list()}


@router.get("/production")
def production(mine: str | None = Query(None)):
    return dashboard.production_for_mine(mine)


@router.get("/actions")
def actions(mine: str | None = Query(None)):
    return dashboard.corrective_actions(mine)


@router.get("/shap")
def shap(mine: str | None = Query(None)):
    return dashboard.shap_for_mine(mine)


@router.get("/ore_volume")
def ore_volume(zone_id: str = Query("UKWA")):
    return dashboard.ore_volume_for_zone(zone_id)


@router.get("/data_sources")
def data_sources():
    return {"sources": dashboard.data_sources_catalog()}


@router.get("/weather")
def weather():
    return dashboard.weather_summary()


@router.get("/grade_tonnage")
def grade_tonnage_ep():
    return dashboard.grade_tonnage()


@router.get("/climate/{layer_id}/{date_key}")
def climate_grid(layer_id: str, date_key: str):
    if layer_id != "rainfall":
        from fastapi import HTTPException
        raise HTTPException(404, f"climate layer not available: {layer_id} (only rainfall)")
    return dashboard.rainfall_grid(date_key)

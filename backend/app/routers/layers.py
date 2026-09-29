# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, Query
from ..services import resources

router = APIRouter(tags=["layers & resources"])


@router.get("/layers")
def layers():
    return resources.layer_catalog()


@router.get("/layers/{name}")
def layer(name: str):
    gj = resources.layer_geojson(name)
    if gj is None:
        raise HTTPException(404, f"layer not found or file missing: {name}")
    return gj


@router.get("/boreholes")
def boreholes(block: str | None = None):
    return resources.boreholes(block)


@router.get("/boreholes/assays")
def assays(block: str | None = None, min_mn: float | None = Query(None)):
    return {"assays": resources.assays(block, min_mn)}


@router.get("/boreholes/structure")
def structure():
    return {"structure": resources.structure()}


@router.get("/volume/summary")
def volume():
    return resources.volume_summary()


@router.get("/grade/summary")
def grade():
    return resources.grade_summary()

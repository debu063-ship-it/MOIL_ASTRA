# -*- coding: utf-8 -*-
from fastapi import APIRouter, Query
from ..services import scoring

router = APIRouter(prefix="/grid", tags=["prospectivity"])


@router.get("/summary")
def grid_summary():
    return scoring.summary()


@router.get("/scores")
def grid_scores(min_lat: float = Query(21.1), min_lon: float = Query(79.2),
                max_lat: float = Query(22.05), max_lon: float = Query(80.49),
                min_prob: float = Query(0.0), max_cells: int = Query(20000, le=60000)):
    return scoring.scores_in_bbox(min_lat, min_lon, max_lat, max_lon, min_prob, max_cells)


@router.get("/cell")
def cell(lat: float, lon: float):
    return scoring.nearest_cell(lat, lon)

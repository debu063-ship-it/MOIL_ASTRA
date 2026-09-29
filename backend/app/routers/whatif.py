# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..services import forecast

router = APIRouter(prefix="/whatif", tags=["what-if"])


class SimRequest(BaseModel):
    mine: str
    equipment_availability: float
    monthly_rain_mm: float
    planned_tonnes: Optional[float] = None
    blast_delay_days: int = 0


@router.post("/simulate")
def simulate(req: SimRequest):
    if not 0 <= req.equipment_availability <= 1:
        raise HTTPException(422, "equipment_availability must be in [0, 1]")
    if req.monthly_rain_mm < 0 or req.monthly_rain_mm > 1500:
        raise HTTPException(422, "monthly_rain_mm must be in [0, 1500]")
    try:
        return forecast.whatif(req.mine, req.equipment_availability,
                               req.monthly_rain_mm, req.planned_tonnes,
                               req.blast_delay_days)
    except KeyError:
        raise HTTPException(404, f"unknown mine: {req.mine}")
    except Exception as e:
        raise HTTPException(500, f"simulation failed: {e}")

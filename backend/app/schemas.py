# -*- coding: utf-8 -*-
"""Pydantic response models (v1 API contract)."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class ProvenanceBlock(BaseModel):
    source: str
    kind: str  # real | synthetic-calibrated | measured


class CellScore(BaseModel):
    lat: float
    lon: float
    prob_v3: float
    risk_category_v3: str


class ScoreSummary(BaseModel):
    cells: int
    generated_by: str
    provenance: str
    metric: str


class ForecastPoint(BaseModel):
    mine: str
    month: str
    planned_tonnes: float
    predicted_shortfall_ratio: float
    predicted_shortfall_tonnes: float


class WhatIfRequest(BaseModel):
    mine: str
    equipment_availability: float
    monthly_rain_mm: float
    planned_tonnes: Optional[float] = None


class WhatIfResponse(BaseModel):
    mine: str
    baseline_ratio: float
    scenario_ratio: float
    delta_ratio: float
    planned_tonnes: float
    scenario_shortfall_tonnes: float
    baseline_shortfall_tonnes: float
    provenance: str


class XaiCell(BaseModel):
    lat: float
    lon: float
    prob_v3: float
    top_drivers: List[Dict[str, Any]]


class ActionItem(BaseModel):
    rule_id: str
    priority: int
    trigger: str
    action: str
    expected_effect: str


class AlertItem(BaseModel):
    mine: str
    month: str
    kind: str
    severity: str
    metric: float
    threshold: float
    message: str


class VolumeRow(BaseModel):
    block: str
    nuid: str
    method: str
    boreholes: int
    volume_m3: float
    tonnage_t: float
    avg_mn_pct: Optional[float]
    avg_sg: Optional[float]
    category: str

# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException
from ..db import Alert, ActionRecommendation, session
from ..services import rules_engine

router = APIRouter(tags=["alerts & actions"])


@router.get("/alerts")
def current_alerts():
    return {"alerts": rules_engine.evaluate_alerts(persist=True),
            "thresholds": {"shortfall_ratio": 0.15, "equipment_availability": 0.85,
                           "heavy_rain_days": 8}}


@router.get("/alerts/history")
def alert_history(limit: int = 100):
    with session() as s:
        rows = s.query(Alert).order_by(Alert.id.desc()).limit(limit).all()
        return {"alerts": [{"mine": r.mine, "month": r.month, "kind": r.kind,
                            "severity": r.severity, "metric": r.metric,
                            "message": r.message, "created_at": r.created_at}
                           for r in rows]}


@router.post("/actions/recommend")
def recommend(mine: str):
    try:
        return rules_engine.recommend(mine)
    except KeyError:
        raise HTTPException(404, f"unknown mine: {mine}")


@router.get("/actions/rules")
def show_rules():
    return {"rules": rules_engine.rules()}

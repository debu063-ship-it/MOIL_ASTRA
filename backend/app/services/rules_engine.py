# -*- coding: utf-8 -*-
"""Corrective-action rules engine (deterministic, auditable) + alert evaluation."""
import os
from datetime import datetime, timezone
import pandas as pd
import yaml
from .. import config
from ..db import Alert, ActionRecommendation, session

_rules = None


def rules() -> list:
    global _rules
    if _rules is None:
        with open(config.RULES_FILE, "r", encoding="utf-8") as fh:
            _rules = yaml.safe_load(fh)["rules"]
    return _rules


def _ctx_for(mine: str) -> dict:
    df = pd.read_csv(config.OPS_SYNTH, parse_dates=["month"])
    m = df[df.mine == mine].sort_values("month")
    if m.empty:
        raise KeyError(mine)
    last = m.iloc[-1]
    rain_roll = m["monthly_rain_mm"].tail(3).mean()
    return {
        "mine": mine,
        "month": last["month"].strftime("%Y-%m"),
        "shortfall_ratio": float(last["shortfall_tonnes"] / last["planned_tonnes"]),
        "equipment_availability": float(last["equipment_availability"]),
        "downtime_hours": float(last["downtime_hours"]),
        "monthly_rain_mm": float(last["monthly_rain_mm"]),
        "rain_mm_roll3": float(rain_roll),
        "heavy_rain_days": int(last["heavy_rain_days"]),
        "blast_delay_flag": int(last["blast_delay_flag"]),
    }


def recommend(mine: str, persist: bool = True) -> dict:
    ctx = _ctx_for(mine)
    fired = []
    for rule in rules():
        try:
            hit = bool(eval(rule["when"], {"__builtins__": {}}, dict(ctx)))
        except Exception:
            hit = False
        if hit:
            fired.append({
                "rule_id": rule["id"], "priority": int(rule["priority"]),
                "trigger": rule["when"], "action": rule["action"],
                "expected_effect": rule["effect"],
            })
    fired.sort(key=lambda a: a["priority"])
    if persist and fired:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with session() as s:
            for a in fired:
                s.add(ActionRecommendation(created_at=now, mine=mine, month=ctx["month"],
                                           rule_id=a["rule_id"], priority=a["priority"],
                                           trigger=a["trigger"], action=a["action"],
                                           expected_effect=a["expected_effect"]))
            s.commit()
    return {"mine": mine, "context": ctx, "actions": fired}


def evaluate_alerts(persist: bool = True) -> list:
    """Threshold alerts on the latest month of every mine."""
    df = pd.read_csv(config.OPS_SYNTH, parse_dates=["month"])
    latest = df.sort_values("month").groupby("mine").tail(1)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    alerts = []
    for r in latest.itertuples():
        ratio = r.shortfall_tonnes / r.planned_tonnes
        if ratio > config.ALERT_RATIO * 2:
            alerts.append({"mine": r.mine, "month": r.month.strftime("%Y-%m"), "kind": "shortfall",
                           "severity": "critical", "metric": round(ratio, 4),
                           "threshold": config.ALERT_RATIO,
                           "message": f"Shortfall {ratio:.0%} of plan (> {config.ALERT_RATIO:.0%})"})
        elif ratio > config.ALERT_RATIO:
            alerts.append({"mine": r.mine, "month": r.month.strftime("%Y-%m"), "kind": "shortfall",
                           "severity": "warning", "metric": round(ratio, 4),
                           "threshold": config.ALERT_RATIO,
                           "message": f"Shortfall {ratio:.0%} of plan (> {config.ALERT_RATIO:.0%})"})
        if r.equipment_availability < config.ALERT_EQ_AVAIL:
            alerts.append({"mine": r.mine, "month": r.month.strftime("%Y-%m"), "kind": "equipment",
                           "severity": "warning", "metric": float(r.equipment_availability),
                           "threshold": config.ALERT_EQ_AVAIL,
                           "message": f"Equipment availability {r.equipment_availability:.0%} below floor "
                                      f"{config.ALERT_EQ_AVAIL:.0%}"})
        if r.heavy_rain_days >= config.ALERT_HEAVY_RAIN:
            alerts.append({"mine": r.mine, "month": r.month.strftime("%Y-%m"), "kind": "heavy_rain",
                           "severity": "info", "metric": float(r.heavy_rain_days),
                           "threshold": config.ALERT_HEAVY_RAIN,
                           "message": f"{r.heavy_rain_days} heavy-rain days this month"})
    if persist and alerts:
        with session() as s:
            for a in alerts:
                s.add(Alert(created_at=now, **a))
            s.commit()
    return alerts


def rules_yaml() -> str:
    with open(config.RULES_FILE, "r", encoding="utf-8") as fh:
        return fh.read()

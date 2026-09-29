# -*- coding: utf-8 -*-
"""Forecast + what-if services: wrappers around shortfall forecaster and response model."""
import numpy as np
import pandas as pd
from .. import config
from .registry import registry

_ops = None


def ops() -> pd.DataFrame:
    global _ops
    if _ops is None:
        df = pd.read_csv(config.OPS_SYNTH, parse_dates=["month"])
        df["month_str"] = df["month"].dt.strftime("%Y-%m")
        df["shortfall_ratio"] = df["shortfall_tonnes"] / df["planned_tonnes"]
        _ops = df.sort_values(["mine", "month"]).reset_index(drop=True)
    return _ops


def mine_names():
    return sorted(ops()["mine"].unique().tolist())


def next_month_forecast(mine: str, planned_tonnes: float | None = None) -> dict:
    """One-step-ahead forecast for a mine using its latest observed history."""
    df = ops()
    m = df[df.mine == mine].sort_values("month")
    if m.empty:
        raise KeyError(mine)
    last = m.iloc[-1]
    nxt = (last["month"] + pd.offsets.MonthBegin(1))
    model = registry().get("shortfall_forecaster")

    # rebuild the exact feature row the training script used
    mine_d = pd.get_dummies(df["mine"], prefix="mine", dtype=float)
    mtype_d = pd.get_dummies(df["mine_type"], prefix="type", dtype=float)
    Xall = pd.concat([df, mine_d, mtype_d], axis=1)
    g = df.groupby("mine")
    Xall["sr_lag1"] = g["shortfall_ratio"].shift(1)
    Xall["sr_lag2"] = g["shortfall_ratio"].shift(2)
    Xall["sr_lag3"] = g["shortfall_ratio"].shift(3)
    Xall["sr_lag12"] = g["shortfall_ratio"].shift(12)
    Xall["sr_roll3"] = g["shortfall_ratio"].transform(lambda s: s.shift(1).rolling(3).mean())
    Xall["sr_roll12"] = g["shortfall_ratio"].transform(lambda s: s.shift(1).rolling(12).mean())
    Xall["eq_lag1"] = g["equipment_availability"].shift(1)
    Xall["eq_lag2"] = g["equipment_availability"].shift(2)
    Xall["eq_lag3"] = g["equipment_availability"].shift(3)
    Xall["eq_lag12"] = g["equipment_availability"].shift(12)
    Xall["rain_mm_roll3"] = g["monthly_rain_mm"].transform(lambda s: s.rolling(3).mean())
    Xall["heavy_rain_roll3"] = g["heavy_rain_days"].transform(lambda s: s.rolling(3).mean())
    Xall["planned_lag1"] = g["planned_tonnes"].shift(1)
    Xall["month_num"] = Xall["month"].dt.month

    meta = registry().metadata("shortfall")
    feats = meta["featurizerA_features"]
    # last observed row for this mine = the base for next-month prediction
    row = Xall[Xall.mine == mine].iloc[-1][feats].astype(float).to_frame().T
    if planned_tonnes:
        row["planned_lag1"] = float(planned_tonnes)
    ratio = float(model.predict(row)[0])
    plan = float(planned_tonnes) if planned_tonnes else float(last["planned_tonnes"])
    return {
        "mine": mine,
        "month": (last["month"] + pd.offsets.MonthBegin(1)).strftime("%Y-%m"),
        "planned_tonnes": plan,
        "predicted_shortfall_ratio": round(ratio, 6),
        "predicted_shortfall_tonnes": round(ratio * plan, 1),
        "based_on_history_through": last["month_str"],
    }


def history(mine: str, months: int = 24) -> list:
    m = ops()[ops().mine == mine].sort_values("month").tail(months)
    return [{
        "month": r.month_str, "planned_tonnes": float(r.planned_tonnes),
        "actual_tonnes": float(r.actual_tonnes),
        "shortfall_ratio": round(float(r.shortfall_ratio), 4),
        "rain_mm": float(r.monthly_rain_mm),
        "equipment_availability": float(r.equipment_availability),
    } for r in m.itertuples()]


def holdout_predictions() -> list:
    df = ops()
    pred = pd.read_csv(config.SHORTFALL_PRED, parse_dates=["month"])
    pred["month"] = pred["month"].dt.strftime("%Y-%m")
    out = []
    for _, r in pred.iterrows():
        out.append({
            "mine": r["mine"], "month": r["month"],
            "planned_tonnes": float(r["planned_tonnes"]),
            "actual_shortfall_tonnes": float(r["shortfall_tonnes"]),
            "actual_ratio": round(float(r["shortfall_tonnes"] / r["planned_tonnes"]), 4),
            "pred_shortfall_tonnes": float(r["pred_shortfall_tonnes"]),
            "pred_shortfall_ratio": float(r["pred_shortfall_ratio"]),
            "model": r["model"],
        })
    return out


def whatif(mine: str, equipment_availability: float, monthly_rain_mm: float,
           planned_tonnes: float | None = None, blast_delay_days: int = 0) -> dict:
    """Scenario: set drivers on the mine's latest state, predict response."""
    df = ops()
    model = registry().get("whatif_response")
    meta = registry().metadata("shortfall")
    featsB = meta["featurizerB_features"]

    m = df[df.mine == mine].sort_values("month")
    if m.empty:
        raise KeyError(mine)
    last = m.iloc[-1]

    mine_d = pd.get_dummies(df["mine"], prefix="mine", dtype=float)
    mtype_d = pd.get_dummies(df["mine_type"], prefix="type", dtype=float)
    Xall = pd.concat([df, mine_d, mtype_d], axis=1)
    g = df.groupby("mine")
    Xall["rain_mm_roll3"] = g["monthly_rain_mm"].transform(lambda s: s.rolling(3).mean())
    Xall["heavy_rain_roll3"] = g["heavy_rain_days"].transform(lambda s: s.rolling(3).mean())
    Xall["planned_lag1"] = g["planned_tonnes"].shift(1)
    Xall["month_num"] = Xall["month"].dt.month

    base_row = Xall[Xall.mine == mine].iloc[-1]

    def build_row(eq, rain, blast_days=0):
        r = base_row.copy()
        r["equipment_availability"] = eq
        r["monthly_rain_mm"] = rain
        r["heavy_rain_days"] = 0 if rain < 50 else (2 if rain < 150 else (6 if rain < 300 else 12))
        r["rain_mm_roll3"] = rain * 0.6
        r["heavy_rain_roll3"] = r["heavy_rain_days"] * 0.6
        r["blast_delay_flag"] = 1 if blast_days > 0 else 0
        r["downtime_hours"] = float(r["downtime_hours"]) + max(0, blast_days) * 24
        if planned_tonnes:
            r["planned_lag1"] = float(planned_tonnes)
        return r[featsB].astype(float).to_frame().T

    base_ratio = float(model.predict(build_row(float(last["equipment_availability"]),
                                               float(last["monthly_rain_mm"])))[0])
    scen_ratio = float(model.predict(
        build_row(equipment_availability, monthly_rain_mm, int(blast_delay_days)))[0])
    plan = float(planned_tonnes) if planned_tonnes else float(last["planned_tonnes"])
    return {
        "mine": mine,
        "baseline_ratio": round(base_ratio, 6),
        "scenario_ratio": round(scen_ratio, 6),
        "delta_ratio": round(scen_ratio - base_ratio, 6),
        "planned_tonnes": plan,
        "baseline_shortfall_tonnes": round(base_ratio * plan, 1),
        "scenario_shortfall_tonnes": round(scen_ratio * plan, 1),
        "scenario_inputs": {"equipment_availability": equipment_availability,
                            "monthly_rain_mm": monthly_rain_mm,
                            "blast_delay_days": int(blast_delay_days)},
        "provenance": config.PROVENANCE["production_forecast"],
    }

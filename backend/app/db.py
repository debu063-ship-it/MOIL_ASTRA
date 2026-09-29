# -*- coding: utf-8 -*-
"""SQLite schema (SQLAlchemy) + bootstrap seed from serving artifacts."""
import json, os
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy import (Column, Float, Integer, String, Text, create_engine)
from sqlalchemy.orm import declarative_base, sessionmaker
from . import config

Base = declarative_base()


class Mine(Base):
    __tablename__ = "mines"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    mine_type = Column(String)
    lat = Column(Float)
    lon = Column(Float)


class OpsMonthly(Base):
    __tablename__ = "ops_monthly"
    id = Column(Integer, primary_key=True)
    mine = Column(String, index=True)
    month = Column(String, index=True)          # YYYY-MM
    planned_tonnes = Column(Float)
    actual_tonnes = Column(Float)
    shortfall_tonnes = Column(Float)
    shortfall_ratio = Column(Float)
    equipment_availability = Column(Float)
    downtime_hours = Column(Float)
    monthly_rain_mm = Column(Float)
    heavy_rain_days = Column(Integer)
    provenance = Column(String, default="synthetic-calibrated")


class ShortfallPrediction(Base):
    __tablename__ = "shortfall_predictions"
    id = Column(Integer, primary_key=True)
    mine = Column(String, index=True)
    month = Column(String, index=True)
    planned_tonnes = Column(Float)
    actual_tonnes = Column(Float)
    actual_shortfall_tonnes = Column(Float)
    pred_shortfall_ratio = Column(Float)
    pred_shortfall_tonnes = Column(Float)
    model = Column(String)
    provenance = Column(String)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    created_at = Column(String)
    mine = Column(String, index=True)
    month = Column(String)
    kind = Column(String)                 # shortfall | heavy_rain | equipment
    severity = Column(String)             # info | warning | critical
    metric = Column(Float)
    threshold = Column(Float)
    message = Column(Text)
    status = Column(String, default="open")


class ActionRecommendation(Base):
    __tablename__ = "action_recommendations"
    id = Column(Integer, primary_key=True)
    created_at = Column(String)
    mine = Column(String, index=True)
    month = Column(String)
    rule_id = Column(String)
    priority = Column(Integer)
    trigger = Column(Text)
    action = Column(Text)
    expected_effect = Column(Text)


class ReportJob(Base):
    __tablename__ = "report_jobs"
    id = Column(Integer, primary_key=True)
    created_at = Column(String)
    scope = Column(String)
    status = Column(String, default="queued")   # queued|running|done|error
    file_path = Column(String)
    error = Column(Text)


_engine = None
_Session = None


def engine():
    global _engine, _Session
    if _engine is None:
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        _engine = create_engine(f"sqlite:///{config.DB_PATH}", future=True)
        Base.metadata.create_all(_engine)
        _Session = sessionmaker(_engine, expire_on_commit=False, future=True)
    return _engine


def session():
    engine()
    return _Session()


def seed_if_empty():
    """Idempotent bootstrap: mines + ops + predictions from serving artifacts."""
    with session() as s:
        if s.query(Mine).count() > 0:
            return False
        ops = pd.read_csv(config.OPS_SYNTH, parse_dates=["month"])
        ops["month"] = ops["month"].dt.strftime("%Y-%m")
        ops["shortfall_ratio"] = (ops["shortfall_tonnes"] / ops["planned_tonnes"]).round(6)
        mines = (ops.groupby("mine")
                    .agg(mine_type=("mine_type", "first"))
                    .reset_index())
        coords = {
            "Balaghat": (21.8333, 80.2333), "Ukwa": (21.9720, 80.4550),
            "Tirodi": (21.684, 79.727), "Dongri Buzurg": (21.705, 80.125),
            "Mansar": (21.85, 79.9), "Gumgaon": (21.35, 79.85),
            "Kandri": (21.3, 79.8), "Chikla": (21.55, 79.65), "Sitapatore": (21.75, 80.3),
        }
        for _, r in mines.iterrows():
            lat, lon = coords.get(r["mine"], (21.8, 80.0))
            s.add(Mine(name=r["mine"], mine_type=r["mine_type"], lat=lat, lon=lon))
        for _, r in ops.iterrows():
            s.add(OpsMonthly(
                mine=r["mine"], month=r["month"],
                planned_tonnes=float(r["planned_tonnes"]),
                actual_tonnes=float(r["actual_tonnes"]),
                shortfall_tonnes=float(r["shortfall_tonnes"]),
                shortfall_ratio=float(r["shortfall_ratio"]),
                equipment_availability=float(r["equipment_availability"]),
                downtime_hours=float(r["downtime_hours"]),
                monthly_rain_mm=float(r["monthly_rain_mm"]),
                heavy_rain_days=int(r["heavy_rain_days"]),
            ))
        try:
            pred = pd.read_csv(config.SHORTFALL_PRED, parse_dates=["month"])
            pred["month"] = pred["month"].dt.strftime("%Y-%m")
            for _, r in pred.iterrows():
                s.add(ShortfallPrediction(
                    mine=r["mine"], month=r["month"],
                    planned_tonnes=float(r["planned_tonnes"]),
                    actual_tonnes=float(r["actual_tonnes"]),
                    actual_shortfall_tonnes=float(r["shortfall_tonnes"]),
                    pred_shortfall_ratio=float(r["pred_shortfall_ratio"]),
                    pred_shortfall_tonnes=float(r["pred_shortfall_tonnes"]),
                    model=str(r["model"]),
                    provenance=config.PROVENANCE["shortfall"],
                ))
        except Exception as e:  # predictions artifact optional for boot
            print("seed: predictions skipped:", e)
        s.commit()
        return True

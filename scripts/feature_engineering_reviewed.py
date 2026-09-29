#!/usr/bin/env python3
"""
MOIL SIH26009 — Reviewed Feature Engineering Pipeline
=====================================================
Recomputes all derived ratios, interactions, lags, and rolling features
from reviewed base data (data/capped_reviewed/).

Key Principles:
  1. Full documentation: mathematical formulas, source columns, units, random seeds.
  2. Cyclical transform: aspect -> aspect_sin, aspect_cos (no linear fences).
  3. No data leakage: deposit_probability is NOT used as an input feature for prospectivity.
  4. Temporal integrity: Rolling windows and lags computed strictly per-mine in chronological order.
  5. Accounting consistency: shortfall_pct and production_efficiency preserve physical identities.
"""

import os
import sys
import io
import warnings
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

BASE = Path(r"c:\Users\Debu018\Downloads\MOIL SIH26009")
REV_DATA = BASE / "data" / "capped_reviewed"
PROC_REV = REV_DATA / "processed"
PROC_REV.mkdir(parents=True, exist_ok=True)
OUT_REV = BASE / "outputs" / "data_capping_review"
OUT_REV.mkdir(parents=True, exist_ok=True)
EXT_GEO = BASE / "data" / "external" / "geology"

feature_catalog = []


def register_feature(name, domain, formula, sources, units, notes=""):
    feature_catalog.append({
        "feature_name": name,
        "domain": domain,
        "mathematical_formula": formula,
        "source_columns": sources,
        "units": units,
        "notes": notes
    })


print("Starting Reviewed Feature Engineering...")

# =========================================================================
# 1. INTEGRATED GRID FEATURES
# =========================================================================
print("\n1. Engineering Integrated Grid Features...")

df_s2 = pd.read_csv(REV_DATA / "external" / "satellite" / "s2_dem_grid_samples.csv")
df_grid = pd.read_csv(REV_DATA / "raw" / "region_grid_predictions.csv")
df_geo = pd.read_csv(EXT_GEO / "gsi_geology_grid.csv")

# Filter to base measurement columns to prevent re-using derived or flagged columns
s2_base_cols = ["lat", "lon", "B2", "B3", "B4", "B8", "B11", "B12", "elevation", "slope", "aspect"]
df_s2_clean = df_s2[[c for c in s2_base_cols if c in df_s2.columns]].copy()

# Round lat/lon to 4 decimal places to ensure exact inner merge
df_s2_clean["lat_r"] = df_s2_clean["lat"].round(4)
df_s2_clean["lon_r"] = df_s2_clean["lon"].round(4)
df_geo["lat_r"] = df_geo["lat"].round(4)
df_geo["lon_r"] = df_geo["lon"].round(4)

# Derived spectral ratios from base bands
df_s2_clean["iron_oxide_index"] = df_s2_clean["B4"] / np.maximum(df_s2_clean["B2"], 1e-6)
register_feature("iron_oxide_index", "Spectral", "B4 / B2", "B4, B2", "ratio", "Sensitivity to Fe-bearing alteration minerals")

df_s2_clean["swir_nir_ratio"] = df_s2_clean["B11"] / np.maximum(df_s2_clean["B8"], 1e-6)
register_feature("swir_nir_ratio", "Spectral", "B11 / B8", "B11, B8", "ratio", "Shortwave IR to Near IR ratio")

df_s2_clean["clay_alteration_idx"] = df_s2_clean["B11"] / np.maximum(df_s2_clean["B12"], 1e-6)
register_feature("clay_alteration_idx", "Spectral", "B11 / B12", "B11, B12", "ratio", "Clay/phyllosilicate hydroxyl absorption proxy")

df_s2_clean["ferrous_iron_idx"] = df_s2_clean["B12"] / np.maximum(df_s2_clean["B8"], 1e-6)
register_feature("ferrous_iron_idx", "Spectral", "B12 / B8", "B12, B8", "ratio", "Ferrous iron bearing silicate index")

df_s2_clean["ndvi"] = (df_s2_clean["B8"] - df_s2_clean["B4"]) / np.maximum(df_s2_clean["B8"] + df_s2_clean["B4"], 1e-6)
register_feature("ndvi", "Vegetation", "(B8 - B4) / (B8 + B4)", "B8, B4", "[-1, 1]", "Normalized Difference Vegetation Index")

# Additional spectral statistics
bands = ["B2", "B3", "B4", "B8", "B11", "B12"]
df_s2_clean["spectral_mean"] = df_s2_clean[bands].mean(axis=1)
register_feature("spectral_mean", "Spectral", "mean(B2, B3, B4, B8, B11, B12)", "B2..B12", "reflectance", "Broadband albedo proxy")

df_s2_clean["spectral_range"] = df_s2_clean[bands].max(axis=1) - df_s2_clean[bands].min(axis=1)
register_feature("spectral_range", "Spectral", "max(B) - min(B)", "B2..B12", "reflectance", "Spectral dynamic contrast")

# Cyclical Aspect Transformations
rad = np.radians(df_s2_clean["aspect"])
df_s2_clean["aspect_sin"] = np.round(np.sin(rad), 6)
register_feature("aspect_sin", "Topography", "sin(aspect * pi / 180)", "aspect", "[-1, 1]", "East-West illumination component")

df_s2_clean["aspect_cos"] = np.round(np.cos(rad), 6)
register_feature("aspect_cos", "Topography", "cos(aspect * pi / 180)", "aspect", "[-1, 1]", "North-South illumination component")

# Topographic ruggedness interaction
df_s2_clean["topo_ruggedness"] = (df_s2_clean["slope"] * df_s2_clean["elevation"]) / 1000.0
register_feature("topo_ruggedness", "Topography", "slope * elevation / 1000", "slope, elevation", "km-deg", "Terrain roughness index")

# Merge Geology on rounded coordinates
df_integrated = pd.merge(df_s2_clean, df_geo[["lat_r", "lon_r", "gsi_group", "gsi_unit", "gsi_age", "dist_to_sausar_km"]],
                         on=["lat_r", "lon_r"], how="inner").drop(columns=["lat_r", "lon_r"])

# Proximity classes
df_integrated["sausar_proximity_class"] = pd.cut(
    df_integrated["dist_to_sausar_km"],
    bins=[0, 1, 5, 10, 25, 100],
    labels=["<1km", "1-5km", "5-10km", "10-25km", ">25km"],
    include_lowest=True
)
register_feature("sausar_proximity_class", "Geology", "binned(dist_to_sausar_km)", "dist_to_sausar_km", "category", "Categorical Sausar proximity bands")

df_integrated["in_sausar"] = (df_integrated["gsi_group"] == "SAUSAR GROUP").astype(int)
register_feature("in_sausar", "Geology", "1 if gsi_group == 'SAUSAR GROUP' else 0", "gsi_group", "binary", "Host rock indicator")

# Merge distance to Gondite from grid
if "dist_to_gondite_km" in df_grid.columns:
    df_integrated = pd.merge(df_integrated, df_grid[["lat", "lon", "dist_to_gondite_km"]], on=["lat", "lon"], how="left")
    register_feature("dist_to_gondite_km", "Geology", "Spatial distance to Gondite formation boundary", "vector geology", "km", "Primary ore formation proximity")

# Add deposit_probability ONLY as a diagnostic benchmark column (explicitly flagged)
if "deposit_probability" in df_grid.columns:
    df_integrated = pd.merge(df_integrated, df_grid[["lat", "lon", "deposit_probability", "risk_category"]], on=["lat", "lon"], how="left")
    df_integrated["is_model_output_diagnostic"] = True
    register_feature("deposit_probability", "Model Diagnostic", "Existing model output probability", "prior model", "[0, 1]", "DIAGNOSTIC ONLY; NOT A PREDICTOR")

out_grid_path = PROC_REV / "engineered_features_integrated_grid.csv"
df_integrated.to_csv(out_grid_path, index=False)
print(f"  [OK] Saved integrated grid features: {df_integrated.shape} -> {out_grid_path}")


# =========================================================================
# 2. MONTHLY OPERATIONS ENGINEERED FEATURES
# =========================================================================
print("\n2. Engineering Monthly Operations Features...")

df_ops = pd.read_csv(REV_DATA / "synthetic" / "monthly_ops_synthetic_2015_2026.csv")
df_ops["month"] = pd.to_datetime(df_ops["month"])
df_ops = df_ops.sort_values(["mine", "month"]).reset_index(drop=True)

# Accounting identities and ratios
df_ops["shortfall_pct"] = (df_ops["shortfall_tonnes"] / np.maximum(df_ops["planned_tonnes"], 1.0)) * 100.0
register_feature("shortfall_pct", "Operations", "(shortfall_tonnes / planned_tonnes) * 100", "shortfall_tonnes, planned_tonnes", "%", "Normalized production shortfall rate")

df_ops["production_efficiency"] = (df_ops["actual_tonnes"] / np.maximum(df_ops["planned_tonnes"], 1.0)) * 100.0
register_feature("production_efficiency", "Operations", "(actual_tonnes / planned_tonnes) * 100", "actual_tonnes, planned_tonnes", "%", "Plan realization percentage")

# Operational and environmental intensity features
df_ops["rain_intensity"] = np.where(df_ops["heavy_rain_days"] > 0, df_ops["monthly_rain_mm"] / df_ops["heavy_rain_days"], 0.0)
register_feature("rain_intensity", "Weather", "monthly_rain_mm / heavy_rain_days", "monthly_rain_mm, heavy_rain_days", "mm/day", "Rainfall volume per heavy rain day")

df_ops["downtime_rate"] = df_ops["downtime_hours"] / (30.0 * 24.0)
register_feature("downtime_rate", "Operations", "downtime_hours / 720", "downtime_hours", "fraction", "Fraction of monthly hours lost to downtime")

df_ops["blast_delay_flag"] = (df_ops["downtime_hours"] > 80.0).astype(int)
register_feature("blast_delay_flag", "Operations", "1 if downtime_hours > 80 else 0", "downtime_hours", "binary", "Flag for severe blasting / logistics suspension")

df_ops["monsoon_flag"] = df_ops["month"].dt.month.isin([6, 7, 8, 9]).astype(int)
register_feature("monsoon_flag", "Weather", "1 if month in [6,7,8,9] else 0", "month", "binary", "Southwest monsoon season indicator")

df_ops["quarter"] = df_ops["month"].dt.quarter
register_feature("quarter", "Calendar", "month.quarter", "month", "integer 1-4", "Quarterly operational cycle")

# Temporal Rolling & Lag Features (strictly per-mine, forward in time)
print("  Computing chronological lags and rolling windows per mine...")
df_ops["actual_lag1"] = df_ops.groupby("mine")["actual_tonnes"].shift(1)
register_feature("actual_lag1", "Operations", "shift(actual_tonnes, 1)", "actual_tonnes", "tonnes", "Previous month actual production")

df_ops["actual_lag3"] = df_ops.groupby("mine")["actual_tonnes"].shift(3)
register_feature("actual_lag3", "Operations", "shift(actual_tonnes, 3)", "actual_tonnes", "tonnes", "Three-month lagged production")

df_ops["actual_tonnes_ma3"] = df_ops.groupby("mine")["actual_tonnes"].transform(lambda x: x.rolling(3, min_periods=1).mean())
register_feature("actual_tonnes_ma3", "Operations", "rolling_mean(actual_tonnes, 3)", "actual_tonnes", "tonnes", "3-month smoothed production baseline")

df_ops["actual_tonnes_ma6"] = df_ops.groupby("mine")["actual_tonnes"].transform(lambda x: x.rolling(6, min_periods=1).mean())
register_feature("actual_tonnes_ma6", "Operations", "rolling_mean(actual_tonnes, 6)", "actual_tonnes", "tonnes", "6-month smoothed production baseline")

df_ops["shortfall_ma3"] = df_ops.groupby("mine")["shortfall_pct"].transform(lambda x: x.rolling(3, min_periods=1).mean())
register_feature("shortfall_ma3", "Operations", "rolling_mean(shortfall_pct, 3)", "shortfall_pct", "%", "3-month smoothed shortfall percentage")

df_ops["shortfall_ma6"] = df_ops.groupby("mine")["shortfall_pct"].transform(lambda x: x.rolling(6, min_periods=1).mean())
register_feature("shortfall_ma6", "Operations", "rolling_mean(shortfall_pct, 6)", "shortfall_pct", "%", "6-month smoothed shortfall percentage")

out_ops_path = PROC_REV / "engineered_features_monthly_ops.csv"
df_ops.to_csv(out_ops_path, index=False)
print(f"  [OK] Saved monthly ops features: {df_ops.shape} -> {out_ops_path}")


# =========================================================================
# 3. MONTHLY WEATHER AGGREGATED FEATURES
# =========================================================================
print("\n3. Engineering Monthly Weather Features...")

sites = ["balaghat", "ukwa", "bhandara", "nagpur"]
monthly_wx_records = []

for site in sites:
    filepath = REV_DATA / "external" / "satellite" / f"weather_daily_{site}_2015_2026.csv"
    df_w = pd.read_csv(filepath, skiprows=3)
    df_w["time"] = pd.to_datetime(df_w["time"])
    df_w["year"] = df_w["time"].dt.year
    df_w["month"] = df_w["time"].dt.month
    
    rain_col = "precipitation_sum (mm)"
    tmean_col = "temperature_2m_mean (°C)"
    tmax_col = "temperature_2m_max (°C)"
    tmin_col = "temperature_2m_min (°C)"
    et0_col = "et0_fao_evapotranspiration (mm)"
    wind_col = "wind_speed_10m_max (km/h)"
    
    grouped = df_w.groupby(["year", "month"])
    for (yr, mo), grp in grouped:
        t_precip = grp[rain_col].sum()
        m_temp = grp[tmean_col].mean()
        mx_temp = grp[tmax_col].max()
        mn_temp = grp[tmin_col].min()
        t_range = mx_temp - mn_temp
        t_et0 = grp[et0_col].sum()
        mx_wind = grp[wind_col].max()
        r_days = (grp[rain_col] > 0.1).sum()
        hv_days = (grp[rain_col] >= 35.0).sum()
        ext_rain_flag = (grp[rain_col] > 100.0).any()
        
        monthly_wx_records.append({
            "site": site,
            "year": yr,
            "month": mo,
            "total_precip_mm": round(float(t_precip), 2),
            "mean_temp_c": round(float(m_temp), 2),
            "max_temp_c": round(float(mx_temp), 2),
            "min_temp_c": round(float(mn_temp), 2),
            "temp_range_c": round(float(t_range), 2),
            "total_et0_mm": round(float(t_et0), 2),
            "max_wind_kmh": round(float(mx_wind), 2),
            "rain_days": int(r_days),
            "heavy_rain_days": int(hv_days),
            "had_extreme_rain_day": int(ext_rain_flag)
        })

df_monthly_wx = pd.DataFrame(monthly_wx_records)
register_feature("total_precip_mm", "Weather", "sum(daily_precip)", "precipitation_sum", "mm", "Monthly cumulative rainfall")
register_feature("temp_range_c", "Weather", "max(temp_max) - min(temp_min)", "temperature_2m_max, min", "°C", "Monthly extreme thermal range")
register_feature("heavy_rain_days", "Weather", "count(daily_precip >= 35mm)", "precipitation_sum", "days", "Monthly heavy rainfall frequency")
register_feature("had_extreme_rain_day", "Weather", "1 if any daily_precip > 100mm else 0", "precipitation_sum", "binary", "Catastrophic precipitation event indicator")

out_wx_path = PROC_REV / "engineered_features_monthly_weather.csv"
df_monthly_wx.to_csv(out_wx_path, index=False)
print(f"  [OK] Saved monthly weather features: {df_monthly_wx.shape} -> {out_wx_path}")


# =========================================================================
# 4. SAVE FEATURE CATALOG & DOCUMENTATION
# =========================================================================
df_catalog = pd.DataFrame(feature_catalog)
df_catalog.to_csv(OUT_REV / "feature_dictionary.csv", index=False)
print(f"\nSaved feature dictionary ({len(df_catalog)} features) -> {OUT_REV / 'feature_dictionary.csv'}")

# Generate markdown documentation
doc_lines = [
    "# MOIL SIH26009 — Reviewed Feature Engineering Catalog\n",
    "> [!NOTE]",
    "> All derived features have been recomputed from the reviewed base data.",
    "> Aspect angles are transformed into orthogonal sine and cosine components.",
    "> `deposit_probability` is strictly isolated as a model diagnostic and NEVER used as a predictor.\n",
    "| Feature Name | Domain | Formula | Source Columns | Physical Units | Description / Purpose |",
    "|---|---|---|---|---|---|"
]
for _, r in df_catalog.iterrows():
    doc_lines.append(f"| `{r['feature_name']}` | {r['domain']} | `{r['mathematical_formula']}` | {r['source_columns']} | {r['units']} | {r['notes']} |")

with open(OUT_REV / "feature_engineering_documentation.md", "w", encoding="utf-8") as f:
    f.write("\n".join(doc_lines) + "\n")

print(f"Saved feature documentation -> {OUT_REV / 'feature_engineering_documentation.md'}")
print("\nReviewed Feature Engineering completed successfully!")

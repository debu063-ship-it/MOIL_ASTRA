#!/usr/bin/env python3
"""
MOIL SIH26009 — Reviewed Data Capping & Outlier Flagging Workflow
==================================================================
Safely revises outlier treatment following review guidelines:
  1. Default to Outlier FLAGGING rather than destructive automatic clipping.
  2. STRICTLY PRESERVE without clipping:
     - Rainfall (preserve valid extreme monsoon events; flag for review)
     - deposit_probability, labels, type
     - Coordinates (lat, lon, cell_id)
     - Aspect angles (do not apply linear fences to angles; compute sin/cos)
     - Production metrics: planned_tonnes, actual_tonnes, shortfall_tonnes
       (preserves shortfall == max(planned - actual, 0) accounting identity)
  3. Recompute derived features from reviewed base data.
  4. For optional model preparation: fit thresholds on training split ONLY,
     apply to validation/test, and log all metadata.
  5. Save reviewed outputs to data/capped_reviewed/.
"""

import os
import sys
import io
import json
import warnings
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")

BASE = Path(r"c:\Users\Debu018\Downloads\MOIL SIH26009")
RAW = BASE / "data" / "raw"
SYNTH = BASE / "data" / "synthetic"
EXT_SAT = BASE / "data" / "external" / "satellite"
PROC = BASE / "data" / "processed"

REV_DIR = BASE / "data" / "capped_reviewed"
(REV_DIR / "raw").mkdir(parents=True, exist_ok=True)
(REV_DIR / "synthetic").mkdir(parents=True, exist_ok=True)
(REV_DIR / "external" / "satellite").mkdir(parents=True, exist_ok=True)
(REV_DIR / "processed").mkdir(parents=True, exist_ok=True)
(REV_DIR / "model_ready").mkdir(parents=True, exist_ok=True)

OUT_REV_DIR = BASE / "outputs" / "data_capping_review"
OUT_REV_DIR.mkdir(parents=True, exist_ok=True)

# ── Non-clipped protected columns policy ──
PROTECTED_COLUMNS = {
    "lat", "lon", "latitude", "longitude", "cell_id", "name", "district", "state",
    "label", "type", "in_gondite_formation", "in_sausar",
    "deposit_probability", "risk_category",
    "planned_tonnes", "actual_tonnes", "shortfall_tonnes",
    "precipitation_sum (mm)", "precip_mm", "monthly_rain_mm", "total_precip",
    "aspect",  # Angle is cyclical; transformed to sin/cos
    "time", "date", "month", "datetime", "mine", "disruption_event", "gsi_group", "gsi_age"
}

PHYSICAL_LIMITS = {
    "B2": (0.0, 1.0), "B3": (0.0, 1.0), "B4": (0.0, 1.0),
    "B8": (0.0, 1.0), "B11": (0.0, 1.0), "B12": (0.0, 1.0),
    "ndvi": (-1.0, 1.0),
    "iron_oxide_index": (0.0, None),
    "swir_nir_ratio": (0.0, None),
    "clay_alteration_idx": (0.0, None),
    "ferrous_iron_idx": (0.0, None),
    "elevation": (0.0, None),
    "slope": (0.0, 90.0),
    "aspect_sin": (-1.0, 1.0),
    "aspect_cos": (-1.0, 1.0),
    "dist_to_gondite_km": (0.0, None),
    "equipment_availability": (0.0, 1.0),
    "downtime_hours": (0.0, 744.0),
    "heavy_rain_days": (0.0, 31.0),
    "temperature_2m_mean (°C)": (-10.0, 60.0),
    "temperature_2m_max (°C)": (-10.0, 60.0),
    "temperature_2m_min (°C)": (-10.0, 60.0),
    "temp_mean": (-10.0, 60.0), "temp_max": (-10.0, 60.0), "temp_min": (-10.0, 60.0),
    "et0_fao_evapotranspiration (mm)": (0.0, None),
    "wind_speed_10m_max (km/h)": (0.0, None),
    "et0_mm": (0.0, None), "wind_max_kmh": (0.0, None),
    "soil_moisture_0_to_7cm (m³/m³)": (0.0, 0.65),
    "soil_moisture_7_to_28cm (m³/m³)": (0.0, 0.65),
    "sm_0_7cm": (0.0, 0.65), "sm_7_28cm": (0.0, 0.65)
}

capping_log_records = []


def flag_outliers_and_protect(df, numeric_cols, dataset_name, k=1.5):
    """
    Computes IQR fences and flags outliers with boolean indicators.
    Guarantees protected columns are NEVER modified or clipped.
    Adds sine/cosine transformations for aspect if present.
    """
    df_out = df.copy()
    
    # Transform cyclical aspect if present
    if "aspect" in df_out.columns:
        rad = np.radians(df_out["aspect"])
        df_out["aspect_sin"] = np.round(np.sin(rad), 6)
        df_out["aspect_cos"] = np.round(np.cos(rad), 6)
    
    flagged_any_cols = []
    
    for col in numeric_cols:
        if col not in df_out.columns:
            continue
        
        # Explicitly skip aspect from linear IQR outlier flagging
        if col == "aspect":
            continue
        
        s = df_out[col].dropna()
        if len(s) < 5:
            continue
            
        is_protected = col in PROTECTED_COLUMNS
        
        q1 = s.quantile(0.25)
        q3 = s.quantile(0.75)
        iqr = q3 - q1
        lower_fence = q1 - k * iqr
        upper_fence = q3 + k * iqr
        
        phys_min, phys_max = PHYSICAL_LIMITS.get(col, (None, None))
        effective_lower = max(lower_fence, phys_min) if phys_min is not None else lower_fence
        effective_upper = min(upper_fence, phys_max) if phys_max is not None else upper_fence
        
        lower_flag_mask = df_out[col] < effective_lower
        upper_flag_mask = df_out[col] > effective_upper
        outlier_mask = lower_flag_mask | upper_flag_mask
        
        n_lower = lower_flag_mask.sum()
        n_upper = upper_flag_mask.sum()
        n_flagged = outlier_mask.sum()
        pct_flagged = (n_flagged / len(df_out)) * 100
        
        # Add explicit flagging column
        flag_col_name = f"flag_{col}_outlier"
        df_out[flag_col_name] = outlier_mask.astype(int)
        flagged_any_cols.append(flag_col_name)
        
        # Values changed count: strictly 0 for all protected features and default flagging mode!
        n_values_changed = 0
        
        capping_log_records.append({
            "dataset": dataset_name,
            "feature": col,
            "is_protected": is_protected,
            "policy": "Protected (Preserved exact raw values; flagged only)" if is_protected else "Flagged for review (Values preserved)",
            "n_records": len(df_out),
            "lower_fence": round(float(effective_lower), 4),
            "upper_fence": round(float(effective_upper), 4),
            "n_flagged_lower": int(n_lower),
            "n_flagged_upper": int(n_upper),
            "n_flagged_total": int(n_flagged),
            "pct_flagged": round(float(pct_flagged), 2),
            "n_values_changed": int(n_values_changed),
            "min_raw": round(float(s.min()), 4),
            "max_raw": round(float(s.max()), 4),
            "mean_raw": round(float(s.mean()), 4),
            "std_raw": round(float(s.std()), 4),
            "skew_raw": round(float(s.skew()), 4),
        })

    # Summary overall outlier flag
    if flagged_any_cols:
        df_out["outlier_feature_count"] = df_out[flagged_any_cols].sum(axis=1)
        df_out["is_any_outlier"] = (df_out["outlier_feature_count"] > 0).astype(int)
    
    return df_out


print("Starting Reviewed Capping & Outlier Flagging Workflow...")

# ── 1. LABELED SAMPLES DATASET ──
df_lab_raw = pd.read_csv(RAW / "labeled_samples_dataset.csv")
lab_numeric = [
    "B2", "B3", "B4", "B8", "B11", "B12",
    "elevation", "slope", # raw aspect excluded from linear IQR flagging
    "iron_oxide_index", "swir_nir_ratio",
    "clay_alteration_idx", "ferrous_iron_idx",
    "ndvi", "dist_to_gondite_km"
]
df_lab_rev = flag_outliers_and_protect(df_lab_raw, lab_numeric, "A. Labeled Samples Dataset")
df_lab_rev.to_csv(REV_DIR / "raw" / "labeled_samples_dataset.csv", index=False)
print(f"  [OK] Labeled samples reviewed: {len(df_lab_rev)} rows -> {REV_DIR / 'raw' / 'labeled_samples_dataset.csv'}")

# ── 2. REGION GRID PREDICTIONS ──
df_grid_raw = pd.read_csv(RAW / "region_grid_predictions.csv")
grid_numeric = [
    "B2", "B3", "B4", "B8", "B11", "B12",
    "elevation", "slope", # raw aspect excluded
    "iron_oxide_index", "swir_nir_ratio",
    "clay_alteration_idx", "ferrous_iron_idx",
    "ndvi", "dist_to_gondite_km", "deposit_probability"
]
df_grid_rev = flag_outliers_and_protect(df_grid_raw, grid_numeric, "B. Region Grid Predictions")
df_grid_rev.to_csv(REV_DIR / "raw" / "region_grid_predictions.csv", index=False)
print(f"  [OK] Region grid reviewed: {len(df_grid_rev)} rows -> {REV_DIR / 'raw' / 'region_grid_predictions.csv'}")

# ── 3. SENTINEL-2 + DEM GRID SAMPLES ──
df_s2_raw = pd.read_csv(EXT_SAT / "s2_dem_grid_samples.csv")
s2_numeric = ["B2", "B3", "B4", "B8", "B11", "B12", "ndvi", "elevation", "slope"] # raw aspect excluded
df_s2_rev = flag_outliers_and_protect(df_s2_raw, s2_numeric, "C. Sentinel-2 + DEM Grid")
df_s2_rev.to_csv(REV_DIR / "external" / "satellite" / "s2_dem_grid_samples.csv", index=False)
print(f"  [OK] Sentinel-2 + DEM reviewed: {len(df_s2_rev)} rows -> {REV_DIR / 'external' / 'satellite' / 's2_dem_grid_samples.csv'}")

# ── 4. MONTHLY OPS SYNTHETIC (2015-2026) ──
df_ops_raw = pd.read_csv(SYNTH / "monthly_ops_synthetic_2015_2026.csv")
ops_numeric = [
    "planned_tonnes", "actual_tonnes", "shortfall_tonnes",
    "equipment_availability", "downtime_hours",
    "monthly_rain_mm", "heavy_rain_days"
]
df_ops_rev = flag_outliers_and_protect(df_ops_raw, ops_numeric, "D. Monthly Ops Synthetic")
# Consistent monthly extreme rainfall definition: strictly monthly_rain_mm > 500 mm (monsoon inundation)
# Kept strictly separate from the generic IQR fence flag
df_ops_rev["flag_extreme_rain_review"] = (df_ops_rev["monthly_rain_mm"] > 500.0).astype(int)
df_ops_rev.to_csv(REV_DIR / "synthetic" / "monthly_ops_synthetic_2015_2026.csv", index=False)
print(f"  [OK] Monthly ops reviewed: {len(df_ops_rev)} rows -> {REV_DIR / 'synthetic' / 'monthly_ops_synthetic_2015_2026.csv'}")

# ── 5. PRODUCTION SCENARIO (Full Synthetic) ──
df_prod_raw = pd.read_csv(SYNTH / "production_scenario.csv")
prod_numeric = [
    "planned_tonnes", "actual_tonnes", "shortfall_tonnes",
    "equipment_availability", "monthly_rain_mm", "heavy_rain_days"
]
df_prod_rev = flag_outliers_and_protect(df_prod_raw, prod_numeric, "E. Production Scenario")
# Consistent monthly extreme rainfall definition: strictly monthly_rain_mm > 500 mm
df_prod_rev["flag_extreme_rain_review"] = (df_prod_rev["monthly_rain_mm"] > 500.0).astype(int)
df_prod_rev.to_csv(REV_DIR / "synthetic" / "production_scenario.csv", index=False)
print(f"  [OK] Production scenario reviewed: {len(df_prod_rev)} rows -> {REV_DIR / 'synthetic' / 'production_scenario.csv'}")

# ── 6. DAILY WEATHER SATELLITE (4 SITES) ──
sites = ["balaghat", "ukwa", "bhandara", "nagpur"]
for site in sites:
    filepath = EXT_SAT / f"weather_daily_{site}_2015_2026.csv"
    with open(filepath, "r", encoding="utf-8") as f:
        meta_lines = [f.readline() for _ in range(3)]
    df_w_raw = pd.read_csv(filepath, skiprows=3)
    cols_w = [c for c in df_w_raw.columns if c != "time"]
    df_w_rev = flag_outliers_and_protect(df_w_raw, cols_w, f"F. Weather Daily ({site.title()})")
    
    # Specific extreme rain flag: STRICTLY precipitation > 100mm
    # Generic IQR outlier flag (flag_precipitation_sum (mm)_outlier) is kept strictly separate
    rain_col = "precipitation_sum (mm)"
    df_w_rev["flag_extreme_rain_review"] = (df_w_rev[rain_col] > 100.0).astype(int)
    
    out_path = REV_DIR / "external" / "satellite" / f"weather_daily_{site}_2015_2026.csv"
    with open(out_path, "w", encoding="utf-8") as f:
        for line in meta_lines:
            f.write(line)
        df_w_rev.to_csv(f, index=False)
    print(f"  [OK] Weather daily ({site}) reviewed: {len(df_w_rev)} rows (extreme rain days >100mm: {df_w_rev['flag_extreme_rain_review'].sum()})")
    


# ── 7. HOURLY SOIL MOISTURE (4 SITES) ──
for site in sites:
    filepath = EXT_SAT / f"soilmoisture_hourly_{site}_2015_2026.csv"
    with open(filepath, "r", encoding="utf-8") as f:
        meta_lines = [f.readline() for _ in range(3)]
    df_sm_raw = pd.read_csv(filepath, skiprows=3)
    cols_sm = [c for c in df_sm_raw.columns if c != "time"]
    df_sm_rev = flag_outliers_and_protect(df_sm_raw, cols_sm, f"G. Soil Moisture ({site.title()})")
    
    out_path = REV_DIR / "external" / "satellite" / f"soilmoisture_hourly_{site}_2015_2026.csv"
    with open(out_path, "w", encoding="utf-8") as f:
        for line in meta_lines:
            f.write(line)
        df_sm_rev.to_csv(f, index=False)
    print(f"  [OK] Soil moisture hourly ({site}) reviewed: {len(df_sm_rev)} rows")

# ── 8. MODEL PREPARATION CAPPING (TRAIN-ONLY FIT) ──
print("\nPreparing Model-Ready Train/Test Datasets with Train-Only Capping...")

# Clean up / archive any stale spatial split files if present at top level
archive_dir = REV_DIR / "model_ready" / "archived_obsolete_splits"
archive_dir.mkdir(parents=True, exist_ok=True)
for stale_name in ["prospectivity_train_spatial_balaghat.csv", "prospectivity_test_spatial_bhandara_nagpur.csv"]:
    stale_p = REV_DIR / "model_ready" / stale_name
    if stale_p.exists():
        stale_p.rename(archive_dir / f"STALE_DO_NOT_USE_{stale_name}")

# Predictor features: aspect_sin and aspect_cos are kept as unclipped model features
# Only continuous non-trigonometric physical features are eligible for IQR clipping
features_to_clip = [
    "B2", "B3", "B4", "B8", "B11", "B12",
    "elevation", "slope",
    "iron_oxide_index", "swir_nir_ratio", "clay_alteration_idx", "ferrous_iron_idx",
    "ndvi", "dist_to_gondite_km"
]

# A. Stratified Split (70/30, seed=42)
train_df, test_df = train_test_split(
    df_lab_rev, test_size=0.30, random_state=42, stratify=df_lab_rev["label"]
)
train_df = train_df.copy()
test_df = test_df.copy()

# Fit capping thresholds ON TRAINING DATA ONLY (excluding aspect_sin/aspect_cos)
thresholds_record = {}
k_prep = 1.5

for feat in features_to_clip:
    q1 = train_df[feat].quantile(0.25)
    q3 = train_df[feat].quantile(0.75)
    iqr = q3 - q1
    raw_lo = q1 - k_prep * iqr
    raw_hi = q3 + k_prep * iqr
    
    phys_min, phys_max = PHYSICAL_LIMITS.get(feat, (None, None))
    lo = max(raw_lo, phys_min) if phys_min is not None else raw_lo
    hi = min(raw_hi, phys_max) if phys_max is not None else raw_hi
    if hi < lo:
        hi = lo
        
    thresholds_record[feat] = {
        "q1_train": float(q1),
        "q3_train": float(q3),
        "iqr_train": float(iqr),
        "lower_bound": float(lo),
        "upper_bound": float(hi),
        "train_capped_lower": int((train_df[feat] < lo).sum()),
        "train_capped_upper": int((train_df[feat] > hi).sum()),
        "test_capped_lower": int((test_df[feat] < lo).sum()),
        "test_capped_upper": int((test_df[feat] > hi).sum()),
    }
    
    # Apply train-derived thresholds to train and test
    train_df[feat] = train_df[feat].clip(lower=lo, upper=hi)
    test_df[feat] = test_df[feat].clip(lower=lo, upper=hi)

# B. Spatial Coordinate Split: East (lon >= 79.75) vs West (lon < 79.75)
spatial_train = df_lab_rev[df_lab_rev["lon"] < 79.75].copy()   # West Block
spatial_test = df_lab_rev[df_lab_rev["lon"] >= 79.75].copy()  # East Block
spatial_thresholds = {}

for feat in features_to_clip:
    q1 = spatial_train[feat].quantile(0.25)
    q3 = spatial_train[feat].quantile(0.75)
    iqr = q3 - q1
    raw_lo = q1 - k_prep * iqr
    raw_hi = q3 + k_prep * iqr
    
    phys_min, phys_max = PHYSICAL_LIMITS.get(feat, (None, None))
    lo = max(raw_lo, phys_min) if phys_min is not None else raw_lo
    hi = min(raw_hi, phys_max) if phys_max is not None else raw_hi
    if hi < lo:
        hi = lo
        
    spatial_thresholds[feat] = {
        "lower_bound": float(lo),
        "upper_bound": float(hi),
    }
    spatial_train[feat] = spatial_train[feat].clip(lower=lo, upper=hi)
    spatial_test[feat] = spatial_test[feat].clip(lower=lo, upper=hi)

# Save model-ready datasets and metadata
train_df.to_csv(REV_DIR / "model_ready" / "prospectivity_train_stratified_capped.csv", index=False)
test_df.to_csv(REV_DIR / "model_ready" / "prospectivity_test_stratified_capped.csv", index=False)
spatial_train.to_csv(REV_DIR / "model_ready" / "prospectivity_train_spatial_west.csv", index=False)
spatial_test.to_csv(REV_DIR / "model_ready" / "prospectivity_test_spatial_east.csv", index=False)

model_prep_metadata = {
    "workflow": "Model-Preparation Capping (Train-Only Fit)",
    "method": "Tukey's IQR Fences (1.5*IQR) with Physical Domain Clamping",
    "target_variable": "label",
    "deposit_probability_used_as_predictor": False,
    "stratified_split": {
        "train_size": len(train_df),
        "test_size": len(test_df),
        "train_positive_count": int(train_df["label"].sum()),
        "test_positive_count": int(test_df["label"].sum()),
        "random_state": 42,
        "fitted_thresholds": thresholds_record
    },
    "spatial_split": {
        "spatial_boundary": "Longitude 79.75°E",
        "spatial_train_region": "West Block (lon < 79.75)",
        "spatial_test_region": "East Block (lon >= 79.75)",
        "spatial_train_size": len(spatial_train),
        "spatial_test_size": len(spatial_test),
        "spatial_train_positive": int(spatial_train["label"].sum()),
        "spatial_train_negative": int((spatial_train["label"] == 0).sum()),
        "spatial_test_positive": int(spatial_test["label"].sum()),
        "spatial_test_negative": int((spatial_test["label"] == 0).sum()),
        "fitted_thresholds": spatial_thresholds
    }
}


with open(REV_DIR / "model_ready" / "prospectivity_model_prep_metadata.json", "w", encoding="utf-8") as f:
    json.dump(model_prep_metadata, f, indent=2)

print("  [OK] Saved model-ready train/test sets and metadata to data/capped_reviewed/model_ready/")

# ── Save comprehensive capping & flagging log table ──
df_capping_log = pd.DataFrame(capping_log_records)
df_capping_log.to_csv(OUT_REV_DIR / "capping_and_flagging_summary.csv", index=False)
print(f"  [OK] Capping & flagging summary saved to: {OUT_REV_DIR / 'capping_and_flagging_summary.csv'}")

print("\nReviewed Capping & Flagging completed successfully!")

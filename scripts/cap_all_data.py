#!/usr/bin/env python3
"""
MOIL SIH26009 — Domain-Aware IQR Data Capping & Outlier Treatment
==================================================================
Performs Domain-Aware IQR Capping (Tukey's Fences: [Q1 - 1.5*IQR, Q3 + 1.5*IQR])
combined with physical domain limits across ALL project datasets.

Output:
  - Capped datasets saved to: data/capped/
  - Detailed before/after statistical report: outputs/data_capping_report.txt
  - Before/after distribution plots: outputs/eda_plots/capped_*.png
"""

import os
import sys
import io
import warnings
from pathlib import Path

# Windows console encoding fix
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

# ── Paths ──
BASE = Path(r"c:\Users\Debu018\Downloads\MOIL SIH26009")
RAW = BASE / "data" / "raw"
SYNTH = BASE / "data" / "synthetic"
PROC = BASE / "data" / "processed"
EXT_SAT = BASE / "data" / "external" / "satellite"
CAPPED = BASE / "data" / "capped"

# Create target directories
(CAPPED / "raw").mkdir(parents=True, exist_ok=True)
(CAPPED / "synthetic").mkdir(parents=True, exist_ok=True)
(CAPPED / "processed").mkdir(parents=True, exist_ok=True)
(CAPPED / "external" / "satellite").mkdir(parents=True, exist_ok=True)

PLOT_DIR = BASE / "outputs" / "eda_plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR = BASE / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150,
    "figure.figsize": (12, 6),
    "axes.titlesize": 12, "axes.labelsize": 10, "font.size": 9,
})
sns.set_theme(style="whitegrid", palette="deep")

report = []

def log(msg=""):
    print(msg)
    report.append(msg)

# ── Physical Domain Constraints ──
DOMAIN_BOUNDS = {
    # Spectral bands (reflectance)
    "B2": (0.0, 1.0), "B3": (0.0, 1.0), "B4": (0.0, 1.0),
    "B8": (0.0, 1.0), "B11": (0.0, 1.0), "B12": (0.0, 1.0),
    "ndvi": (-1.0, 1.0),
    "iron_oxide_index": (0.0, None),
    "swir_nir_ratio": (0.0, None),
    "clay_alteration_idx": (0.0, None),
    "ferrous_iron_idx": (0.0, None),
    # Topography
    "elevation": (0.0, None),
    "slope": (0.0, 90.0),
    "aspect": (0.0, 360.0),
    # Prospectivity
    "dist_to_gondite_km": (0.0, None),
    "deposit_probability": (0.0, 1.0),
    # Operations
    "planned_tonnes": (0.0, None),
    "actual_tonnes": (0.0, None),
    "shortfall_tonnes": (0.0, None),
    "equipment_availability": (0.0, 1.0),
    "downtime_hours": (0.0, 744.0),
    "monthly_rain_mm": (0.0, None),
    "heavy_rain_days": (0.0, 31.0),
    "shortfall_pct": (0.0, None),
    "production_efficiency": (0.0, None),
    # Weather
    "precipitation_sum (mm)": (0.0, None),
    "precip_mm": (0.0, None),
    "temperature_2m_mean (°C)": (-10.0, 60.0),
    "temperature_2m_max (°C)": (-10.0, 60.0),
    "temperature_2m_min (°C)": (-10.0, 60.0),
    "et0_fao_evapotranspiration (mm)": (0.0, None),
    "wind_speed_10m_max (km/h)": (0.0, None),
    "temp_mean": (-10.0, 60.0), "temp_max": (-10.0, 60.0), "temp_min": (-10.0, 60.0),
    "et0_mm": (0.0, None), "wind_max_kmh": (0.0, None),
    # Soil Moisture
    "soil_moisture_0_to_7cm (m³/m³)": (0.0, 0.65),
    "soil_moisture_7_to_28cm (m³/m³)": (0.0, 0.65),
    "sm_0_7cm": (0.0, 0.65), "sm_7_28cm": (0.0, 0.65)
}


def cap_dataframe(df, cols, dataset_name, k=1.5):
    """
    Applies Domain-Aware IQR Capping to numeric columns in df.
    Returns (capped_df, summary_df).
    """
    capped_df = df.copy()
    stats_list = []

    log(f"\n{'='*110}")
    log(f"CAPPING DATASET: {dataset_name} (n={len(df)})")
    log(f"{'='*110}")
    log(f"{'Feature':<28} {'Lower Fence':>12} {'Upper Fence':>12} {'Capped Lo':>10} {'Capped Hi':>10} {'% Capped':>9} {'Skew Before':>12} {'Skew After':>12}")
    log("-" * 110)

    for col in cols:
        if col not in df.columns:
            continue
        s_orig = df[col].dropna()
        if len(s_orig) < 5:
            continue

        q1 = s_orig.quantile(0.25)
        q3 = s_orig.quantile(0.75)
        iqr = q3 - q1
        
        # Tukey fences
        raw_lo = q1 - k * iqr
        raw_hi = q3 + k * iqr

        # Apply physical domain constraints
        phys_lo, phys_hi = DOMAIN_BOUNDS.get(col, (None, None))
        lo_bound = raw_lo
        hi_bound = raw_hi

        if phys_lo is not None:
            lo_bound = max(raw_lo, phys_lo)
        if phys_hi is not None:
            hi_bound = min(raw_hi, phys_hi)
        
        # If IQR upper is less than physical lower (edge case), adjust
        if hi_bound < lo_bound:
            hi_bound = lo_bound

        # Perform clipping
        s_capped = s_orig.clip(lower=lo_bound, upper=hi_bound)
        capped_df[col] = s_capped

        n_lo = (s_orig < lo_bound).sum()
        n_hi = (s_orig > hi_bound).sum()
        n_total_capped = n_lo + n_hi
        pct_capped = (n_total_capped / len(s_orig)) * 100

        skew_before = s_orig.skew()
        skew_after = s_capped.skew()
        kurt_before = s_orig.kurtosis()
        kurt_after = s_capped.kurtosis()

        log(f"{col:<28} {lo_bound:>12.4f} {hi_bound:>12.4f} {n_lo:>10} {n_hi:>10} {pct_capped:>8.2f}% {skew_before:>12.3f} {skew_after:>12.3f}")

        stats_list.append({
            "dataset": dataset_name,
            "feature": col,
            "n": len(s_orig),
            "lower_bound": lo_bound,
            "upper_bound": hi_bound,
            "n_capped_lower": n_lo,
            "n_capped_upper": n_hi,
            "n_total_capped": n_total_capped,
            "pct_capped": pct_capped,
            "min_before": s_orig.min(),
            "max_before": s_orig.max(),
            "min_after": s_capped.min(),
            "max_after": s_capped.max(),
            "mean_before": s_orig.mean(),
            "mean_after": s_capped.mean(),
            "std_before": s_orig.std(),
            "std_after": s_capped.std(),
            "skew_before": skew_before,
            "skew_after": skew_after,
            "kurt_before": kurt_before,
            "kurt_after": kurt_after
        })

    summary_df = pd.DataFrame(stats_list)
    return capped_df, summary_df


def plot_capping_comparison(df_orig, df_capped, cols, title, out_filename, ncols=4):
    """Plots before vs after boxplots/distributions for capped features."""
    cols_to_plot = [c for c in cols if c in df_orig.columns and c in df_capped.columns]
    if not cols_to_plot:
        return
    # Limit to at most 8 features for readability
    if len(cols_to_plot) > 8:
        cols_to_plot = cols_to_plot[:8]

    n = len(cols_to_plot)
    ncols = min(ncols, n)
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, 3.5 * nrows))
    axes = np.array(axes).ravel() if nrows * ncols > 1 else [axes]

    for i, col in enumerate(cols_to_plot):
        ax = axes[i]
        s_orig = df_orig[col].dropna()
        s_cap = df_capped[col].dropna()

        # Combine into long form for seaborn boxplot
        plot_data = pd.DataFrame({
            "Value": pd.concat([s_orig, s_cap]),
            "Version": ["Original"] * len(s_orig) + ["Capped"] * len(s_cap)
        })
        sns.boxplot(data=plot_data, x="Version", y="Value", ax=ax, palette=["#e76f51", "#2a9d8f"], width=0.4)
        ax.set_title(f"{col}", fontweight="bold", fontsize=10)
        ax.set_xlabel("")
        ax.set_ylabel("")

    for j in range(len(cols_to_plot), len(axes)):
        axes[j].set_visible(False)

    fig.suptitle(title, fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(PLOT_DIR / out_filename)
    plt.close()


all_summaries = []

# =====================================================================
# 1. LABELED SAMPLES DATASET
# =====================================================================
path_lab = RAW / "labeled_samples_dataset.csv"
df_lab = pd.read_csv(path_lab)
lab_cols = [
    "B2", "B3", "B4", "B8", "B11", "B12",
    "elevation", "slope", "aspect",
    "iron_oxide_index", "swir_nir_ratio",
    "clay_alteration_idx", "ferrous_iron_idx",
    "ndvi", "dist_to_gondite_km"
]
capped_lab, sum_lab = cap_dataframe(df_lab, lab_cols, "A. Labeled Samples Dataset")
capped_lab.to_csv(CAPPED / "raw" / "labeled_samples_dataset.csv", index=False)
plot_capping_comparison(df_lab, capped_lab, ["elevation", "slope", "B8", "ndvi", "dist_to_gondite_km", "iron_oxide_index"],
                        "Before vs After Capping: Labeled Samples (n=90)", "capped_A_labeled_samples.png", ncols=3)
all_summaries.append(sum_lab)


# =====================================================================
# 2. REGION GRID PREDICTIONS
# =====================================================================
path_grid = RAW / "region_grid_predictions.csv"
df_grid = pd.read_csv(path_grid)
grid_cols = [
    "B2", "B3", "B4", "B8", "B11", "B12",
    "elevation", "slope", "aspect",
    "iron_oxide_index", "swir_nir_ratio",
    "clay_alteration_idx", "ferrous_iron_idx",
    "ndvi", "dist_to_gondite_km", "deposit_probability"
]
capped_grid, sum_grid = cap_dataframe(df_grid, grid_cols, "B. Region Grid Predictions")
capped_grid.to_csv(CAPPED / "raw" / "region_grid_predictions.csv", index=False)
plot_capping_comparison(df_grid, capped_grid, ["elevation", "slope", "B8", "ndvi", "dist_to_gondite_km", "deposit_probability"],
                        "Before vs After Capping: Region Grid (n=5,568)", "capped_B_grid_predictions.png", ncols=3)
all_summaries.append(sum_grid)


# =====================================================================
# 3. SENTINEL-2 + DEM GRID SAMPLES
# =====================================================================
path_s2 = EXT_SAT / "s2_dem_grid_samples.csv"
df_s2 = pd.read_csv(path_s2)
s2_cols = ["B2", "B3", "B4", "B8", "B11", "B12", "ndvi", "elevation", "slope", "aspect"]
capped_s2, sum_s2 = cap_dataframe(df_s2, s2_cols, "C. Sentinel-2 + DEM Grid")
capped_s2.to_csv(CAPPED / "external" / "satellite" / "s2_dem_grid_samples.csv", index=False)
plot_capping_comparison(df_s2, capped_s2, ["elevation", "slope", "B8", "B11", "ndvi"],
                        "Before vs After Capping: Sentinel-2 + DEM (n=5,568)", "capped_C_sentinel2_dem.png", ncols=3)
all_summaries.append(sum_s2)


# =====================================================================
# 4. MONTHLY OPS SYNTHETIC (2015-2026)
# =====================================================================
path_ops = SYNTH / "monthly_ops_synthetic_2015_2026.csv"
df_ops = pd.read_csv(path_ops)
ops_cols = [
    "planned_tonnes", "actual_tonnes", "shortfall_tonnes",
    "equipment_availability", "downtime_hours",
    "monthly_rain_mm", "heavy_rain_days"
]
capped_ops, sum_ops = cap_dataframe(df_ops, ops_cols, "D. Monthly Ops Synthetic")
capped_ops.to_csv(CAPPED / "synthetic" / "monthly_ops_synthetic_2015_2026.csv", index=False)
plot_capping_comparison(df_ops, capped_ops, ["planned_tonnes", "actual_tonnes", "shortfall_tonnes", "downtime_hours", "monthly_rain_mm"],
                        "Before vs After Capping: Monthly Ops (n=1,188)", "capped_D_monthly_ops.png", ncols=3)
all_summaries.append(sum_ops)


# =====================================================================
# 5. PRODUCTION SCENARIO (Full Synthetic)
# =====================================================================
path_prod = SYNTH / "production_scenario.csv"
df_prod = pd.read_csv(path_prod)
prod_cols = [
    "planned_tonnes", "actual_tonnes", "shortfall_tonnes",
    "equipment_availability", "monthly_rain_mm", "heavy_rain_days"
]
capped_prod, sum_prod = cap_dataframe(df_prod, prod_cols, "E. Production Scenario")
capped_prod.to_csv(CAPPED / "synthetic" / "production_scenario.csv", index=False)
plot_capping_comparison(df_prod, capped_prod, ["planned_tonnes", "actual_tonnes", "shortfall_tonnes", "monthly_rain_mm"],
                        "Before vs After Capping: Production Scenario (n=1,452)", "capped_E_production_scenario.png", ncols=2)
all_summaries.append(sum_prod)


# =====================================================================
# 6. DAILY WEATHER SATELLITE / REANALYSIS (4 SITES)
# =====================================================================
sites = ["balaghat", "ukwa", "bhandara", "nagpur"]
wx_summaries = []

for site in sites:
    filepath = EXT_SAT / f"weather_daily_{site}_2015_2026.csv"
    # Read the top 3 metadata lines to preserve exact structure
    with open(filepath, "r", encoding="utf-8") as f:
        meta_lines = [f.readline() for _ in range(3)]
    
    df_w = pd.read_csv(filepath, skiprows=3)
    cols_w = [c for c in df_w.columns if c != "time"]
    capped_w, sum_w = cap_dataframe(df_w, cols_w, f"F. Weather Daily ({site.title()})")
    wx_summaries.append(sum_w)
    
    # Write back preserving the 3 metadata lines
    out_path = CAPPED / "external" / "satellite" / f"weather_daily_{site}_2015_2026.csv"
    with open(out_path, "w", encoding="utf-8") as f:
        for line in meta_lines:
            f.write(line)
        capped_w.to_csv(f, index=False)

if wx_summaries:
    all_summaries.append(pd.concat(wx_summaries, ignore_index=True))


# =====================================================================
# 7. HOURLY SOIL MOISTURE (4 SITES)
# =====================================================================
sm_summaries = []
for site in sites:
    filepath = EXT_SAT / f"soilmoisture_hourly_{site}_2015_2026.csv"
    with open(filepath, "r", encoding="utf-8") as f:
        meta_lines = [f.readline() for _ in range(3)]
        
    df_sm = pd.read_csv(filepath, skiprows=3)
    cols_sm = [c for c in df_sm.columns if c != "time"]
    capped_sm, sum_sm = cap_dataframe(df_sm, cols_sm, f"G. Soil Moisture ({site.title()})")
    sm_summaries.append(sum_sm)
    
    out_path = CAPPED / "external" / "satellite" / f"soilmoisture_hourly_{site}_2015_2026.csv"
    with open(out_path, "w", encoding="utf-8") as f:
        for line in meta_lines:
            f.write(line)
        capped_sm.to_csv(f, index=False)

if sm_summaries:
    all_summaries.append(pd.concat(sm_summaries, ignore_index=True))


# =====================================================================
# 8. PROCESSED ENGINEERED FEATURES (IF PRESENT)
# =====================================================================
eng_grid_path = PROC / "engineered_features_integrated_grid.csv"
if eng_grid_path.exists():
    df_eng = pd.read_csv(eng_grid_path)
    num_cols = df_eng.select_dtypes(include=[np.number]).columns.tolist()
    # Exclude lat/lon/cell_id from capping
    num_cols = [c for c in num_cols if c not in ["cell_id", "lon", "lat", "label"]]
    capped_eng, sum_eng = cap_dataframe(df_eng, num_cols, "H. Processed Engineered Grid")
    capped_eng.to_csv(CAPPED / "processed" / "engineered_features_integrated_grid.csv", index=False)
    all_summaries.append(sum_eng)

eng_ops_path = PROC / "engineered_features_monthly_ops.csv"
if eng_ops_path.exists():
    df_eops = pd.read_csv(eng_ops_path)
    num_cols = df_eops.select_dtypes(include=[np.number]).columns.tolist()
    num_cols = [c for c in num_cols if c not in ["year", "month_num", "disruption_occurred"]]
    capped_eops, sum_eops = cap_dataframe(df_eops, num_cols, "I. Processed Engineered Monthly Ops")
    capped_eops.to_csv(CAPPED / "processed" / "engineered_features_monthly_ops.csv", index=False)
    all_summaries.append(sum_eops)

eng_wx_path = PROC / "engineered_features_monthly_weather.csv"
if eng_wx_path.exists():
    df_ewx = pd.read_csv(eng_wx_path)
    num_cols = df_ewx.select_dtypes(include=[np.number]).columns.tolist()
    num_cols = [c for c in num_cols if c not in ["year", "month"]]
    capped_ewx, sum_ewx = cap_dataframe(df_ewx, num_cols, "J. Processed Engineered Monthly Weather")
    capped_ewx.to_csv(CAPPED / "processed" / "engineered_features_monthly_weather.csv", index=False)
    all_summaries.append(sum_ewx)


# =====================================================================
# SUMMARY & REPORT
# =====================================================================
full_summary = pd.concat(all_summaries, ignore_index=True)
full_summary.to_csv(OUT_DIR / "capping_summary_table.csv", index=False)

log("\n" + "="*110)
log("OVERALL CAPPING IMPACT SUMMARY")
log("="*110)
log(f"{'Dataset Group':<35} {'Features Capped':<18} {'Total Features':<18} {'Mean % Capped':<15} {'Max % Capped':<15}")
log("-" * 110)

for dname, group in full_summary.groupby("dataset"):
    feats_with_capping = (group["n_total_capped"] > 0).sum()
    total_feats = len(group)
    mean_pct = group["pct_capped"].mean()
    max_pct = group["pct_capped"].max()
    log(f"{dname:<35} {feats_with_capping:<18} {total_feats:<18} {mean_pct:<15.2f}% {max_pct:<15.2f}%")

# Save report
report_path = OUT_DIR / "data_capping_report.txt"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(report))

log(f"\n[DONE] All datasets successfully capped and saved to: {CAPPED}")
log(f"[REPORT] Capping log saved to: {report_path}")

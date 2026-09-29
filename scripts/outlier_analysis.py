#!/usr/bin/env python3
"""
MOIL SIH26009 — Comprehensive Outlier Detection & Analysis
===========================================================
Applies multiple outlier detection methods across ALL project datasets:

Methods:
  1. IQR (Tukey's fences) — robust, non-parametric
  2. Z-score (Modified Z-score using MAD) — robust to skew
  3. Isolation Forest — multivariate, detects complex outliers
  4. Domain-specific bounds — physical / geological constraints

Datasets:
  A. Labeled Samples (90 samples, 15 features)
  B. Region Grid Predictions (5,568 cells)
  C. Sentinel-2 + DEM Grid (5,568 cells)
  D. Monthly Ops Production (1,188 records)
  E. Production Scenario (1,452 records)
  F. Weather (17,136 daily records, 4 sites)
  G. Soil Moisture (411,264 hourly records)

Outputs:
  - Outlier summary tables & plots  →  outputs/eda_plots/
  - Full report  →  outputs/outlier_analysis_report.txt
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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ── Paths ──
BASE = Path(r"c:\Users\Debu018\Downloads\MOIL SIH26009")
RAW = BASE / "data" / "raw"
SYNTH = BASE / "data" / "synthetic"
PROC = BASE / "data" / "processed"
EXT_SAT = BASE / "data" / "external" / "satellite"
EXT_GEO = BASE / "data" / "external" / "geology"
PLOT_DIR = BASE / "outputs" / "eda_plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR = BASE / "outputs"

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150,
    "figure.figsize": (14, 8),
    "axes.titlesize": 13, "axes.labelsize": 11, "font.size": 10,
})
sns.set_theme(style="whitegrid", palette="deep")

report = []


def log(msg):
    print(msg)
    report.append(msg)


# =====================================================================
# OUTLIER DETECTION UTILITIES
# =====================================================================

def iqr_outliers(series, k=1.5):
    """IQR-based outlier detection (Tukey's fences)."""
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    mask = (series < lower) | (series > upper)
    return mask, lower, upper


def modified_zscore_outliers(series, threshold=3.5):
    """Modified Z-score using Median Absolute Deviation (robust)."""
    median = series.median()
    mad = np.median(np.abs(series - median))
    if mad == 0:
        mad = series.std() * 0.6745  # fallback
    modified_z = 0.6745 * (series - median) / mad if mad > 0 else pd.Series(0, index=series.index)
    mask = np.abs(modified_z) > threshold
    return mask, modified_z


def detect_outliers_summary(df, columns, dataset_name):
    """Run IQR + Modified Z-score on multiple columns, return summary."""
    log(f"\n{'='*90}")
    log(f"OUTLIER ANALYSIS: {dataset_name}")
    log(f"{'='*90}")
    log(f"Total records: {len(df)}")
    log(f"\n{'Feature':<30} {'N':<8} {'IQR Out':<10} {'IQR %':<8} {'MZ Out':<10} {'MZ %':<8} {'Min':<12} {'Max':<12} {'Skew':<8} {'Kurt':<8}")
    log("-" * 124)

    results = []
    for col in columns:
        s = df[col].dropna()
        if len(s) < 5:
            continue

        iqr_mask, iqr_lo, iqr_hi = iqr_outliers(s)
        mz_mask, mz_scores = modified_zscore_outliers(s)

        n_iqr = iqr_mask.sum()
        n_mz = mz_mask.sum()
        pct_iqr = n_iqr / len(s) * 100
        pct_mz = n_mz / len(s) * 100
        skew = s.skew()
        kurt = s.kurtosis()

        log(f"{col:<30} {len(s):<8} {n_iqr:<10} {pct_iqr:<8.2f} {n_mz:<10} {pct_mz:<8.2f} {s.min():<12.4f} {s.max():<12.4f} {skew:<8.3f} {kurt:<8.3f}")

        results.append({
            "feature": col, "n": len(s),
            "iqr_outliers": n_iqr, "iqr_pct": pct_iqr,
            "mz_outliers": n_mz, "mz_pct": pct_mz,
            "iqr_lower": iqr_lo, "iqr_upper": iqr_hi,
            "min": s.min(), "max": s.max(),
            "mean": s.mean(), "median": s.median(),
            "skewness": skew, "kurtosis": kurt,
        })

    return pd.DataFrame(results)


def plot_outlier_boxplots(df, columns, title, filename, ncols=4):
    """Generate box plots with outlier points highlighted."""
    nrows = (len(columns) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
    axes = np.array(axes).ravel() if nrows * ncols > 1 else [axes]

    for i, col in enumerate(columns):
        ax = axes[i]
        s = df[col].dropna()
        bp = ax.boxplot(s, vert=True, patch_artist=True,
                        boxprops=dict(facecolor="#a8dadc", alpha=0.7),
                        flierprops=dict(marker='o', markerfacecolor='#e63946',
                                       markeredgecolor='#e63946', markersize=4, alpha=0.6))

        iqr_mask, lo, hi = iqr_outliers(s)
        n_out = iqr_mask.sum()
        pct = n_out / len(s) * 100

        ax.set_title(f"{col}\n({n_out} outliers, {pct:.1f}%)", fontsize=9, fontweight="bold")
        ax.set_xticklabels([])

        # Add whisker annotations
        ax.text(0.95, 0.95, f"IQR: [{lo:.3f}, {hi:.3f}]",
                transform=ax.transAxes, fontsize=6, ha='right', va='top',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.7))

    for j in range(len(columns), len(axes)):
        axes[j].set_visible(False)

    fig.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(PLOT_DIR / filename)
    plt.close()


def plot_outlier_scatter_matrix(df, columns, label_col, title, filename):
    """2D scatter of top feature pairs with outliers colored."""
    if len(columns) < 2:
        return
    # Pick top 4 features for scatter matrix
    cols = columns[:min(4, len(columns))]
    n = len(cols)
    fig, axes = plt.subplots(n, n, figsize=(4 * n, 4 * n))

    # Compute multivariate outlier mask via Isolation Forest
    X = df[columns].dropna()
    if len(X) < 10:
        return
    iso = IsolationForest(contamination=0.05, random_state=42, n_estimators=200)
    preds = iso.fit_predict(X)
    is_outlier = preds == -1

    for i, ci in enumerate(cols):
        for j, cj in enumerate(cols):
            ax = axes[i, j] if n > 1 else axes
            if i == j:
                ax.hist(X[ci], bins=30, color="#457b9d", alpha=0.7, edgecolor="white")
                ax.hist(X.loc[is_outlier, ci], bins=30, color="#e63946", alpha=0.7, edgecolor="white")
                ax.set_ylabel(ci if j == 0 else "")
            else:
                ax.scatter(X.loc[~is_outlier, cj], X.loc[~is_outlier, ci],
                          c="#457b9d", s=5, alpha=0.3, label="Normal")
                ax.scatter(X.loc[is_outlier, cj], X.loc[is_outlier, ci],
                          c="#e63946", s=15, alpha=0.8, label="Outlier", marker="x")
            if i == n - 1:
                ax.set_xlabel(cj, fontsize=8)
            if j == 0:
                ax.set_ylabel(ci, fontsize=8)
            ax.tick_params(labelsize=6)

    fig.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(PLOT_DIR / filename)
    plt.close()

    return is_outlier


# =====================================================================
# A. LABELED SAMPLES
# =====================================================================
df_lab = pd.read_csv(RAW / "labeled_samples_dataset.csv")
lab_cols = ["B2", "B3", "B4", "B8", "B11", "B12",
            "elevation", "slope", "aspect",
            "iron_oxide_index", "swir_nir_ratio",
            "clay_alteration_idx", "ferrous_iron_idx",
            "ndvi", "dist_to_gondite_km"]

res_lab = detect_outliers_summary(df_lab, lab_cols, "A. LABELED SAMPLES (Prospectivity, n=90)")
plot_outlier_boxplots(df_lab, lab_cols, "Outlier Detection: Labeled Samples (90 points)",
                      "OL_A_labeled_boxplots.png", ncols=4)

# Isolation Forest — multivariate outliers
log("\n--- Isolation Forest (Multivariate Outlier Detection, contamination=5%) ---")
X_lab = df_lab[lab_cols].fillna(0)
iso_lab = IsolationForest(contamination=0.05, random_state=42, n_estimators=200)
df_lab["iso_outlier"] = iso_lab.fit_predict(X_lab)
n_iso = (df_lab["iso_outlier"] == -1).sum()
log(f"  Multivariate outliers detected: {n_iso} / {len(df_lab)} ({n_iso/len(df_lab)*100:.1f}%)")

# Show which samples are multivariate outliers
outlier_samples = df_lab[df_lab["iso_outlier"] == -1][["name", "label", "type"] + lab_cols[:5]]
log(f"  Outlier samples:")
log(outlier_samples.to_string(index=False))

# Domain-specific checks
log("\n--- Domain-Specific Validation ---")
log(f"  NDVI range: [{df_lab['ndvi'].min():.4f}, {df_lab['ndvi'].max():.4f}]  (Valid: [-1, 1])")
neg_ndvi = (df_lab["ndvi"] < -0.2).sum()
log(f"  Suspiciously negative NDVI (<-0.2): {neg_ndvi} samples")
log(f"  Elevation range: [{df_lab['elevation'].min():.0f}, {df_lab['elevation'].max():.0f}] m")
high_elev = (df_lab["elevation"] > 600).sum()
log(f"  Unusually high elevation (>600m): {high_elev} samples")
log(f"  Slope range: [{df_lab['slope'].min():.2f}, {df_lab['slope'].max():.2f}] degrees")
steep = (df_lab["slope"] > 20).sum()
log(f"  Very steep slopes (>20 deg): {steep} samples")

# Outlier scatter (top features)
iso_outliers_lab = plot_outlier_scatter_matrix(
    df_lab, lab_cols, "label",
    "Multivariate Outlier Detection: Labeled Samples\n(Red = Isolation Forest Outliers, 5% contamination)",
    "OL_A_labeled_scatter_outliers.png"
)

# Check if outliers are disproportionately deposits or controls
if n_iso > 0:
    ol_label_dist = df_lab[df_lab["iso_outlier"] == -1]["label"].value_counts()
    log(f"  Outlier label distribution: {ol_label_dist.to_dict()}")
    log(f"  Outlier class balance: {ol_label_dist.get(1, 0) / max(n_iso, 1) * 100:.1f}% deposits")


# =====================================================================
# B. REGION GRID PREDICTIONS
# =====================================================================
df_grid = pd.read_csv(RAW / "region_grid_predictions.csv")
grid_cols = ["B2", "B3", "B4", "B8", "B11", "B12",
             "elevation", "slope", "aspect",
             "iron_oxide_index", "swir_nir_ratio",
             "clay_alteration_idx", "ferrous_iron_idx",
             "ndvi", "dist_to_gondite_km", "deposit_probability"]

res_grid = detect_outliers_summary(df_grid, grid_cols, "B. REGION GRID PREDICTIONS (n=5,568)")
plot_outlier_boxplots(df_grid, grid_cols, "Outlier Detection: Region Grid Predictions (5,568 cells)",
                      "OL_B_grid_boxplots.png", ncols=4)

# Multivariate (Isolation Forest)
log("\n--- Isolation Forest (Grid, contamination=5%) ---")
X_grid = df_grid[grid_cols].fillna(0)
iso_grid = IsolationForest(contamination=0.05, random_state=42, n_estimators=200)
df_grid["iso_outlier"] = iso_grid.fit_predict(X_grid)
n_iso_grid = (df_grid["iso_outlier"] == -1).sum()
log(f"  Multivariate outliers: {n_iso_grid} / {len(df_grid)} ({n_iso_grid/len(df_grid)*100:.1f}%)")

# Spatial distribution of grid outliers
hot_outliers = df_grid[(df_grid["iso_outlier"] == -1) & (df_grid["deposit_probability"] > 0.5)]
log(f"  High-prob outliers (prob>0.5 + ISO outlier): {len(hot_outliers)}")

# Domain checks on grid
log("\n--- Domain-Specific Grid Checks ---")
neg_ndvi_g = (df_grid["ndvi"] < -0.3).sum()
log(f"  Very negative NDVI (<-0.3): {neg_ndvi_g} cells (may indicate water/shadow)")
extreme_prob = (df_grid["deposit_probability"] > 0.7).sum()
log(f"  Extreme deposit probability (>0.7): {extreme_prob} cells")
zero_dist = (df_grid["dist_to_gondite_km"] == 0).sum()
log(f"  Zero distance to Gondite: {zero_dist} cells (within formation)")

# ── Spatial map of outlier locations ──
fig, axes = plt.subplots(1, 2, figsize=(18, 7))
# Left: outliers on map
normal = df_grid[df_grid["iso_outlier"] == 1]
outlier = df_grid[df_grid["iso_outlier"] == -1]
axes[0].scatter(normal["lon"], normal["lat"], c="#e0e0e0", s=3, alpha=0.3, label="Normal")
axes[0].scatter(outlier["lon"], outlier["lat"], c="#e63946", s=10, alpha=0.8,
                label=f"Outlier ({n_iso_grid})")
axes[0].set_xlabel("Longitude")
axes[0].set_ylabel("Latitude")
axes[0].set_title("Spatial Location of Multivariate Outliers", fontweight="bold")
axes[0].legend()

# Right: outlier feature profile
outlier_means = df_grid[df_grid["iso_outlier"] == -1][grid_cols].mean()
normal_means = df_grid[df_grid["iso_outlier"] == 1][grid_cols].mean()
# Normalize for comparison
scaler = StandardScaler()
combined = pd.DataFrame({
    "Outlier": scaler.fit_transform(outlier_means.values.reshape(1, -1)).ravel(),
    "Normal": scaler.transform(normal_means.values.reshape(1, -1)).ravel(),
}, index=grid_cols)
combined.plot(kind="barh", ax=axes[1], color=["#e63946", "#457b9d"], alpha=0.7)
axes[1].set_title("Feature Profile: Outliers vs Normal (Z-scored)", fontweight="bold")
axes[1].set_xlabel("Standardized Mean")
axes[1].axvline(0, color="gray", linestyle="--")
plt.tight_layout()
plt.savefig(PLOT_DIR / "OL_B_grid_outlier_spatial.png")
plt.close()


# =====================================================================
# C. SENTINEL-2 + DEM GRID
# =====================================================================
df_s2 = pd.read_csv(EXT_SAT / "s2_dem_grid_samples.csv")
s2_cols = ["B2", "B3", "B4", "B8", "B11", "B12", "ndvi", "elevation", "slope", "aspect"]

res_s2 = detect_outliers_summary(df_s2, s2_cols, "C. SENTINEL-2 + DEM GRID (n=5,568)")
plot_outlier_boxplots(df_s2, s2_cols, "Outlier Detection: Sentinel-2 + DEM (5,568 cells)",
                      "OL_C_sentinel2_boxplots.png", ncols=5)

# Physical bounds checks
log("\n--- Physical Bounds Validation (Sentinel-2) ---")
for band in ["B2", "B3", "B4", "B8", "B11", "B12"]:
    neg = (df_s2[band] < 0).sum()
    high = (df_s2[band] > 1).sum()
    log(f"  {band}: negative={neg}, >1.0={high}")

log(f"  NDVI range: [{df_s2['ndvi'].min():.4f}, {df_s2['ndvi'].max():.4f}]")
neg_ndvi_s2 = (df_s2["ndvi"] < -0.3).sum()
log(f"  Very negative NDVI (<-0.3): {neg_ndvi_s2} (water/cloud/shadow artifacts)")
log(f"  Elevation: [{df_s2['elevation'].min():.0f}, {df_s2['elevation'].max():.0f}] m")
log(f"  Slope: [{df_s2['slope'].min():.4f}, {df_s2['slope'].max():.4f}] deg")


# =====================================================================
# D. MONTHLY OPS SYNTHETIC
# =====================================================================
df_ops = pd.read_csv(SYNTH / "monthly_ops_synthetic_2015_2026.csv")
df_ops["month"] = pd.to_datetime(df_ops["month"])
df_ops["shortfall_pct"] = df_ops["shortfall_tonnes"] / df_ops["planned_tonnes"] * 100
df_ops["production_efficiency"] = df_ops["actual_tonnes"] / df_ops["planned_tonnes"] * 100

ops_cols = ["planned_tonnes", "actual_tonnes", "shortfall_tonnes",
            "equipment_availability", "downtime_hours",
            "monthly_rain_mm", "heavy_rain_days",
            "shortfall_pct", "production_efficiency"]

res_ops = detect_outliers_summary(df_ops, ops_cols, "D. MONTHLY OPS SYNTHETIC (n=1,188)")
plot_outlier_boxplots(df_ops, ops_cols, "Outlier Detection: Monthly Operations (1,188 records)",
                      "OL_D_ops_boxplots.png", ncols=3)

# Mine-specific outliers
log("\n--- Mine-Specific Outlier Counts (IQR method) ---")
log(f"  {'Mine':<20} {'Prod Outliers':<15} {'Shortfall Out':<15} {'Rain Outliers':<15}")
for mine in sorted(df_ops["mine"].unique()):
    md = df_ops[df_ops["mine"] == mine]
    p_out = iqr_outliers(md["actual_tonnes"])[0].sum()
    s_out = iqr_outliers(md["shortfall_pct"])[0].sum()
    r_out = iqr_outliers(md["monthly_rain_mm"])[0].sum()
    log(f"  {mine:<20} {p_out:<15} {s_out:<15} {r_out:<15}")

# ── Check for production impossibilities ──
log("\n--- Operational Domain Checks ---")
over_prod = (df_ops["actual_tonnes"] > df_ops["planned_tonnes"]).sum()
log(f"  Production exceeding plan: {over_prod} months ({over_prod/len(df_ops)*100:.1f}%)")
zero_shortfall = (df_ops["shortfall_tonnes"] == 0).sum()
log(f"  Zero shortfall months: {zero_shortfall}")
equip_range = df_ops["equipment_availability"]
log(f"  Equipment availability: [{equip_range.min():.4f}, {equip_range.max():.4f}]")
log(f"  Equipment avail < 0.80: {(equip_range < 0.80).sum()} months")
extreme_downtime = (df_ops["downtime_hours"] > 150).sum()
log(f"  Extreme downtime (>150 hrs/month): {extreme_downtime}")


# =====================================================================
# E. PRODUCTION SCENARIO (Full dataset)
# =====================================================================
df_prod = pd.read_csv(SYNTH / "production_scenario.csv")
df_prod["month"] = pd.to_datetime(df_prod["month"])
df_prod["shortfall_pct"] = (df_prod["shortfall_tonnes"] / df_prod["planned_tonnes"] * 100).clip(lower=0)
df_prod["production_efficiency"] = df_prod["actual_tonnes"] / df_prod["planned_tonnes"] * 100

prod_cols = ["planned_tonnes", "actual_tonnes", "shortfall_tonnes",
             "equipment_availability", "monthly_rain_mm", "heavy_rain_days",
             "shortfall_pct", "production_efficiency"]

res_prod = detect_outliers_summary(df_prod, prod_cols, "E. PRODUCTION SCENARIO (n=1,452)")
plot_outlier_boxplots(df_prod, prod_cols, "Outlier Detection: Production Scenario (1,452 records)",
                      "OL_E_production_boxplots.png", ncols=4)

# Check extreme efficiency values
log("\n--- Production Efficiency Extreme Cases ---")
very_low = df_prod[df_prod["production_efficiency"] < 60]
log(f"  Efficiency < 60%: {len(very_low)} records")
if len(very_low) > 0:
    log(f"  Low-efficiency breakdown:")
    for _, r in very_low.head(10).iterrows():
        log(f"    {r['mine']:<18} {r['month'].strftime('%Y-%m')}  eff={r['production_efficiency']:.1f}%  rain={r['monthly_rain_mm']:.0f}mm  event={r.get('disruption_event', 'N/A')}")

over_100 = df_prod[df_prod["production_efficiency"] > 105]
log(f"  Efficiency > 105%: {len(over_100)} records (possible catch-up production)")


# =====================================================================
# F. WEATHER DATA
# =====================================================================
log(f"\n{'='*90}")
log("F. WEATHER DATA — Outlier Analysis (Daily, 4 Sites)")
log(f"{'='*90}")

sites = ["balaghat", "ukwa", "bhandara", "nagpur"]
weather_all = []
for site in sites:
    w = pd.read_csv(EXT_SAT / f"weather_daily_{site}_2015_2026.csv", skiprows=2)
    w.columns = ["date", "precip_mm", "temp_mean", "temp_max", "temp_min", "et0_mm", "wind_max_kmh"]
    w["date"] = pd.to_datetime(w["date"])
    w["site"] = site
    weather_all.append(w)

df_wx = pd.concat(weather_all, ignore_index=True)
wx_cols = ["precip_mm", "temp_mean", "temp_max", "temp_min", "et0_mm", "wind_max_kmh"]

res_wx = detect_outliers_summary(df_wx, wx_cols, f"F. WEATHER DATA (n={len(df_wx)}, 4 sites combined)")
plot_outlier_boxplots(df_wx, wx_cols, f"Outlier Detection: Weather Data ({len(df_wx):,} daily records)",
                      "OL_F_weather_boxplots.png", ncols=3)

# Per-site weather extremes
log("\n--- Per-Site Weather Extremes ---")
for site in sites:
    ws = df_wx[df_wx["site"] == site]
    log(f"\n  {site.upper()}:")
    log(f"    Max daily rain: {ws['precip_mm'].max():.1f} mm on {ws.loc[ws['precip_mm'].idxmax(), 'date'].strftime('%Y-%m-%d')}")
    log(f"    Max temperature: {ws['temp_max'].max():.1f} C on {ws.loc[ws['temp_max'].idxmax(), 'date'].strftime('%Y-%m-%d')}")
    log(f"    Min temperature: {ws['temp_min'].min():.1f} C on {ws.loc[ws['temp_min'].idxmin(), 'date'].strftime('%Y-%m-%d')}")
    log(f"    Rain > 100mm days: {(ws['precip_mm'] > 100).sum()}")
    log(f"    Temp > 44C days: {(ws['temp_max'] > 44).sum()}")

# ── Physical bounds checks ──
log("\n--- Weather Physical Bounds ---")
neg_precip = (df_wx["precip_mm"] < 0).sum()
log(f"  Negative precipitation: {neg_precip}")
temp_inversion = (df_wx["temp_min"] > df_wx["temp_max"]).sum()
log(f"  Temperature inversions (min > max): {temp_inversion}")
neg_et0 = (df_wx["et0_mm"] < 0).sum()
log(f"  Negative ET0: {neg_et0}")
extreme_wind = (df_wx["wind_max_kmh"] > 80).sum()
log(f"  Extreme wind (>80 km/h): {extreme_wind}")

# ── Plot: Temperature anomalies ──
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
for i, site in enumerate(sites):
    ax = axes[i // 2, i % 2]
    ws = df_wx[df_wx["site"] == site].copy()
    ws["temp_range"] = ws["temp_max"] - ws["temp_min"]
    ax.scatter(ws["date"], ws["temp_range"], c="#457b9d", s=1, alpha=0.3)
    # Highlight outliers
    iqr_m, lo, hi = iqr_outliers(ws["temp_range"])
    ax.scatter(ws.loc[iqr_m, "date"], ws.loc[iqr_m, "temp_range"],
               c="#e63946", s=5, alpha=0.8, label=f"Outliers ({iqr_m.sum()})")
    ax.axhline(hi, color="red", linestyle="--", alpha=0.5, label=f"Upper fence: {hi:.1f}")
    ax.set_title(f"{site.title()} — Diurnal Temperature Range", fontweight="bold")
    ax.set_ylabel("Temp Range (C)")
    ax.legend(fontsize=7)
fig.suptitle("Weather Outliers: Diurnal Temperature Range", fontsize=14, fontweight="bold")
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig(PLOT_DIR / "OL_F_weather_temp_range.png")
plt.close()


# =====================================================================
# G. SOIL MOISTURE
# =====================================================================
log(f"\n{'='*90}")
log("G. SOIL MOISTURE — Outlier Analysis (Hourly, 4 Sites)")
log(f"{'='*90}")

sm_summaries = []
for site in sites:
    sm = pd.read_csv(EXT_SAT / f"soilmoisture_hourly_{site}_2015_2026.csv", skiprows=2)
    sm.columns = ["datetime", "sm_0_7cm", "sm_7_28cm"]
    sm["datetime"] = pd.to_datetime(sm["datetime"])
    sm["site"] = site
    sm_summaries.append(sm)

df_sm = pd.concat(sm_summaries, ignore_index=True)
sm_cols = ["sm_0_7cm", "sm_7_28cm"]

res_sm = detect_outliers_summary(df_sm, sm_cols, f"G. SOIL MOISTURE (n={len(df_sm):,}, hourly, 4 sites)")

# Physical validation
log("\n--- Soil Moisture Physical Validation ---")
log(f"  sm_0_7cm range: [{df_sm['sm_0_7cm'].min():.4f}, {df_sm['sm_0_7cm'].max():.4f}] m3/m3")
log(f"  sm_7_28cm range: [{df_sm['sm_7_28cm'].min():.4f}, {df_sm['sm_7_28cm'].max():.4f}] m3/m3")
neg_sm = (df_sm["sm_0_7cm"] < 0).sum() + (df_sm["sm_7_28cm"] < 0).sum()
log(f"  Negative soil moisture: {neg_sm} records")
above_sat = ((df_sm["sm_0_7cm"] > 0.6).sum() + (df_sm["sm_7_28cm"] > 0.6).sum())
log(f"  Above saturation (>0.6 m3/m3): {above_sat} records")
dry_shallow = (df_sm["sm_0_7cm"] < 0.05).sum()
log(f"  Extremely dry shallow (<0.05): {dry_shallow} records ({dry_shallow/len(df_sm)*100:.2f}%)")

# Per-site IQR counts
log("\n--- Per-Site Soil Moisture Outlier Counts (IQR) ---")
for site in sites:
    ss = df_sm[df_sm["site"] == site]
    shallow_out = iqr_outliers(ss["sm_0_7cm"])[0].sum()
    deep_out = iqr_outliers(ss["sm_7_28cm"])[0].sum()
    log(f"  {site.title():<12} Shallow outliers: {shallow_out:>6} ({shallow_out/len(ss)*100:.2f}%)  "
        f"Deep outliers: {deep_out:>6} ({deep_out/len(ss)*100:.2f}%)")

# ── Plot: Soil moisture outliers ──
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
for i, site in enumerate(sites):
    ax = axes[i // 2, i % 2]
    ss = df_sm[df_sm["site"] == site].copy()
    # Daily aggregation for plotting
    daily = ss.groupby(ss["datetime"].dt.date)[["sm_0_7cm", "sm_7_28cm"]].mean().reset_index()
    daily["date"] = pd.to_datetime(daily["datetime"])

    ax.plot(daily["date"], daily["sm_0_7cm"], color="#2a9d8f", linewidth=0.5, alpha=0.6, label="Shallow")
    iqr_m, lo, hi = iqr_outliers(daily["sm_0_7cm"])
    ax.scatter(daily.loc[iqr_m, "date"], daily.loc[iqr_m, "sm_0_7cm"],
               c="#e63946", s=5, alpha=0.7, label=f"Outliers ({iqr_m.sum()})", zorder=5)
    ax.axhline(lo, color="red", linestyle=":", alpha=0.4)
    ax.axhline(hi, color="red", linestyle=":", alpha=0.4)
    ax.set_title(f"{site.title()} — Shallow Soil Moisture (Daily Mean)", fontweight="bold", fontsize=10)
    ax.set_ylabel("m3/m3")
    ax.legend(fontsize=7)
fig.suptitle("Soil Moisture Outlier Detection", fontsize=14, fontweight="bold")
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig(PLOT_DIR / "OL_G_soil_moisture_outliers.png")
plt.close()


# =====================================================================
# H. CROSS-DATASET OUTLIER SUMMARY
# =====================================================================
log(f"\n{'='*90}")
log("H. CROSS-DATASET OUTLIER SUMMARY")
log(f"{'='*90}")

all_results = {
    "A. Labeled Samples": res_lab,
    "B. Grid Predictions": res_grid,
    "C. Sentinel-2 DEM": res_s2,
    "D. Monthly Ops": res_ops,
    "E. Production Scenario": res_prod,
    "F. Weather": res_wx,
    "G. Soil Moisture": res_sm,
}

log(f"\n{'Dataset':<25} {'Features':<10} {'Total Recs':<12} {'Mean IQR%':<12} {'Mean MZ%':<12} {'Max IQR%':<12} {'Worst Feature':<30}")
log("-" * 115)
for name, res_df in all_results.items():
    if len(res_df) == 0:
        continue
    worst_idx = res_df["iqr_pct"].idxmax()
    worst_feat = res_df.loc[worst_idx, "feature"]
    worst_pct = res_df.loc[worst_idx, "iqr_pct"]
    log(f"{name:<25} {len(res_df):<10} {res_df['n'].iloc[0]:<12} "
        f"{res_df['iqr_pct'].mean():<12.2f} {res_df['mz_pct'].mean():<12.2f} "
        f"{worst_pct:<12.2f} {worst_feat:<30}")

# ── Skewness analysis across all datasets ──
log("\n--- Features with High Skewness (|skew| > 2) — Candidates for Transformation ---")
for name, res_df in all_results.items():
    skewed = res_df[res_df["skewness"].abs() > 2]
    if len(skewed) > 0:
        for _, r in skewed.iterrows():
            log(f"  [{name}] {r['feature']:<30} skew={r['skewness']:>8.3f}  kurtosis={r['kurtosis']:>8.3f}")

# ── High-kurtosis (leptokurtic, heavy-tailed) ──
log("\n--- Features with High Kurtosis (kurt > 7) — Heavy-Tailed Distributions ---")
for name, res_df in all_results.items():
    heavy = res_df[res_df["kurtosis"] > 7]
    if len(heavy) > 0:
        for _, r in heavy.iterrows():
            log(f"  [{name}] {r['feature']:<30} kurtosis={r['kurtosis']:>8.3f}  IQR outlier%={r['iqr_pct']:>6.2f}")


# ── Comprehensive recommendation ──
log(f"\n{'='*90}")
log("OUTLIER HANDLING RECOMMENDATIONS")
log(f"{'='*90}")
log("""
  1. LABELED SAMPLES (n=90):
     - Small sample size makes outlier removal risky
     - Recommend: Flag but RETAIN outliers; use robust methods (RF, XGB)
     - Key concern: Very steep slopes and extreme elevation values

  2. REGION GRID / SENTINEL-2 (n=5,568):
     - ~5% multivariate outliers detected via Isolation Forest
     - Highly negative NDVI values likely represent water bodies/shadows
     - Recommend: Cap extreme spectral values; keep spatial outliers for
       anomaly detection (they may indicate mineral signatures)

  3. OPERATIONS DATA:
     - Production overshoots (>100% efficiency) are operationally valid
       (catch-up production after delays)
     - High-rainfall months are real operational risks, not data errors
     - Recommend: Winsorize extreme shortfall values for modeling;
       retain raw values for risk analysis

  4. WEATHER DATA:
     - No physical impossibilities detected (no negative rain, no inversions)
     - Extreme rainfall events (>100mm/day) are real monsoon events
     - Recommend: No outlier treatment needed; these are genuine extremes

  5. SOIL MOISTURE:
     - Values within physical bounds (0 to ~0.55 m3/m3)
     - Outliers mostly represent genuine seasonal extremes
     - Recommend: Retain all values; consider temporal smoothing
       for modeling
""")


# ── Write report ──
report_path = OUT_DIR / "outlier_analysis_report.txt"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(report))
log(f"\nFull report saved to: {report_path}")

# List generated plots
log("\n--- Generated Outlier Plots ---")
for p in sorted(PLOT_DIR.glob("OL_*.png")):
    log(f"  [PLOT] {p.relative_to(BASE)}")

print("\n[DONE] Comprehensive Outlier Analysis complete!")

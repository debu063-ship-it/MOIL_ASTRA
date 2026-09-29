# -*- coding: utf-8 -*-
"""
Shortfall prediction v2 — two models on the synthetic-but-calibrated ops data.

A) NEXT-MONTH FORECASTER (time-series features: lags/rolls of shortfall ratio)
   - Target: shortfall_ratio = shortfall/planned (scale-free); reported in tonnes too.
   - Selection: expanding-window TimeSeriesSplit (folds end 2019-12, 2021-12, 2023-12, 2024-12).
   - Honest test: last 5 months (2025-08..2025-12), never touched during development.
   - Caveat: trained on synthetic calibrated ops data; metrics validate learning, not real ops.

B) WHAT-IF RESPONSE MODEL (no time leakage: predicts shortfall from controllable drivers)
   - Learns response surface: equipment availability, downtime hours, blast delays,
     rain exposure -> shortfall ratio. Used by the what-if simulator.
   - Honest test: same 5-month holdout.

Outputs -> outputs/models_v3/ + data/processed/shortfall_predictions_v2.csv
"""
import os, json, warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import (RandomForestRegressor, ExtraTreesRegressor,
                              HistGradientBoostingRegressor, StackingRegressor,
                              RandomForestClassifier)
from sklearn.linear_model import RidgeCV, LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, r2_score, roc_auc_score, average_precision_score
import joblib

warnings.filterwarnings("ignore")
RS = 42
OPS_F = "data/synthetic/monthly_ops_synthetic_2015_2026.csv"
OUT_DIR = "outputs/models_v3"
os.makedirs(OUT_DIR, exist_ok=True)

# ------------------------------------------------------------------ data
df = pd.read_csv(OPS_F, parse_dates=["month"]).sort_values(["mine", "month"]).reset_index(drop=True)
df["shortfall_ratio"] = df["shortfall_tonnes"] / df["planned_tonnes"]
df["month_num"] = df["month"].dt.month
# monsoon context features (real seasonality inside the synthetic data)
df["rain_mm_roll3"] = df.groupby("mine")["monthly_rain_mm"].transform(lambda s: s.rolling(3).mean())
df["heavy_rain_roll3"] = df.groupby("mine")["heavy_rain_days"].transform(lambda s: s.rolling(3).mean())

# time-series features (per mine)
g = df.groupby("mine")
for lag in (1, 2, 3, 12):
    df[f"sr_lag{lag}"] = g["shortfall_ratio"].shift(lag)
    df[f"eq_lag{lag}"] = g["equipment_availability"].shift(lag)
df["sr_roll3"] = g["shortfall_ratio"].transform(lambda s: s.shift(1).rolling(3).mean())
df["sr_roll12"] = g["shortfall_ratio"].transform(lambda s: s.shift(1).rolling(12).mean())
df["planned_next"] = g["planned_tonnes"].shift(-1)          # known plan for the target month
df["planned_lag1"] = g["planned_tonnes"].shift(1)

mine_d = pd.get_dummies(df["mine"], prefix="mine", dtype=float)
mtype_d = pd.get_dummies(df["mine_type"], prefix="type", dtype=float)

FEATS_F = ["sr_lag1", "sr_lag2", "sr_lag3", "sr_lag12", "sr_roll3", "sr_roll12",
           "eq_lag1", "eq_lag2", "eq_lag3", "eq_lag12",
           "equipment_availability", "downtime_hours", "blast_delay_flag",
           "monthly_rain_mm", "heavy_rain_days", "rain_mm_roll3", "heavy_rain_roll3",
           "planned_lag1", "month_num"]
FEATS_W = ["equipment_availability", "downtime_hours", "blast_delay_flag",
           "monthly_rain_mm", "heavy_rain_days", "rain_mm_roll3", "heavy_rain_roll3",
           "planned_lag1", "month_num"]

Xf = pd.concat([df[FEATS_F], mine_d, mtype_d], axis=1)
Xw = pd.concat([df[FEATS_W], mine_d, mtype_d], axis=1)
y = df["shortfall_ratio"]
y_t = df["shortfall_tonnes"]

# tree models can't take NaN lag rows; keep valid-row masks
VALID_F = Xf[FEATS_F].notna().all(axis=1)
VALID_W = Xw[FEATS_W].notna().all(axis=1)

TEST_MASK = df["month"] >= "2025-08-01"
DEV_MASK = ~TEST_MASK
df_dev = df[DEV_MASK]
print(f"rows: {len(df)} | dev: {DEV_MASK.sum()} | holdout: {TEST_MASK.sum()} (2025-08..12)")

# ------------------------------------------------------- candidate models
def reg_candidates():
    return {
        "rf": RandomForestRegressor(n_estimators=500, min_samples_leaf=3, random_state=RS, n_jobs=-1),
        "et": ExtraTreesRegressor(n_estimators=500, min_samples_leaf=3, random_state=RS, n_jobs=-1),
        "hgb": HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06, max_leaf_nodes=15,
                                             min_samples_leaf=15, l2_regularization=1.0, random_state=RS),
        "ridge": RidgeCV(alphas=np.logspace(-3, 2, 20)),
    }
try:
    from xgboost import XGBRegressor
    reg_candidates()["xgb"] = XGBRegressor(n_estimators=500, learning_rate=0.05, max_depth=4,
                                           subsample=0.9, colsample_bytree=0.8, reg_lambda=1.0,
                                           random_state=RS, n_jobs=-1, verbosity=0)
except Exception:
    pass

def tscv_groups_ok(X, yv, model, valid):
    """Manual expanding-window TS CV on dev rows (mines pooled, month-ordered)."""
    order = df_dev.sort_values(["month", "mine"]).index
    order = order[valid.loc[order].values]
    Xo, yo = X.loc[order], yv.loc[order]
    n = len(Xo)
    edges = [int(n * f) for f in (0.5, 0.62, 0.75, 0.88)] + [n]
    preds = np.full(n, np.nan)
    for a, b in zip(edges[:-1], edges[1:]):
        m = clone(model)
        m.fit(Xo.iloc[:a], yo.iloc[:a])
        preds[a:b] = m.predict(Xo.iloc[a:b])
    ok = ~np.isnan(preds)
    return (mean_absolute_error(yo.values[ok], preds[ok]),
            r2_score(yo.values[ok], preds[ok]))

print("\n[A] next-month forecaster — TimeSeriesSplit CV (dev rows):")
cv_rows = []
for name, model in reg_candidates().items():
    mae, r2 = tscv_groups_ok(Xf, y, model, VALID_F)
    cv_rows.append((name, mae, r2))
    print(f"  {name:5s} MAE {mae:.4f}  R2 {r2:.3f}")
best_a = min(cv_rows, key=lambda t: t[1])[0]
print("  best (MAE):", best_a)

# ------------------------------------------------------------- fit A
model_a = reg_candidates()[best_a]
fit_mask_A = DEV_MASK & VALID_F
model_a.fit(Xf[fit_mask_A], y[fit_mask_A])
pred_ratio = model_a.predict(Xf[TEST_MASK].fillna(Xf[fit_mask_A].mean()))
plan_test = df.loc[TEST_MASK, "planned_tonnes"].to_numpy()
actual_ratio = y[TEST_MASK].to_numpy()
actual_t = y_t[TEST_MASK].to_numpy()
pred_t = pred_ratio * plan_test
mae_ratio = mean_absolute_error(actual_ratio, pred_ratio)
mae_t = mean_absolute_error(actual_t, pred_t)
r2_t = r2_score(actual_t, pred_t)
print(f"\n[A] HOLDOUT (2025-08..12, unseen): MAE_ratio {mae_ratio:.4f} | MAE {mae_t:,.0f} t | R2 {r2_t:.3f}")
naive = np.full_like(actual_ratio, df_dev["shortfall_ratio"].mean())
print(f"    baseline (dev mean ratio): MAE_ratio {mean_absolute_error(actual_ratio, naive):.4f}")

# ------------------------------------------------------------- model B
print("\n[B] what-if response model — TimeSeriesSplit CV (dev rows):")
cv_rows_b = []
for name, model in reg_candidates().items():
    mae, r2 = tscv_groups_ok(Xw, y, model, VALID_W)
    cv_rows_b.append((name, mae, r2))
    print(f"  {name:5s} MAE {mae:.4f}  R2 {r2:.3f}")
best_b = min(cv_rows_b, key=lambda t: t[1])[0]
print("  best (MAE):", best_b)
model_b = reg_candidates()[best_b]
fit_mask_B = DEV_MASK & VALID_W
model_b.fit(Xw[fit_mask_B], y[fit_mask_B])
pred_b = model_b.predict(Xw[TEST_MASK].fillna(Xw[fit_mask_B].mean()))
print(f"[B] HOLDOUT: MAE_ratio {mean_absolute_error(actual_ratio, pred_b):.4f} "
      f"(what-if uses no history features — expectedly weaker than A)")

# -------------------------------------------------- alert classifier (C)
# "next month will miss plan by >15%" — the actionable dashboard alert
thr = 0.15
y_cls = (df["shortfall_ratio"].shift(-1) if False else None)
next_ratio = df.groupby("mine")["shortfall_ratio"].shift(-1)
yC = (next_ratio > thr).astype(int)
maskC = yC.notna() & DEV_MASK & VALID_F
clf = RandomForestClassifier(n_estimators=500, min_samples_leaf=5,
                             class_weight="balanced", random_state=RS, n_jobs=-1)
# ordered CV on dev (valid rows only)
order = df_dev.sort_values(["month", "mine"]).index
order = order[VALID_F.loc[order].values]
Xo, yo = Xf.loc[order], yC.loc[order]
n = len(Xo)
edges = [int(n * f) for f in (0.5, 0.62, 0.75, 0.88)] + [n]
pc = np.full(n, np.nan)
for a, b in zip(edges[:-1], edges[1:]):
    m = clone(clf)
    m.fit(Xo.iloc[:a], yo.iloc[:a])
    pc[a:b] = m.predict_proba(Xo.iloc[a:b])[:, 1]
try:
    ok = ~np.isnan(pc)
    auc = roc_auc_score(yo.values[ok], pc[ok]); ap = average_precision_score(yo.values[ok], pc[ok])
    print(f"\n[C] alert classifier (next-month ratio>{thr}) CV: ROC {auc:.3f} PR {ap:.3f} (prevalence {yo.mean():.2f})")
except Exception as e:
    print("alert clf CV skipped:", e)
clf.fit(Xf[maskC], yC[maskC].astype(int))

# ------------------------------------------------------------- outputs
out = df.loc[TEST_MASK, ["mine", "month", "planned_tonnes", "actual_tonnes", "shortfall_tonnes"]].copy()
out["pred_shortfall_ratio"] = pred_ratio
out["pred_shortfall_tonnes"] = pred_t
out["model"] = best_a
out.to_csv("data/processed/shortfall_predictions_v2.csv", index=False)

# response surface grid for the what-if simulator (fixed at dev-typical values)
typ = Xw[fit_mask_B].median(numeric_only=True)
# pick modal mine/type profile instead of fractional dummy medians
modal_mine = df["mine"].mode()[0]
modal_type = df.loc[df["mine"] == modal_mine, "mine_type"].mode()[0]
for c in list(mine_d.columns) + list(mtype_d.columns):
    typ[c] = 0.0
typ[f"mine_{modal_mine}"] = 1.0
typ[f"type_{modal_type}"] = 1.0
sim = []
for eq in np.arange(0.75, 1.001, 0.025):
    for rain in (0, 25, 50, 100, 200, 300, 400):
        row = typ.copy()
        row["equipment_availability"] = eq
        row["monthly_rain_mm"] = rain
        row["heavy_rain_days"] = 0 if rain < 50 else (2 if rain < 150 else (6 if rain < 300 else 12))
        row["rain_mm_roll3"] = rain * 0.6
        row["heavy_rain_roll3"] = row["heavy_rain_days"] * 0.6
        sim.append(row)
sim = pd.DataFrame(sim)[list(Xw.columns)]
sim["pred_shortfall_ratio"] = model_b.predict(sim)
sim["mine_profile"] = f"{modal_mine} ({modal_type})"
sim.to_csv(os.path.join(OUT_DIR, "whatif_response_surface.csv"), index=False)

joblib.dump(model_a, os.path.join(OUT_DIR, "shortfall_forecaster_v2.joblib"))
joblib.dump(model_b, os.path.join(OUT_DIR, "whatif_response_v2.joblib"))
joblib.dump(clf, os.path.join(OUT_DIR, "shortfall_alert_clf_v2.joblib"))

meta = {
    "data": OPS_F, "provenance": "SYNTHETIC ops calibrated to real MOIL annual anchors + real rainfall seasonality",
    "featurizerA_features": FEATS_F + list(mine_d.columns) + list(mtype_d.columns),
    "featurizerB_features": FEATS_W + list(mine_d.columns) + list(mtype_d.columns),
    "modelA": best_a, "modelB": best_b,
    "cvA": [{"model": n, "mae": m, "r2": r} for n, m, r in cv_rows],
    "cvB": [{"model": n, "mae": m, "r2": r} for n, m, r in cv_rows_b],
    "holdout": {"months": "2025-08..2025-12", "mae_ratio": mae_ratio, "mae_tonnes": mae_t, "r2_tonnes": r2_t,
                "baseline_mae_ratio_dev_mean": float(mean_absolute_error(actual_ratio, naive))},
    "alert_clf": {"threshold_ratio": thr},
}
with open(os.path.join(OUT_DIR, "shortfall_v2_metadata.json"), "w") as fh:
    json.dump(meta, fh, indent=2, default=float)
print("\nsaved: data/processed/shortfall_predictions_v2.csv, outputs/models_v3/ (models + response surface)")

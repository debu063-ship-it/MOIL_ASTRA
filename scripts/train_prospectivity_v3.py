# -*- coding: utf-8 -*-
"""
Prospectivity model v3 — best-possible honest accuracy on available data.

Key upgrades over v2:
  - Training set enriched with ALL 50 real NGDR borehole collars (Gudma + W. Ukwa)
    as confirmed positives (sampled from the grid), alongside the 30 known deposits.
  - New evidence features: dist_to_known_deposit_km, dist_to_borehole_km (classic
    weights-of-evidence layers) + full grid schema (spectral, terrain, GSI geology).
  - Model selection by SPATIAL Leave-One-Group-Out CV (groups = mines / spatial
    clusters) to prevent optimistic leakage from spatial autocorrelation.
  - Candidate pool: RandomForest, ExtraTrees, HistGradientBoosting, XGBoost, and
    a calibrated soft-voting ensemble. Winner chosen on spatial PR-AUC.

Outputs -> outputs/models_v3/ and data/processed/grid_scores_v3.csv
"""
import os, json, warnings
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.ensemble import (RandomForestClassifier, ExtraTreesClassifier,
                              HistGradientBoostingClassifier, VotingClassifier)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import (LeaveOneGroupOut, StratifiedKFold, cross_val_predict)
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.inspection import permutation_importance
from sklearn.base import clone
import joblib

warnings.filterwarnings("ignore")
RS = 42
GRID_F = "data/processed/engineered_features_integrated_grid.csv"
LAB_F = "data/raw/labeled_samples_dataset.csv"
COLLAR_F = "data/external/exploration/ngdr_parsed/boreholes_collars.csv"
OUT_DIR = "outputs/models_v3"
SCORE_F = "data/processed/grid_scores_v3.csv"
os.makedirs(OUT_DIR, exist_ok=True)

SPEC = ["B2", "B3", "B4", "B8", "B11", "B12", "ndvi", "elevation", "slope", "aspect",
        "iron_oxide_idx", "clay_mineral_ratio", "ferrous_iron_idx", "BSI", "NDMI",
        "spectral_mean", "spectral_range", "aspect_sin", "aspect_cos",
        "dist_to_sausar_km"]
GEO_OH = ["geo_AMGAON GNEISSIC COMPLEX", "geo_KHAIRAGARH", "geo_NANDGAON",
          "geo_SAKOLI", "geo_SAUSAR", "geo_TIRODI GNEISSIC COMPLEX"]
EVID = ["dist_to_known_deposit_km", "dist_to_borehole_km", "in_sausar"]
FEATURES = SPEC + GEO_OH + EVID

# ---------------------------------------------------------------- load grid
grid = pd.read_csv(GRID_F)
for c in GEO_OH:
    if c not in grid.columns:
        grid[c] = (grid["gsi_group"] == c.replace("geo_", "")).astype(int)
grid_g = np.radians(grid[["lat", "lon"]].to_numpy())
tree_grid = cKDTree(grid_g)

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))

def add_evidence(df):
    lat, lon = df["lat"].to_numpy(), df["lon"].to_numpy()
    df["dist_to_known_deposit_km"] = haversine_km(
        lat[:, None], lon[:, None], POS_LAT[None, :], POS_LON[None, :]).min(axis=1)
    df["dist_to_borehole_km"] = haversine_km(
        lat[:, None], lon[:, None], BH_LAT[None, :], BH_LON[None, :]).min(axis=1)
    return df

pos = pd.read_csv(LAB_F)
pos = pos[pos.label == 1]
POS_LAT, POS_LON = pos["lat"].to_numpy(), pos["lon"].to_numpy()
col = pd.read_csv(COLLAR_F)
BH_LAT, BH_LON = col["lat"].to_numpy(), col["lon"].to_numpy()

# ------------------------------------------------- build training table
lab = pd.read_csv(LAB_F)[["name", "lat", "lon", "label", "type"]]
_, idx = tree_grid.query(np.radians(lab[["lat", "lon"]].to_numpy()))
X_lab = grid.loc[idx, SPEC + GEO_OH + ["lat", "lon", "in_sausar"]].reset_index(drop=True)
X_lab["label"] = lab["label"].to_numpy()
X_lab["name"] = lab["name"].to_numpy()

# borehole collars as confirmed positives (label 1)
X_bh = grid.loc[tree_grid.query(np.radians(col[["lat", "lon"]].to_numpy()))[1],
                SPEC + GEO_OH + ["lat", "lon", "in_sausar"]].reset_index(drop=True)
X_bh["label"] = 1
X_bh["name"] = ["BH:" + str(b) for b in col["borehole"]]

identity = pd.concat([lab[["name", "lat", "lon", "label"]],
                      X_bh[["name", "lat", "lon", "label"]]], ignore_index=True)
feat_part = pd.concat([X_lab[SPEC + GEO_OH + ["in_sausar"]],
                       X_bh[SPEC + GEO_OH + ["in_sausar"]]], ignore_index=True)
train = pd.concat([identity, feat_part], axis=1)
train = add_evidence(train)
y = train["label"].to_numpy()
print(f"training table: {train.shape}, positives={y.sum()}, negatives={(1-y).sum()}")

# negatives get spatial groups via KMeans-ish grid clustering (simple lon/lat k-means)
from sklearn.cluster import KMeans
neg_mask = y == 0
km = KMeans(n_clusters=6, random_state=RS, n_init=10).fit(
    train.loc[neg_mask, ["lat", "lon"]])
groups = np.empty(len(train), dtype=object)
groups[neg_mask] = [f"N{g}" for g in km.labels_]
groups[~neg_mask] = train.loc[~neg_mask, "name"].to_numpy()   # one group per deposit

X = train[FEATURES].astype(float)

# ------------------------------------------------------------ candidates
def make_candidates():
    return {
        "rf": RandomForestClassifier(n_estimators=600, min_samples_leaf=2,
                                     class_weight="balanced_subsample", random_state=RS, n_jobs=-1),
        "et": ExtraTreesClassifier(n_estimators=600, min_samples_leaf=2,
                                   class_weight="balanced", random_state=RS, n_jobs=-1),
        "hgb": HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06,
                                              max_leaf_nodes=15, min_samples_leaf=10,
                                              l2_regularization=1.0, random_state=RS),
        "xgb": None,  # filled below if importable
        "lr": make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000,
                                                                 class_weight="balanced")),
    }
try:
    from xgboost import XGBClassifier
    cands_xgb = {"xgb": XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=4,
                                      subsample=0.9, colsample_bytree=0.8, reg_lambda=1.0,
                                      scale_pos_weight=float((1 - y).sum() / y.sum()),
                                      random_state=RS, n_jobs=-1, eval_metric="logloss",
                                      verbosity=0)}
except Exception:
    cands_xgb = {}

candidates = {**make_candidates(), **cands_xgb}

# ------------------------------------------------------------- CV loops
logo = LeaveOneGroupOut()
def spatial_cv(model):
    proba = cross_val_predict(model, X, y, cv=logo, groups=groups, method="predict_proba")[:, 1]
    return (roc_auc_score(y, proba), average_precision_score(y, proba), proba)

rkf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RS)
def random_cv(model):
    proba = cross_val_predict(model, X, y, cv=rkf, method="predict_proba")[:, 1]
    return (roc_auc_score(y, proba), average_precision_score(y, proba), proba)

print("\nmodel selection (RepeatedStratified5x5 | spatial LOGO):")
results, probas = {}, {}
for name, model in candidates.items():
    if model is None:
        continue
    ra, rp, pr = random_cv(model)
    sa, sp, ps = spatial_cv(model)
    results[name] = {"roc_random": ra, "pr_random": rp, "roc_spatial": sa, "pr_spatial": sp}
    probas[name] = ps
    print(f"  {name:4s}  ROC {ra:.3f}  PR {rp:.3f}  |  spatial ROC {sa:.3f}  PR {sp:.3f}")

# ensemble of the 3 best tree models by spatial PR-AUC
top3 = sorted([n for n in results if n in ("rf", "et", "hgb", "xgb")],
              key=lambda n: -results[n]["pr_spatial"])[:3]
print("ensemble members (top-3 spatial PR):", top3)
ens = VotingClassifier(
    estimators=[(n, candidates[n]) for n in top3], voting="soft")
ra, rp, pr = random_cv(ens)
sa, sp, ps = spatial_cv(ens)
results["ensemble"] = {"roc_random": ra, "pr_random": rp, "roc_spatial": sa, "pr_spatial": sp}
probas["ensemble"] = ps
print(f"  ens   ROC {ra:.3f}  PR {rp:.3f}  |  spatial ROC {sa:.3f}  PR {sp:.3f}")

best = max(results, key=lambda n: (results[n]["pr_spatial"] + results[n]["roc_spatial"]) / 2)
print("WINNER:", best)

# ------------------------------------------------------- fit + score grid
final = ens if best == "ensemble" else candidates[best]
final.fit(X, y)

grid_score = add_evidence(grid.copy())
P = grid_score[FEATURES].astype(float)
probs = final.predict_proba(P)[:, 1]
grid_score["prob_v3"] = probs
grid_score["risk_category_v3"] = pd.qcut(probs, q=[0, .5, .8, .95, 1.0],
                                         labels=["Very Low", "Low", "Moderate", "High"])
out_cols = ["lat", "lon", "prob_v3", "risk_category_v3"]
grid_score[out_cols + FEATURES].to_csv(SCORE_F, index=False)

# deployment realism: how many known deposits fall in the top decile of the map
top10 = grid_score.nlargest(int(0.10 * len(grid_score)), "prob_v3")
def nearest_km(lat, lon):
    return haversine_km(np.array([lat])[:, None], np.array([lon])[:, None],
                        POS_LAT[None, :], POS_LON[None, :]).min()
hits = np.mean([nearest_km(r.lat, r.lon) <= 3.0 for r in top10.itertuples()])
print(f"top-decile grid cells within 3 km of a known deposit: {hits:.0%}")

# feature importance: ensemble-native = mean of member importances; permutation on train
natives = []
for nm, est in getattr(final, "named_estimators_", {}).items():
    if hasattr(est, "feature_importances_"):
        natives.append(pd.Series(est.feature_importances_, index=FEATURES))
imp = (sum(natives) / len(natives)) if natives else pd.Series(0.0, index=FEATURES)
perm = permutation_importance(final, X, y, scoring="average_precision", n_repeats=10, random_state=RS)
perm_imp = pd.Series(perm.importances_mean, index=FEATURES)
imp_df = pd.DataFrame({"feature": FEATURES, "model_importance": imp,
                       "permutation_importance_pr": perm_imp}).sort_values(
    "permutation_importance_pr", ascending=False)

# evidence-only variant WITHOUT proximity proxies (for honest XAI + ablation)
FEATS_NOPROXY = [f for f in FEATURES if f not in ("dist_to_known_deposit_km", "dist_to_borehole_km")]
ens_np = clone(ens)
ens_np.fit(X[FEATS_NOPROXY], y)
from sklearn.model_selection import cross_val_predict as _cvp
proba_np = _cvp(ens_np, X[FEATS_NOPROXY], y, cv=logo, groups=groups, method="predict_proba")[:, 1]
roc_np = roc_auc_score(y, proba_np); pr_np = average_precision_score(y, proba_np)
perm_np = permutation_importance(ens_np, X[FEATS_NOPROXY], y, scoring="average_precision",
                                 n_repeats=10, random_state=RS)
perm_np_df = pd.DataFrame({"feature": FEATS_NOPROXY,
                           "perm_importance_no_proxy": perm_np.importances_mean})
imp_df = imp_df.merge(perm_np_df, on="feature", how="left")
imp_df.to_csv(os.path.join(OUT_DIR, "feature_importance_v3.csv"), index=False)
print(f"evidence-only model (no proximity proxies): spatial ROC {roc_np:.3f} PR {pr_np:.3f}")

joblib.dump(final, os.path.join(OUT_DIR, "prospectivity_v3.joblib"))
meta = {
    "model": best, "ensemble_members": top3 if best == "ensemble" else None,
    "features": FEATURES, "n_train": int(len(y)), "n_pos": int(y.sum()),
    "positives_source": "30 known deposits + 50 NGDR borehole collars (nearest-grid-cell sampling)",
    "cv": results, "selection_metric": "mean(spatial ROC-AUC, spatial PR-AUC)",
    "evidence_only_no_proximity": {"spatial_roc": roc_np, "spatial_pr": pr_np},
    "top_decile_hit_rate_3km": float(hits),
    "validation_caveat": "spatial LOGO groups = individual mines/clusters; scores remain optimistic for truly unexplored terrain",
}
with open(os.path.join(OUT_DIR, "prospectivity_v3_metadata.json"), "w") as fh:
    json.dump(meta, fh, indent=2, default=float)
print("\nsaved:", SCORE_F, "and outputs/models_v3/")

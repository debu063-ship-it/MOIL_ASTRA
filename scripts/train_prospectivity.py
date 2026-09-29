"""
Phase 1 - Manganese prospectivity model (MOIL belt, Sausar Group).

Inputs:
  data/raw/training_labels.geojson     (120 positives on corrected mine pts, 240 negatives)
  data/raw/labeled_samples_dataset.csv (90 labeled samples w/ spectral+terrain features)
  data/raw/region_grid_predictions.csv (5,568-cell prediction grid features)

Method:
  - Common feature schema across train + grid: B2,B3,B4,B8,B11,B12, elevation, slope,
    aspect, iron_oxide_index, swir_nir_ratio, ndvi, in_gondite_formation, dist_to_gondite_km.
  - Spatial-block CV: 0.1-degree blocks as folds (prevents spatial leakage).
  - Models: RandomForest + XGBoost, class-balanced.
  - Outputs: cleaned grid scores + comparison with the old predictions.
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, average_precision_score

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

RAW = Path("data/raw")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

FEATURES = [
    "B2", "B3", "B4", "B8", "B11", "B12",
    "elevation", "slope", "aspect",
    "iron_oxide_index", "swir_nir_ratio",
    "ndvi", "in_gondite_formation", "dist_to_gondite_km",
]

def load_training():
    gj = json.loads((RAW / "training_labels.geojson").read_text(encoding="utf-8"))
    rows = []
    for f in gj["features"]:
        p = f["properties"]
        rows.append({"lat": p["lat"], "lon": p["lon"], "label": p["label"]})
    labels = pd.DataFrame(rows)

    # Join features from the labeled_samples dataset where names/coords match,
    # otherwise sample features from the grid as background for every label point.
    grid = pd.read_csv(RAW / "region_grid_predictions.csv")
    grid = grid.rename(columns={"lat": "lat", "lon": "lon"})

    # Build the full feature space from the grid (it has all FEATURES columns).
    # For each labeled point, take features from the NEAREST grid cell.
    glat = grid[["lat", "lon"]].to_numpy()
    from scipy.spatial import cKDTree  # may not exist; fallback below
    tree = cKDTree(glat)
    dist, idx = tree.query(labels[["lat", "lon"]].to_numpy(), k=1)
    train = grid.iloc[idx].reset_index(drop=True).copy()
    train["label"] = labels["label"].to_numpy()
    train["match_km"] = dist * 111.32
    return train, grid

def load_training_fallback():
    # scipy-free fallback: exact-cell merge on rounded coords
    grid = pd.read_csv(RAW / "region_grid_predictions.csv")
    labels = []
    gj = json.loads((RAW / "training_labels.geojson").read_text(encoding="utf-8"))
    for f in gj["features"]:
        p = f["properties"]
        labels.append({"lat": p["lat"], "lon": p["lon"], "label": p["label"]})
    labels = pd.DataFrame(labels)
    grid["lat_r"] = grid["lat"].round(3)
    grid["lon_r"] = grid["lon"].round(3)
    labels["lat_r"] = labels["lat"].round(3)
    labels["lon_r"] = labels["lon"].round(3)
    merged = labels.merge(
        grid.drop(columns=["lat", "lon"]), on=["lat_r", "lon_r"], how="left"
    )
    return merged, grid

def spatial_blocks(df, size=0.1):
    return (df["lat"] // size).astype(int).astype(str) + "_" + (df["lon"] // size).astype(int).astype(str)

def main():
    try:
        from scipy.spatial import cKDTree
        train, grid = load_training()
    except ImportError:
        train, grid = load_training_fallback()

    print(f"Training rows: {len(train)} (pos={int((train.label==1).sum())}, neg={int((train.label==0).sum())})")
    print(f"Grid rows: {len(grid)}")

    train = train.dropna(subset=[c for c in FEATURES if c in train.columns])
    X = train[FEATURES].to_numpy()
    y = train["label"].to_numpy()
    blocks = spatial_blocks(train)

    models = {
        "rf": RandomForestClassifier(
            n_estimators=500, min_samples_leaf=2, class_weight="balanced",
            random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "xgb": XGBClassifier(
            n_estimators=400, max_depth=4, learning_rate=0.05,
            scale_pos_weight=float((y == 0).sum() / max((y == 1).sum(), 1)),
            random_state=RANDOM_STATE, n_jobs=-1, eval_metric="logloss",
        ),
    }

    results = {}
    for name, model in models.items():
        aucs, aps = [], []
        gkf = GroupKFold(n_splits=5)
        for tr, te in gkf.split(X, y, groups=blocks):
            m = model.__class__(**model.get_params())
            m.fit(X[tr], y[tr])
            p = m.predict_proba(X[te])[:, 1]
            if len(np.unique(y[te])) > 1:
                aucs.append(roc_auc_score(y[te], p))
                aps.append(average_precision_score(y[te], p))
        results[name] = {"auc_mean": float(np.mean(aucs)), "auc_std": float(np.std(aucs)),
                         "ap_mean": float(np.mean(aps))}
        print(f"{name}: spatial-CV AUC={np.mean(aucs):.3f}±{np.std(aucs):.3f}, AP={np.mean(aps):.3f}")

    # Fit final models on all data and score the grid
    scored = grid.copy()
    for name, model in models.items():
        model.fit(X, y)
        scored[f"prob_{name}"] = model.predict_proba(grid[FEATURES].to_numpy())[:, 1]

    scored["prob_ensemble"] = (scored["prob_rf"] + scored["prob_xgb"]) / 2
    scored["old_prob"] = scored["deposit_probability"]
    scored["prob_delta"] = scored["prob_ensemble"] - scored["old_prob"]

    def bucket(p):
        if p >= 0.65: return "High Potential"
        if p >= 0.45: return "Moderate Potential"
        return "Low Potential"
    scored["risk_category_new"] = scored["prob_ensemble"].map(bucket)

    cols = ["lat", "lon", "prob_rf", "prob_xgb", "prob_ensemble",
            "old_prob", "prob_delta", "risk_category_new"]
    scored[cols].to_csv(OUT / "grid_scores_v2.csv", index=False)

    # Feature importance from RF
    imp = pd.Series(models["rf"].feature_importances_, index=FEATURES).sort_values(ascending=False)
    imp.to_csv(OUT / "feature_importance.csv", header=["importance"])

    print("\nTop features (RF):")
    print(imp.head(8).round(3).to_string())
    print(f"\nSaved: {OUT/'grid_scores_v2.csv'} ({len(scored)} cells), feature_importance.csv")

if __name__ == "__main__":
    main()

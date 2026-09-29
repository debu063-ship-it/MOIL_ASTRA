# Model Training Summary — v3 (2026-09-29)

Scripts: `scripts/train_prospectivity_v3.py`, `scripts/train_shortfall_v2.py`
Artifacts: `outputs/models_v3/`, `data/processed/grid_scores_v3.csv`, `data/processed/shortfall_predictions_v2.csv`

## 1) Reserve / prospectivity model (grid_scores_v3)

**Winner:** soft-voting ensemble (XGBoost + RandomForest + HistGradientBoosting), selected over
RF / ExtraTrees / HGB / XGB / LR by spatial LOGO cross-validation (groups = each mine + negative clusters).

| Model | Random 5-fold ROC/PR | Spatial LOGO ROC/PR |
|---|---|---|
| RandomForest | 0.999 / 0.999 | 0.992 / 0.993 |
| ExtraTrees | 0.982 / 0.986 | 0.910 / 0.941 |
| HistGB | 0.989 / 0.986 | 0.989 / 0.987 |
| XGBoost | 0.996 / 0.997 | 0.992 / 0.994 |
| **Ensemble** | **1.000 / 1.000** | **0.997 / 0.998** |

- Training: 140 samples = 30 known deposits + **50 real NGDR borehole collars** (positives) vs 60 controls.
- Features: S2 spectral + terrain + GSI geology one-hots + **dist_to_known_deposit_km**,
  **dist_to_borehole_km** (weights-of-evidence layers), in_sausar.
- Deployment realism: **54% of top-decile cells lie within 3 km of a known deposit** (~40x the 3.8%
  base rate of the region).
- **Honest ablation** (evidence-only, no proximity proxies): spatial ROC **0.759** / PR **0.872** —
  spectral/terrain/geology alone still rank deposits, but proximity-to-known-mineralization is the
  dominant driver (native importance 0.53). Both views reported; XAI panel should show both.
- Caveat: spatial LOGO still shares regional structure; scores for unexplored terrain are optimistic.

## 2) Shortfall models (shortfall_predictions_v2)

Provenance: synthetic ops calibrated to real MOIL annual anchors + real rainfall seasonality.
Metrics validate *learning*, not real-ops performance (no public mine-monthly data exists).

**A) Next-month forecaster** (lags/rolls of shortfall ratio + ops + rain + mine/type):
- TS-CV best: ExtraTrees (MAE 0.0389 ratio).
- **Honest holdout (2025-08..12, untouched): MAE 0.0381 ratio ≈ 736 t/month, R² 0.656**
  vs baseline (mean ratio) MAE 0.0558 → **32% error reduction**.

**B) What-if response model** (no history features — drivable by the simulator):
- RandomForest, TS-CV MAE 0.0384; holdout MAE 0.0374.
- `outputs/models_v3/whatif_response_surface.csv` = precomputed surface over
  equipment_availability 0.75–1.0 × rain 0–400 mm for the modal mine profile.

**C) Alert classifier** (next-month shortfall ratio > 15%):
- TS-CV ROC 0.634 / PR 0.599 at 0.38 prevalence — weak; keep as secondary signal, not a standalone alert.

## Files
- `data/processed/grid_scores_v3.csv` — per-cell prob_v3 + risk_category_v3 (5,568 cells)
- `data/processed/shortfall_predictions_v2.csv` — holdout-month predictions per mine
- `outputs/models_v3/` — .joblib models, metadata JSONs, importance CSV, response surface

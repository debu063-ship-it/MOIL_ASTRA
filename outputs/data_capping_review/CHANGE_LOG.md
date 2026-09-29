# MOIL Manganese Prospectivity — Workflow Revision Change Log

**Project Directory:** `C:\Users\Debu018\Downloads\MOIL SIH26009`  
**Review Execution Date:** 2026-09-29  
**Output Locations:**  
- Revised Datasets: `data/capped_reviewed/`  
- Model-Ready Sets: `data/capped_reviewed/model_ready/`  
- Validation & Statistical Reports: `outputs/data_capping_review/`  

---

## 1. What Changed

1. **Default Outlier Policy Shifted to Flagging**:
   - Replaced automatic destructive clipping with non-destructive outlier flagging (`flag_<feature>_outlier`, `is_any_outlier`).
   - Original measurement values are 100% preserved.

2. **Rainfall Protection & Separation of Flag Types**:
   - Daily weather rainfall (`precipitation_sum (mm)`) is preserved without modification.
   - Generic IQR outlier flags (`flag_precipitation_sum (mm)_outlier`) are kept strictly separate from extreme rainfall flags.
   - Extreme daily rainfall is strictly defined as `precipitation > 100.0 mm` (`flag_extreme_rain_review`). Ordinary monsoon showers (11–99 mm) that exceed the IQR fence are no longer mislabeled as extreme rainfall.
   - Extreme monthly rainfall in synthetic operations and production scenarios is strictly defined as `monthly_rain_mm > 500.0 mm`.

3. **Aspect Handling**:
   - Raw aspect angles are excluded from linear IQR outlier flagging to avoid invalid 1D fences on cyclical 0°–360° variables.
   - In model-ready data, `aspect_sin = sin(aspect)` and `aspect_cos = cos(aspect)` are retained as unclipped trigonometric predictors (bounded naturally in $[-1, 1]$).

4. **Preservation of Accounting Identities**:
   - In operations datasets, `planned_tonnes`, `actual_tonnes`, and `shortfall_tonnes` are protected from clipping.
   - Eliminates the 157 accounting failures present in the old `data/capped/` folder where $\text{shortfall} \neq \max(\text{planned} - \text{actual}, 0)$.

5. **Train-Only Model Preparation Thresholds**:
   - In `data/capped_reviewed/model_ready/`, IQR clipping thresholds are fitted strictly on the training set and applied forward to test/validation sets, eliminating data leakage.
   - `deposit_probability` is excluded as an input feature for prospectivity modeling and treated solely as a diagnostic benchmark.

6. **Obsolete Spatial Split Archival**:
   - Archived stale single-class split files (`prospectivity_train_spatial_balaghat.csv` and `prospectivity_test_spatial_bhandara_nagpur.csv`) into `data/capped_reviewed/model_ready/archived_obsolete_splits/` prefixed with `STALE_DO_NOT_USE_`.
   - Active spatial split uses a balanced geographic longitude boundary at 79.75°E (West Block vs. East Block).

7. **Statistical Inference & Reporting**:
   - Mann–Whitney U tests on labeled samples evaluated against pooled, intra-belt, and outer-region controls with Benjamini–Hochberg FDR adjustments ($q$-values).
   - Accurately reports that **0 of 16 features** reach statistical significance ($q < 0.05$).
   - Global Moran's I permutation test ($B=999$) accurately reports the permutation resolution limit ($p \le 0.0010$).
   - Top-decile predicted cells are designated as **Descriptive Priority Targets**, not inferential statistical hotspots.
   - Synthetic operations analyses are explicitly framed as simulation scenario checks, not empirical MOIL mine data.

---

## 2. Validation Results

Executed via [`scripts/validate_capping_reviewed.py`](file:///c:/Users/Debu018/Downloads/MOIL%20SIH26009/scripts/validate_capping_reviewed.py):

| Verification Category | Target Standard | Result | Violations | Status |
|---|---|---|---|---|
| **Monthly Ops Shortfall Identity** | $\vert\text{shortfall} - \max(\text{plan} - \text{act}, 0)\vert \le 0.15\text{ t}$ | Max diff $= 0.100\text{ t}$ | 0 / 1,188 | **PASS** |
| **Production Scenario Shortfall** | $\vert\text{shortfall} - \max(\text{plan} - \text{act}, 0)\vert \le 0.02\text{ t}$ | Max diff $= 0.010\text{ t}$ | 0 / 1,452 | **PASS** |
| **Daily Weather Temperature Ordering** | $T_{\min} \le T_{\text{mean}} \le T_{\max}$ | Evaluated on 17,136 station-days | 0 / 17,136 | **PASS** |
| **Rainfall Value Preservation** | $\text{Delta}(\text{raw}, \text{reviewed}) == 0$ | Max delta $= 0.000\text{ mm}$ across all sites | 0 | **PASS** |
| **Row Keys & Timestamps** | Exact row-for-row alignment with raw source data | Verified on all 7 datasets | 0 | **PASS** |
| **Original Raw Column Preservation** | Identical values for all raw source columns | Verified across all features | 0 | **PASS** |
| **Audited Physical Range Bounds** | Specific fields: elevation, slope, B2..B12, NDVI, aspect_sin/cos, Gondite dist, rain, equipment avail, downtime, soil moisture | All checked fields within domain bounds | 0 | **PASS** |

---

## 3. Unresolved Limitations

1. **Small Sample Size for Known Deposits ($n=30$)**:
   - With only 30 labeled deposit points across 3 districts, univariate statistical power after multiple testing correction is insufficient to demonstrate significant standalone spectral separation.
   - Spatial block validation leaves only 13–17 positive deposits per partition, producing wide uncertainty bounds on out-of-fold metrics.

2. **Synthetic Operational Data**:
   - The production scenarios (`monthly_ops_synthetic_2015_2026.csv`, `production_scenario.csv`) are synthetic simulations and must not be used to infer actual MOIL historical performance or establish causal claims.

3. **Absence of 3D Subsurface Assays**:
   - The dataset currently lacks drillhole collars, downhole assay intervals, and 3D wireframe geology, restricting prospectivity modeling to 2D surficial screening.

---

## 4. Exact Re-run Command

To re-run the complete workflow end-to-end:
```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts/run_reviewed_pipeline.py
```

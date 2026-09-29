# Feature-by-Feature Data Gap Analysis (SIH26009)

Date: 2026-09-29. Legend: ✅ = real data on disk, 🟡 = synthetic/proxy only, ❌ = missing entirely.

> **UPDATE 2026-09-29 (evening):** The top-priority unlock happened — both NGDR exploration
> packages (Gudma CRO-23394-2017, Western Ukwa CRO-23290-2016) were downloaded and parsed
> (`data/external/exploration/ngdr_parsed/`). This closes the core gaps for **#1** (50 real
> collars + 77 structure measurements as new ground truth), **#10** (GSI-measured thickness,
> SG 3.55/2.09, volumes: 2.183 Mt @ 35.1% Mn Ukwa + 0.169 Mt Gudma), and **#11** (161 real
> assay samples, 57 ore-grade averaging 34.9% Mn). Remaining gaps below are unchanged except
> where noted: assay/coverage is still block-scale (2 blocks), and mine-monthly production
> remains unobtainable publicly.

## What we actually have today (real)

| Asset | File | Coverage |
|---|---|---|
| Sentinel-2 spectral (B2–B12) + DEM terrain | `data/external/satellite/s2_dem_grid_samples.csv` (5,568 cells) | Balaghat bbox 21.1–22.05N, 79.2–80.49E |
| Weather daily 2015→2026 ×4 stations | `data/external/satellite/weather_daily_*.csv` (skiprows=3) | ~4,285 rows |
| Soil moisture hourly ×4 | `data/external/satellite/soilmoisture_hourly_*.csv` | 102,818 rows |
| NDVI monthly ×4 | `data/external/satellite/ndvi_monthly_*.csv` | 139 rows |
| GSI geology polygons (53) | `data/external/geology/gsi_geology_grid.csv` | unit/age/dist_to_sausar_km |
| NGDR borehole catalog (51 records) | `data/external/geology/ngdr/ngdr_ai_query_balaghat_boreholes.csv` | **metadata only** (NUID, stage, year, toposheet) |
| IBM/MOIL reserves 2024 (20 mines) | `data/external/exploration/ibm_moil_reserves_2024.csv` | lease_ha, drilling_m, UNFC tonnage — **no grade column** |
| 2-block exploration summary | `data/external/exploration/manganese_drilling_resource_summary.csv` | Gudma & W. Ukwa: thickness range, tonnage, avg Mn 21.65% (Gudma only) |
| Labeled samples | `data/raw/labeled_samples_dataset.csv` (90×23), `known_occurrences.csv` (11×47) | 11 known mines = real positives |
| Model scores | `data/processed/grid_scores_v2.csv` | prob_rf/xgb/ensemble per cell |

**Synthetic (must be replaced or clearly labeled):** boreholes_synthetic.csv, block_model.geojson/parquet, monthly_ops_synthetic_2015_2026.csv, production_scenario.csv (anchored to real MOIL annual totals but mine-wise monthly is generated).

---

## 1. Manganese prospectivity map
✅ Have: S2 spectral, DEM, GSI geology, NDVI, 90 labels, 11 confirmed mine locations, scores for all 5,568 cells.
❌ Missing:
- **Drill-confirmed ground truth beyond the 11 known mines** — no collar coordinates for the 51 NGDR catalog entries (catalog is metadata-only; reports not yet downloaded).
- **Negative labels** from surveyed-but-barren ground (needed to fix class balance / avoid circular training near mines).
- Airborne geophysics (magnetic/EM) and hyperspectral (AVIRIS-NG) anomaly layers.
- Structural layers: fault/lineament map (structural fields in known_occurrences.csv are blank), drainage density.
- Soil/rock geochemistry (pXRF or lab assay grids).
📍 Source: NGDR report PDFs (13-file manifest, 2 priority NUIDs) → collar coords + assay intervals; GSI Bhukosh for lineament/geophysics layers.

## 2. Production forecasting
✅ Have: real weather (2015→2026), real MOIL **annual** company production anchors.
🟡 Have: monthly mine-wise planned/actual — synthetic (`production_scenario.csv`, `monthly_ops_synthetic_*.csv`).
❌ Missing:
- **Mine-wise monthly production (planned vs actual)** — MOIL publishes company-annual only; mine-monthly does not exist publicly. Options: request from MOIL mentor, scrape annual-report mine tables for annual-only calibration.
- ROM grade by month, ore vs waste split, stripping ratio, OMS (output per man-shift).
- Life-of-mine / mine-plan drawdown schedules (which blocks feed which years).
- Mn ore price series (if forecasting value, not just tonnes).
📍 Impact: model currently learns synthetic rain-sensitivity coefficients; with real annual anchors only, monthly skill is unverifiable.

## 3. Shortfall prediction
🟡 Have: synthetic disruption events (equipment_availability, downtime_hours, blast_delay_flag, injected monsoon events).
❌ Missing:
- Real maintenance/downtime logs and equipment availability records (MOIL internal).
- Real historical disruption log: strikes, power cuts, explosives shortage, flooding, evacuation orders.
- Calibration of rainfall → stoppage-day thresholds (we have rain data; no linkage to actual halt days).
- Logistics: rail-rake availability, dispatch/lead-time data (shortfall is often logistics, not mining).
- Labor attendance/shift data.
📍 Impact: shortfall classifier can only be demonstrated on synthetic events until MOIL shares ops logs — flag this in the pitch.

## 4. Dashboard
✅ Have: mine boundaries (`data/raw/moil_mines.geojson`), scores, zones, KPI tables.
❌ Missing:
- Real monthly production **targets** per mine (currently synthetic plan = 5% uplift of synthetic actual).
- Alert thresholds / business rules from MOIL (what counts as "shortfall" worth escalating).
- Stock/inventory levels (ROM yard, despatch).
- Production deployment feeds: GEE service account + scheduled refresh (auth works interactively today, not as an unattended pipeline).

## 5. Corrective action
❌ Missing (entirely — biggest conceptual gap):
- Historical corrective actions + their measured outcomes (action → production delta). Without action-outcome pairs, recommendations can only be rule-based playbooks, not learned.
- MOIL SOP/playbook documents, intervention costs, procurement lead times (e.g., how long a crusher repair takes).
📍 Workaround: hard-code an expert rule table (rain>threshold → reschedule blasting; equipment_availability<x → shift load to mine Y) and say so honestly.

## 6. What-if simulator
🟡 Have: simulator inputs exist (scenario CSV with disruption flags, rain).
❌ Missing:
- **Calibrated response coefficients**: rain→production elasticity, equipment availability→output curve, grade-tonnage response. Currently assumed in the synthetic generator.
- Real constraint envelopes: mine capacity (t/month), shift structure, haulage limits.
- Price/demand scenarios if the simulator includes economics.

## 7. Explainable AI
✅ Have: feature_importance.csv, per-cell probabilities.
❌ Missing: no *new external data* required — but explanations are bounded by feature set: SHAP will show spectral/geology/weather drivers and silently omit geophysics/geochem/borehole density (data gaps from #1 leak into #7). Also add per-cell SHAP export (compute, not fetch).

## 8. Report export
❌ Missing: MOIL/org template + branding, disclaimer text, and — critically — **real numbers to cite** (production sections currently cite synthetic series). Map figures need print-res raster exports (config, not data).

## 9. Interactive map layers
✅ Have: geology polygons, probability raster, mines, priority zones, 3 satellite PNGs.
❌ Missing:
- Forest cover / restricted-area (FC Act) layers — mining permission context.
- Cadastral lease boundaries beyond the 20 MOIL polygons (accuracy unverified).
- Toposheet footprints (we have toposheet_number in NGDR catalog — derivable).
- Road/rail network for logistics context; drainage.
- More up-to-date S2 composite tiles as basemap (have 3 PNGs only).

## 10. Volume & area where manganese is present
✅ Have: 2D area (priority_zones.geojson from 5,568-cell probability surface); real IBM UNFC tonnage for 20 mines.
🟡 Have: block_model (synthetic geometry).
❌ Missing:
- **Thickness per zone** — 2D probability × thickness × bulk density = volume; we have neither real interpolated thickness nor measured bulk density for the grid.
- Real 3D block model from boreholes (synthetic today); ore-body dip/strike geometry from real sections.
- UNFC stage breakdown mapped to our zones (IBM CSV has UNFC codes per mine — joinable, but our "zones" ≠ their "mine blocks").
📍 Fastest unlock: the two priority NGDR reports (Gudma CRO-23394-2017, W. Ukwa CRO-23290-2016) contain TABLES workbooks with real borehole intervals.

## 11. Grade of manganese ore
✅ Have: IBM reserves table (tonnage only — **no grade column**), avg Mn 21.65% for Gudma block only.
🟡 Have: synthetic borehole assays (mn_pct, fe_pct).
❌ Missing:
- Real assays per borehole/interval: Mn%, Fe%, P%, SiO₂, Al₂O₃ (P is the key penalty element for Mn ore).
- Ore-type classification (pyrolusite vs psilomelane vs silicate/carbonate facies) — changes processing route.
- Mine-wise ROM grade history; grade-tonnage curves per deposit.
📍 Same unlock as #10: NGDR report downloads + IBM annual report tables.

---

## Priority ranking (impact × feasibility)

1. **NGDR report PDFs** (blocked, workaround designed) — single unlock for #1, #10, #11: collars, assays, thickness.
2. **Bulk density + thickness → volume pipeline** for #10 (can start with literature values for Sausar Mn ore, label as assumed).
3. **MOIL real ops data** for #2, #3, #5, #6 — ask the hackathon mentor; if unavailable, keep synthetic but label every chart "synthetic calibration".
4. **Structural/lineament + forest layers** for #1, #9 from GSI Bhukosh / forest clearance portals (fetchable).
5. **Per-cell SHAP export** for #7 (pure compute, do when wiring the dashboard).

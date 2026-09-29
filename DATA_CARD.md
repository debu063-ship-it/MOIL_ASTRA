# Data card: MOIL ASTRA manganese intelligence dashboard

*Updated 2026-09-29 to reflect the integrated v3 models and live dashboard. Supersedes earlier versions that predate borehole/assay/reserve integration.*

## Purpose

Prospectivity mapping, production forecasting, and operational decision support for manganese mining in the Balaghat belt (Balaghat, Bhandara, Nagpur, Ukwa areas). Outputs support screening, planning, and hackathon demonstration; they do not establish a mineral resource or replace statutory exploration reporting.

## Coverage and coordinate system

- Prospectivity grid: **5,568 cell centroids** in EPSG:4326, lat 21.100–22.045 N, lon 79.200–80.490 E.
- Mapped dashboards centered on the Ukwa / Balaghat lease cluster (~80.45 E, 21.97 N).

## Data included (with volumes)

**Real, sourced data**

- **NGDR exploration**: **50 borehole collars** with 3D coordinates (block-unique IDs such as `UKWA-UKH-7`, `GUDMA-GDBH-1`) and **161 assay intervals**; 57 ore-grade intervals averaging **34.9% Mn**. Sourced from registered-user NGDR reports (GSI).
- **GSI geology**: **135 lithology polygons** (MultiPolygon, validated ring geometry) colored by supergroup; regional structure set (77 measurements).
- **GSI resource blocks**: **37 blocks** with tonnage and grade (e.g., West Ukwa **2,182,604 t** validated against the published report; Gudma 169 kt @ 21.65%), rendered as 3D prisms (~120 m footprint). Measured SG values 3.55 / 2.09 used for volume→tonnage conversion.
- **IBM / MOIL statutory reserves (UNFC 2024)**: stages 111 = 16.76 Mt, 122 = 13.54 Mt, 211/221 = 35.79 Mt, 332/333 = 4.74 Mt; cutoff-grade curve (70.8 Mt at 15% Mn).
- **Satellite / climate**: Sentinel-2 sampled reflectance & derived indices (iron-oxide, clay ratio, ferrous iron, BSI, NDMI, NDVI), Copernicus DEM terrain, observed daily rainfall/weather station series, monthly rainfall grids for the timeline layer.

**Modeled outputs** (`[MODELED]`)

- Prospectivity probabilities per grid cell (v3 ensemble) → **160 priority zones** as UI polygons with probability, risk category, and estimated reserve contribution.
- Production forecasts, shortfall predictions, SHAP-style importances, what-if response surface.

**Synthetic, clearly labeled** (`[SYNTHETIC]`)

- Mine-monthly operations 2015–2026 for 9 mines (`data/synthetic/monthly_ops_synthetic_2015_2026.csv`) — equipment availability, downtime, blast delays, production/planned/shortfall — **calibrated to real MOIL annual anchors and real rainfall seasonality** (shortfall ratio mean 0.135). Labeled 90-sample alert training set.

## Model validation summary

- Prospectivity v3 (XGB+RF+HistGB ensemble, 140 samples = 80 positives + 60 controls): spatial LOGO ROC **0.997** / PR **0.998**; honest evidence-only ablation (proximity features removed) ROC **0.759**; top-decile hit rate 54% within 3 km of known mineralization (~40× base rate).
- Shortfall v2 ExtraTrees forecaster: honest holdout (2025-08..12) MAE ≈ **736 t/month**, R² 0.656, 32% better than mean baseline.
- Alert classifier ROC 0.634 — deliberately kept as a secondary signal.

## Limitations (read before judging)

- The sample intervals include ore and non-ore lithologies, overlapping records, and one reversed from/to interval retained and flagged as reported. Downhole survey traces are unavailable, so boreholes render as vertical traces below their collar elevation.
- **Volume & grade are quantified only for the two explored NGDR blocks (Ukwa, Gudma)** — the 37 GSI resource blocks and UNFC tables cover those areas; the wider basin carries modeled prospectivity only. Earlier drafts of this card said "the 3D block model is empty"; that is no longer true — blocks are served as 3D prisms via `/api/v1/dashboard/ore_volume`.
- Mine-wise monthly production, planned targets, and shortfalls in `data/synthetic/` are **illustrative, not observed MOIL operating data**; models trained on them validate learning, not real-ops accuracy (no public mine-monthly data exists).
- Corrective actions are **deterministic rule playbooks** (CA-001…CA-009), not learned policies — no action-outcome data was available.
- Spatial LOGO validation still shares regional structure; prospectivity scores for truly unexplored terrain remain optimistic.
- Mapped outputs support screening and discussion; they do not establish a mineral resource or replace field exploration.

## Provenance

Generated rows/features carry one of **SOURCE**, **DERIVED**, or **SYNTHETIC** tags, with source references or a method + seed. See `data/MANIFEST.json`, `data/GAPS_LOG.md`, [docs/data_sources.md](docs/data_sources.md), and [docs/feature_data_gaps.md](docs/feature_data_gaps.md). Legacy raw files were left unchanged and may not contain row-level provenance fields. The UI displays `[REAL]` / `[MODELED]` / `[SYNTHETIC]` badges on every layer and key metric, and generated reports embed the same tags.

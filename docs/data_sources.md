# MOIL AI/ML PS — Data Sources Master Index

Fetched **2026-09-24**. All data below is real unless marked *synthetic (Phase 2)*.

## 1. Weather / Satellite-derived — ✅ FETCHED
Source: Open-Meteo Historical Archive (ERA5 reanalysis + satellite-derived soil moisture).
Free, no API key, citable as "ERA5 via Open-Meteo (2026)".

Location             | Files
---------------------|---------------------------------------------------------------
Balaghat (21.82N, 80.20E) | `data/external/satellite/weather_daily_balaghat_2015_2026.csv`
Ukwa (21.95N, 80.10E)     | `data/external/satellite/weather_daily_ukwa_2015_2026.csv`
Bhandara (21.17N, 79.65E) | `data/external/satellite/weather_daily_bhandara_2015_2026.csv`
Nagpur (21.15N, 79.09E)   | `data/external/satellite/weather_daily_nagpur_2015_2026.csv`

- **Daily variables** (per file, ~4,285 rows, 2015-01-01 → 2026-09-23):
  precipitation_sum (mm), temperature_2m_mean/max/min (°C), ET₀ FAO (mm), wind_speed_10m_max (km/h)
- **Soil moisture** (hourly, ~102,820 rows per file, m³/m³):
  `data/external/satellite/soilmoisture_hourly_<mine>_2015_2026.csv` — layers 0–7 cm and 7–28 cm
- Refresh: change `end_date` in the URL; same API supports **forecast** endpoints for the shortfall early-warning model.

## 2. NDVI / Vegetation Index — ✅ FETCHED
Real MODIS MOD13Q1 (250 m, 16-day, monthly means over 2 km buffer, 2015→2026, 139 months/site):
`data/external/satellite/ndvi_monthly_<mine>_2015_2026.csv` (Balaghat, Ukwa, Bhandara, Nagpur).
Source: Google Earth Engine, project `gen-lang-client-0124119718`. Script: `scripts/fetch_ndvi_gee.py`.
Verified: dry-season dip + monsoon peak present.

## 2b. Sentinel-2 reflectance + Copernicus DEM — ✅ FETCHED
Real measured values for all 5,568 prospectivity grid cells (dry-season 2024 cloud-masked S2 L2A median + GLO30 2024_1 terrain, 30 m):
`data/external/satellite/s2_dem_grid_samples.csv`
columns: lat, lon, B2, B3, B4, B8, B11, B12, ndvi, elevation, slope, aspect.
Script: `scripts/fetch_s2_dem_grid.py` (replaces the model-derived spectral/terrain values in `region_grid_predictions.csv`).

## 3. Geology — ✅ FETCHED (GSI official polygons)
Real GSI 1:2M "Geology of India" polygons (Geological Survey of India, via public ArcGIS
Feature Service livingatlas.esri.in `Geology/Geology`, CC-licensed source GSI):
- `data/external/geology/gsi_geology_raw.json` — 53 polygons covering the belt bbox
  (20.9–22.1N, 78.9–80.6E): SAUSAR Gp (Mansar/Junewani/Sitasaongi/Lohangi/Bichua Fm),
  Tirodi Gneissic Complex, Amgaon Gneissic Complex, Sakoli Gp, Dongargarh Granite, Deccan Trap, etc.
- `data/external/geology/gsi_geology_grid.csv` — per-grid-cell assignment (5,568 rows):
  lat, lon, gsi_group, gsi_unit, gsi_age, **dist_to_sausar_km**.
- Validation: all 6 verified mines lie 0.4–3.5 km from the mapped SAUSAR boundary.
- Script: `scripts/build_gsi_geology_grid.py` (re-runnable; fetch URL inside).

## 3b. NGDR exploration reports (Balaghat Mn) — ✅ metadata FETCHED, ✅ 2 priority packages DOWNLOADED & PARSED
**2026-09-29: Full registered-user downloads for Gudma (CRO-23394-2017, G3) and Western
Ukwa (CRO-23290-2016, G2) — report PDFs, TABLES workbooks, GIS File GDBs, georeferenced
plate images. Parsed into analysis-ready files by `scripts/parse_ngdr_exploration.py` →
`data/external/exploration/ngdr_parsed/`:**
- `boreholes_collars.csv` / `exploration_boreholes.geojson` — **50 real collars** (37 Ukwa + 13 Gudma),
  toposheet 64C/05, real collar RLs (Gudma 589.7–597 m; Ukwa 599–603 m from Table-10), borehole names UKBH/UKH/GSU/GUG/GDBH.
- `borehole_assays.csv` — **161 sample rows, 102 with Mn%**: real interval assays
  (Gudma Table-V: Mn ore 20.2–45.0% Mn; Ukwa ANNEXURE-VIII(B): Mn ore 13.5–50.7% Mn with Fe/SiO2/P and measured SG 3.75–5.3),
  57 ore-grade (Mn≥15%) samples averaging **34.9% Mn**. Includes geochem annexures (MnO, P2O5, trace elements, REE).
- `borehole_lithologs.csv` — 73 summarized lithology intervals across 11 Ukwa boreholes
  (soil → laterite → schists → Mn ore horizon → biotite gneiss basement).
- `resource_estimates.csv` — 37 GSI resource blocks: true/apparent thickness, Mn%, measured SG
  (3.55 Ukwa / 2.09 Gudma), volume m³, tonnage, category. Totals cross-checked against report-stated values:
  **Western Ukwa 2.183 Mt @ 35.1% Mn; Gudma 0.169 Mt @ 21.65% Mn; + 0.21 Mt probable (partial W-block)**.
- `structure_measurements.csv` — 77 real strike/dip + plunge measurements (59 planes, 18 lines).
- `lithology_polygons.geojson` — 135 mapped lithology polygons from the GDB plates (unit/age/mineral attrs).
- Georeferenced rasters: `Dam-3.tif` (+.tfw, ~35 m/px, EPSG:4326) and `PLATE 7.tif`; raw archives kept under
  `data/external/geology/ngdr/downloads/<NUID>/`.
- Residual gaps after this batch: Ukwa PLATE 3/4 georef images + supplementary IMAGE zip (3 manifest rows,
  lower value); assay coverage is block-scale (2 blocks), not district-wide; mine-monthly production data
  still does not exist publicly (see feature_data_gaps.md).
Source: NGDR AI Query Interface (geodataindia.gov.in, login required), query
"i want to find the borehole data of balaghat manganese mines", export PDF
195 pp → parsed with `scripts/parse_ngdr_ai_pdf.py` (+ `scripts/fix_ngdr_nuids.py`).
- `data/external/geology/ngdr/ngdr_ai_query_balaghat_boreholes.csv` — **51 real records**:
  nuid (standard `PREFIX-NNNNN-YYYY`, 51/51 verified), project_title, commodity (Manganese),
  state_name, district_name (48/51 mention Balaghat), toposheet_number, exploration_stage
  (G4×28, G3×22, G2×1); NUID prefixes CRO/IBM/DMP; years 1962–2024.
- Source PDF kept at `C:\Users\Debu018\Downloads\NGDR_i_want_to_find_the_borehole_da_2026-09-28 (8).pdf`.
- Report files for the 2 priority NUIDs: ✅ downloaded & parsed (see below). Remaining 49 catalog
  NUIDs are metadata-only; fetch on demand via the same Download Cart flow.

Still available (manual, browser + login): GSI Bhukosh occurrence points — see
`docs/ndvi_and_geology_sources.md`.
Notes: USGS MRDS and Overpass API are unreachable from this network; Macrostrat has only
coarse world-map coverage for India.

## 4. Production history — 📋 verified sources + seed figures
Real annual/monthly production figures already compiled with citations in
`docs/production_data_sources.md` (MOIL ARs, PIB, IBM Yearbook, BSE filings).
Download the AR PDFs → extract to `data/external/production/production_history.csv`.

## 5. Phase-2 synthetic (downtime, blasting delays) — *to generate*
No public source exists. Will be generated with documented assumptions anchored to
the real production figures above and real monsoon rainfall seasonality.

## Folder layout
```
data/external/satellite/    # ✅ 8 real CSVs (weather + soil moisture)
data/external/geology/ngdr/ # ✅ 51 NGDR Mn exploration records (catalog CSV)
data/external/geology/      # Bhukosh downloads go here
data/external/production/   # MOIL AR PDFs + extracted CSV go here
data/synthetic/             # Phase-2 generated data
docs/                       # this file + source guides
scripts/                    # fetch_ndvi_gee.py, (upcoming) generators
```

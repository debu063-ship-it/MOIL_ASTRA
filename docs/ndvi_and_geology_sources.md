# NDVI / Vegetation Index — How to Get It

## Option A (recommended): Google Earth Engine — script included
1. Create a free Google account and register at https://code.earthengine.google.com/register (choose "Noncommercial" or research use).
2. `pip install earthengine-api geemap pandas`
3. `earthengine authenticate`
4. `python scripts/fetch_ndvi_gee.py`

→ produces `data/external/satellite/ndvi_monthly_<mine>_2015_2026.csv` for all 4 sites (MODIS MOD13Q1, 250 m, monthly mean over a 2 km buffer).

## Option B (no signup): Sentinel-2 via Open-Meteo does not exist — use Copernicus Browser
1. Register free at https://dataspace.copernicus.eu
2. Use "Copernicus Browser" → area: Balaghat/Bhandara belt → Sentinel-2 L2A → NDVI visualization → download stat exports manually (slower, UI-based).

## Option C (NASA AppEEARS, free login)
https://appeears.earthdatacloud.nasa.gov — point-and-click subset of MODIS 13Q1 over your ROI; outputs CSV/NetCDF.

# Manganese Geology Data — GSI Bhukosh Guide

## Bhukosh (Geological Survey of India) — free, official
1. Go to https://bhukosh.gsi.gov.in
2. Login (free registration) → "Mineral Resources" → select state = **Madhya Pradesh** and **Maharashtra**, commodity = **Manganese**.
3. Layers to download (each has a download/export button as CSV/KML/shapefile):
   - Mineral occurrence points (Mn) — lat/lon, type, host rock
   - Geological quadrangle maps (GQ) — Balaghat, Bhandara, Nagpur quadrangles
   - Lineament / structure layers if available
4. Save into `data/external/geology/`.

## Other useful geology sources
- **India-WRIS / Bhuvan (ISRO)**: https://bhuvan.nrsc.gov.in — land use/land cover, DEM (CartoDEM 30 m) — useful as model features.
- **Published literature**: papers on the Sausar Group / Mansar formation (mn belt, central India) — good for validation of mapped prospectivity, not bulk data.
- **USGS MRDS**: https://mrdata.usgs.gov/mrds/ — global mineral deposits CSV; includes India Mn occurrences (coarse but machine-readable, good as extra training labels).

# Production Data — Where to Get It

## MOIL Annual Reports (official, real)
- https://moil.nic.in → "Investors" → "Annual Reports" (PDF). Contains mine-wise and year-wise production, reserves, grades.
- Save PDFs to `data/external/production/moil_annual_reports/`.

## Ministry of Mines / Indian Bureau of Mines (IBM)
- Monthly production statistics: https://mines.gov.in and https://ibm.gov.in — "Indian Minerals Yearbook" (annual, state + mineral-wise manganese ore production, free PDFs).
- India Data Portal: https://indiadataportal.com — has machine-readable CSVs of mineral production (search "manganese ore production state wise").

## Extraction tip
Once PDFs are downloaded, extract tables into one `data/external/production/production_history.csv` with columns:
`year, mine, ore_raised_mt, mn_grade_pct, remarks`. If table extraction is messy (it usually is), use `camelot-py` or `pdfplumber`:
```
pip install pdfplumber
python -c "import pdfplumber; [print(p.extract_text()) for p in pdfplumber.open('report.pdf').pages]"
```

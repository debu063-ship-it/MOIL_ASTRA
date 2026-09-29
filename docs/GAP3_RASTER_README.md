# Gap 3 raster fallback: Google Earth Engine

Use this only if `scripts/close_gap3_rasters.py` reports a public STAC/network
failure. The script uses real Copernicus DEM GLO-30 and real Sentinel-2 L2A
scenes; it does not synthesize raster values.

1. Open the Google Earth Engine Code Editor with an account that has Earth
   Engine access.
2. Open `scripts/earth_engine_gap3.js`. Its bounding box is the existing grid
   extent expanded by approximately 2 km; confirm against
   `data/raw/region_grid_predictions.csv` before running.
3. Run the script and approve the seven Google Drive export tasks.
4. Download each completed GeoTIFF into `data/processed/rasters/`.
5. Run `python scripts/close_gap3_rasters.py --verify-only` to sample the
   rasters at the grid centroids and produce the correlation report.

The current Planetary Computer script writes 60 m outputs from the 30 m GLO-30
source and Sentinel-2 L2A observations, in EPSG:4326 for the project grid. Any
output from the GEE fallback must also be sampled at the 5,568 centroids and compared against
`s2_dem_grid_samples.csv` before it is treated as complete. NDVI, slope, aspect,
hillshade, and RGB composites are DERIVED products of real SOURCE imagery/DEM.

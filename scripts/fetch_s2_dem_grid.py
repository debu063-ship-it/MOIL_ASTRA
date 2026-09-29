"""
Fetch REAL Sentinel-2 surface reflectance + Copernicus DEM terrain for the
5,568-cell MOIL prospectivity grid — one reduceRegions call for everything.

Replaces the model-derived B2..B12/elevation/slope/aspect values in
data/raw/region_grid_predictions.csv with measured values.

PREREQ: ee authenticated (already done) + earthengine-api + pandas.

RUN:
  export PATH="$LOCALAPPDATA/Programs/Python/Python312:$LOCALAPPDATA/Programs/Python/Python312/Scripts:$PATH"
  python scripts/fetch_s2_dem_grid.py

OUTPUT:
  data/external/satellite/s2_dem_grid_samples.csv
  columns: lat,lon,B2,B3,B4,B8,B11,B12,ndvi,elevation,slope,aspect
"""
import ee
import pandas as pd

ee.Initialize(project="gen-lang-client-0124119718")

GRID_CSV = "data/raw/region_grid_predictions.csv"
OUT = "data/external/satellite/s2_dem_grid_samples.csv"

# ---- grid cells as an EE FeatureCollection -------------------------------
grid = pd.read_csv(GRID_CSV)
cells = grid[["lat", "lon"]].drop_duplicates()
fc = ee.FeatureCollection(
    [
        ee.Feature(ee.Geometry.Point([r.lon, r.lat]), {"lat": r.lat, "lon": r.lon})
        for r in cells.itertuples()
    ]
)
print(f"Grid cells: {len(cells)}")

# ---- Sentinel-2 L2A median composite (dry season, cloud-masked) -----------
def mask_s2(img):
    scl = img.select("SCL")
    # mask clouds, cirrus, snow, dark pixels
    mask = (
        scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
    )
    return img.updateMask(mask).divide(10000)

s2 = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterDate("2024-01-01", "2024-03-31")  # dry season: clear skies, low veg signal noise
    .filterBounds(fc.geometry())
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
    .map(mask_s2)
)
bands = ["B2", "B3", "B4", "B8", "B11", "B12"]
composite = s2.select(bands).median()

# ---- Copernicus DEM 30 m --------------------------------------------------
dem = (
    ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1")
    .select("DEM")
    .mosaic()
)
slope = ee.Terrain.slope(dem)
aspect = ee.Terrain.aspect(dem)
stack = (
    composite.addBands(dem.rename("elevation"))
    .addBands(slope.rename("slope"))
    .addBands(aspect.rename("aspect"))
    .addBands(composite.normalizedDifference(["B8", "B4"]).rename("ndvi"))
)

# ---- sample everything in one call ---------------------------------------
def sample_chunk(points):
    chunk_fc = ee.FeatureCollection(
        [ee.Feature(ee.Geometry.Point([lon, lat]), {"lat": lat, "lon": lon}) for lat, lon in points]
    )
    result = stack.reduceRegions(
        collection=chunk_fc, reducer=ee.Reducer.mean(), scale=30, crs="EPSG:4326"
    )
    return [f["properties"] for f in result.getInfo()["features"]]

points = list(zip(cells["lat"], cells["lon"]))

# checkpointing: skip points already fetched (script is re-run in batches)
import os
if os.path.exists(OUT):
    done = pd.read_csv(OUT)
    done_keys = set(zip(done["lat"], done["lon"]))
    points = [p for p in points if p not in done_keys]
    print(f"Resuming: {len(done_keys)} done, {len(points)} remaining")
else:
    done = None

rows = []
CHUNK = 200
for i in range(0, len(points), CHUNK):
    rows.extend(sample_chunk(points[i : i + CHUNK]))
    print(f"  {min(i + CHUNK, len(points))}/{len(points)}", flush=True)
    # checkpoint after every chunk
    new = pd.DataFrame(rows)[
        ["lat", "lon"] + bands + ["ndvi", "elevation", "slope", "aspect"]
    ]
    combined = new if done is None else pd.concat([done, new], ignore_index=True)
    combined.to_csv(OUT, index=False)

df = pd.read_csv(OUT)
print(df.describe().loc[["mean", "min", "max"]].round(3).to_string())

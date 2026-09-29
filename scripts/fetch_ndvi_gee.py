"""
Fetch MODIS NDVI (16-day, 250m) monthly means for the MOIL manganese belt.

PREREQUISITES (one-time):
  pip install earthengine-api geemap pandas
  earthengine authenticate      # opens browser, use a free Google account
  Then sign up at https://code.earthengine.google.com/register (Noncommercial/Research)

RUN:
  python scripts/fetch_ndvi_gee.py

OUTPUT:
  data/external/satellite/ndvi_monthly_<mine>_2015_2026.csv  (columns: month, ndvi_mean)
"""
import ee
import pandas as pd

ee.Initialize(project="gen-lang-client-0124119718")

MINE_SITES = {
    "balaghat": (21.82, 80.20),
    "ukwa":     (21.95, 80.10),
    "bhandara": (21.17, 79.65),
    "nagpur":   (21.15, 79.09),
}

# MODIS Terra Vegetation Indices 16-day, 250 m
modis_ndvi = (
    ee.ImageCollection("MODIS/061/MOD13Q1")
    .select("NDVI")
    .map(lambda img: img.multiply(0.0001).copyProperties(img, ["system:time_start"]))
)

START = "2015-01-01"
N_MONTHS = 138  # ~11.5 years

def monthly_means(lon, lat):
    point = ee.Geometry.Point([lon, lat]).buffer(2000)  # ~2 km around mine
    months = ee.List.sequence(0, N_MONTHS)

    def per_month(m):
        start = ee.Date(START).advance(m, "month")
        end = start.advance(1, "month")
        img = modis_ndvi.filterDate(start, end).mean()
        stat = img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point,
            scale=250,
            maxPixels=1e9,
        ).get("NDVI")
        return ee.Feature(None, {"month": start.format("YYYY-MM"), "ndvi_mean": stat})

    return ee.FeatureCollection(months.map(per_month))

if __name__ == "__main__":
    for name, (lat, lon) in MINE_SITES.items():
        fc = monthly_means(lon, lat)
        rows = [f["properties"] for f in fc.getInfo()["features"]]
        df = pd.DataFrame(rows)
        out = f"data/external/satellite/ndvi_monthly_{name}_2015_2026.csv"
        df.to_csv(out, index=False)
        print(f"{name}: {len(df)} months -> {out}")

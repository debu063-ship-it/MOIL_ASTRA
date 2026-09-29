"""
Fetch real Sentinel-2 IMAGE TILES of the MOIL belt for the dashboard/deck:
  1. True-color composite (B4-B3-B2)  — cloud-free dry-season 2024 median
  2. False-color composite (B8-B4-B3) — vegetation/landform contrast
  3. Hillshade from Copernicus GLO30 DEM

Region: 20.9-22.1N, 78.9-80.6E (Balaghat-Bhandara-Nagpur manganese belt).

OUTPUT: data/external/satellite/imagery/belt_truecolor.png / belt_falsecolor.png / belt_hillshade.png
RUN:    python scripts/fetch_belt_imagery.py
"""
import ee
import urllib.request

ee.Initialize(project="gen-lang-client-0124119718")

REGION = ee.Geometry.Rectangle([78.9, 20.9, 80.6, 22.1])
OUTDIR = "data/external/satellite/imagery"
DIMS = 2048  # width px (~85 m/px across the belt; GEE thumb cap is 50 MB)

# same cloud-masked dry-season composite as the grid sampler
def mask_s2(img):
    scl = img.select("SCL")
    mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
    return img.updateMask(mask).divide(10000)

s2 = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterDate("2024-01-01", "2024-03-31")
    .filterBounds(REGION)
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
    .map(mask_s2)
)
median = s2.median()

dem = ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").select("DEM").mosaic()
hillshade = ee.Terrain.hillshade(dem.reproject(crs="EPSG:4326", scale=90))

IMAGES = [
    (
        "belt_truecolor.png",
        median.select(["B4", "B3", "B2"]),
        {"bands": ["B4", "B3", "B2"], "min": 0, "max": 0.3, "gamma": 1.2},
    ),
    (
        "belt_falsecolor.png",
        median.select(["B8", "B4", "B3"]),
        {"bands": ["B8", "B4", "B3"], "min": 0, "max": 0.45, "gamma": 1.1},
    ),
    (
        "belt_hillshade.png",
        hillshade,
        {"bands": ["hillshade"], "min": 0, "max": 255, "palette": ["000000", "ffffff"]},
    ),
]

import os
import urllib.request

os.makedirs(OUTDIR, exist_ok=True)


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as f:
            f.write(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read()[:300]}")
        raise

for fname, img, vis in IMAGES:
    url = img.getThumbURL({"format": "png", "dimensions": DIMS, "region": REGION, **vis})
    dest = f"{OUTDIR}/{fname}"
    download(url, dest)
    size_mb = os.path.getsize(dest) / 1e6
    print(f"{fname}: {size_mb:.1f} MB")
print("done")

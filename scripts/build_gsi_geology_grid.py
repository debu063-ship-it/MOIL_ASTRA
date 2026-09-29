"""
Assign each of the 5,568 prospectivity grid cells its REAL geological unit from
the GSI 1:2M "Geology of India" polygons (Fetched via ArcGIS REST, source:
Geological Survey of India). Pure-python point-in-polygon, no geopandas needed.

INPUT:  data/external/geology/gsi_geology_raw.json  (GeoJSON, 53 polygons)
OUTPUT: data/external/geology/gsi_geology_grid.csv  (lat,lon,gsi_group,gsi_unit,gsi_age)
"""
import json
import pandas as pd

GEO = "data/external/geology/gsi_geology_raw.json"
GRID = "data/raw/region_grid_predictions.csv"
OUT = "data/external/geology/gsi_geology_grid.csv"

with open(GEO) as f:
    gj = json.load(f)

# build polygon index with bounding boxes: [(bbox, ring_or_holes, attrs)]
polys = []
for feat in gj["features"]:
    props = {
        "gsi_group": (feat["properties"].get("group_") or "").strip(),
        "gsi_unit": (feat["properties"].get("index_") or "").strip(),
        "gsi_age": (feat["properties"].get("age") or "").strip(),
    }
    geom = feat["geometry"]
    if geom["type"] == "Polygon":
        geomlist = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        geomlist = geom["coordinates"]
    else:
        continue
    for part in geomlist:  # part = [outer_ring, hole1, hole2...]
        xs = [p[0] for p in part[0]]
        ys = [p[1] for p in part[0]]
        polys.append(((min(xs), min(ys), max(xs), max(ys)), part, props))

print(f"Polygon parts indexed: {len(polys)}")


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def lookup(lat, lon):
    for bbox, part, props in polys:
        if bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]:
            if point_in_ring(lon, lat, part[0]) and not any(
                point_in_ring(lon, lat, h) for h in part[1:]
            ):
                return props
    return {"gsi_group": "", "gsi_unit": "", "gsi_age": ""}


grid = pd.read_csv(GRID)[["lat", "lon"]].drop_duplicates().sort_values(["lat", "lon"])
rows = []
for r in grid.itertuples():
    props = lookup(r.lat, r.lon)
    rows.append({"lat": r.lat, "lon": r.lon, **props})
    if len(rows) % 1000 == 0:
        print(f"  {len(rows)}/{len(grid)}", flush=True)

df = pd.DataFrame(rows)

# distance to nearest SAUSAR polygon boundary (km) — robust feature since the
# 1:2M SAUSAR belt is narrow and mines often fall in adjacent TGC cells
import numpy as np

sausar_segs = []
for feat in gj["features"]:
    if "SAUSAR" not in (feat["properties"].get("group_") or "").upper():
        continue
    geom = feat["geometry"]
    parts = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for part in parts:
        ring = np.array(part[0], dtype=float)
        segs = np.stack([ring[:-1], ring[1:]], axis=1)  # (n, 2, 2)
        sausar_segs.append(segs)
segs = np.vstack(sausar_segs)
print(f"SAUSAR boundary segments: {len(segs)}")

R_KM = 111.32  # deg->km approx at these latitudes (lon scaled by cos)

def dist_to_sausar_km(lat, lon):
    a, b = segs[:, 0, 0], segs[:, 0, 1]  # segment start (lon, lat)
    c, d = segs[:, 1, 0], segs[:, 1, 1]  # segment end
    abx, aby = c - a, d - b
    acx, acy = lon - a, lat - b
    denom = abx * abx + aby * aby
    t = np.clip(np.where(denom > 0, (acx * abx + acy * aby) / denom, 0), 0, 1)
    px = a + t * abx
    py = b + t * aby
    dx = (lon - px) * np.cos(np.radians(lat))
    dy = lat - py
    return float(np.sqrt(dx * dx + dy * dy).min() * R_KM)

df["dist_to_sausar_km"] = [
    dist_to_sausar_km(r.lat, r.lon) for r in df.itertuples()
]

df.to_csv(OUT, index=False)
print(f"Wrote {len(df)} rows -> {OUT}")
print("\nUnit distribution:")
print(df["gsi_unit"].value_counts().to_string())

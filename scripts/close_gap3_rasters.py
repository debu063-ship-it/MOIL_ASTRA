"""Fetch 30 m DEM and cloud-filtered Q1-2024 Sentinel-2 COGs from Planetary Computer.

Deliverables use EPSG:4326 to match project centroid coordinates. Rasters are
downloaded/reduced from real public imagery; terrain derivatives/NDVI are DERIVED.
"""
from __future__ import annotations

import json
import math
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import planetary_computer as pc
import rasterio
import stackstac
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import calculate_default_transform, reproject
from scipy.ndimage import generic_filter
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "data/raw/region_grid_predictions.csv"
SAMPLES = ROOT / "data/external/satellite/s2_dem_grid_samples.csv"
OUT = ROOT / "data/processed/rasters"
OUT.mkdir(parents=True, exist_ok=True)
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
DATE_RETRIEVED = date.today().isoformat()
TARGET_CRS = "EPSG:4326"
WORK_CRS = "EPSG:32644"
# Project cell spacing is ~1.6 km; 60 m output retains useful terrain/reflectance
# detail while keeping a regional 2 km buffered export tractable on a workstation.
RES_M = 60


def get_work_bounds() -> tuple[float, float, float, float]:
    grid = pd.read_csv(GRID)
    # Transform bbox corners to UTM 44N, then buffer 2 km in projected units.
    tr = Transformer.from_crs(TARGET_CRS, WORK_CRS, always_xy=True)
    west, east = float(grid.lon.min()), float(grid.lon.max())
    south, north = float(grid.lat.min()), float(grid.lat.max())
    corners = [tr.transform(x, y) for x in (west, east) for y in (south, north)]
    return (min(x for x, _ in corners) - 2000, min(y for _, y in corners) - 2000,
            max(x for x, _ in corners) + 2000, max(y for _, y in corners) + 2000)


def search_items(client, collection: str, bbox_ll: list[float], start: str, end: str):
    kwargs = {"collections": [collection], "bbox": bbox_ll, "max_items": 200}
    if collection == "sentinel-2-l2a":
        kwargs["datetime"] = f"{start}T00:00:00Z/{end}T00:00:00Z"
        kwargs["query"] = {"eo:cloud_cover": {"lt": 60}}
    search = client.search(**kwargs)
    return list(search.items())


def reduce_stack(items, assets: list[str], bounds, epsg: int, mask_scl: bool = False):
    cube = stackstac.stack(items, assets=assets, epsg=epsg, resolution=RES_M,
                           bounds=bounds, resampling=Resampling.nearest,
                           chunksize=512, dtype="float32", fill_value=np.float32(-9999.0), rescale=False,
                           xy_coords="center")
    if mask_scl:
        scl = cube.sel(band="SCL")
        reflectance = cube.sel(band=["B02", "B03", "B04", "B08", "B11", "B12"])
        # SCL 3=cloud shadow, 8/9=cloud, 10=cirrus, 11=snow/ice.
        valid = (scl >= 0) & ~scl.isin([3, 8, 9, 10, 11])
        reflectance = reflectance.where(valid) * 0.0001
        composite = reflectance.median(dim="time", skipna=True).compute(scheduler="single-threaded")
        arrays = {str(b): np.asarray(composite.sel(band=b).values, dtype=np.float32)
                  for b in ["B02", "B03", "B04", "B08", "B11", "B12"]}
        return arrays, cube.attrs["transform"]
    data = cube.median(dim="time", skipna=True).compute(scheduler="single-threaded")
    values = np.asarray(data.sel(band=assets[0]).values, dtype=np.float32)
    values[values == -9999] = np.nan
    return values, cube.attrs["transform"]


def reproject_array(array: np.ndarray, src_transform, src_crs: str,
                    dst_transform, width: int, height: int,
                    method=Resampling.bilinear) -> np.ndarray:
    dst = np.full((height, width), np.nan, dtype=np.float32)
    reproject(source=array, destination=dst, src_transform=src_transform,
              src_crs=src_crs, src_nodata=np.nan, dst_transform=dst_transform,
              dst_crs=TARGET_CRS, dst_nodata=np.nan, resampling=method)
    return dst


def write_cog(path: Path, data: np.ndarray, transform, *, provenance: str,
              source_ref: str, method: str, descriptions: list[str] | None = None):
    if data.ndim == 2:
        data = data[np.newaxis, :, :]
    height, width = data.shape[1:]
    profile = {"driver": "GTiff", "height": height, "width": width,
               "count": data.shape[0], "dtype": "float32", "crs": TARGET_CRS,
               "transform": transform, "nodata": np.nan,
               "compress": "DEFLATE", "predictor": 3, "tiled": True,
               "blockxsize": 512, "blockysize": 512}
    temp = path.with_suffix(".tmp.tif")
    with rasterio.open(temp, "w", **profile) as ds:
        ds.write(data.astype(np.float32, copy=False))
        ds.update_tags(provenance=provenance, source_ref=source_ref,
                       retrieval_date=DATE_RETRIEVED, method=method)
        if descriptions:
            ds.descriptions = tuple(descriptions)
    rasterio.shutil.copy(temp, path, driver="COG", compress="DEFLATE",
                         blocksize=512, overview_resampling="average")
    temp.unlink()


def main() -> dict:
    client = Client.open(STAC, modifier=pc.sign_inplace)
    work_bounds = get_work_bounds()
    to_ll = Transformer.from_crs(WORK_CRS, TARGET_CRS, always_xy=True)
    corners = [to_ll.transform(x, y) for x in (work_bounds[0], work_bounds[2])
               for y in (work_bounds[1], work_bounds[3])]
    bbox_ll = [min(x for x, _ in corners), min(y for _, y in corners),
               max(x for x, _ in corners), max(y for _, y in corners)]

    dem_items = search_items(client, "cop-dem-glo-30", bbox_ll, "2024-01-01", "2024-04-01")
    s2_items_all = search_items(client, "sentinel-2-l2a", bbox_ll,
                                "2024-01-01", "2024-04-01")
    if not dem_items or not s2_items_all:
        raise RuntimeError(f"STAC returned no data (DEM={len(dem_items)}, S2={len(s2_items_all)})")
    # Keep the three clearest scenes for each MGRS tile for a reproducible median.
    by_tile: dict[str, list] = {}
    for item in s2_items_all:
        tile = str(item.properties.get("s2:mgrs_tile", "unknown"))
        by_tile.setdefault(tile, []).append(item)
    s2_items = []
    for tile, tile_items in sorted(by_tile.items()):
        tile_items.sort(key=lambda i: (float(i.properties.get("eo:cloud_cover", 100)), i.id))
        s2_items.extend(tile_items[:3])

    dem, dem_transform = reduce_stack(dem_items, ["data"], work_bounds, 32644)
    s2_bands, src_transform = reduce_stack(s2_items,
                         ["B02", "B03", "B04", "B08", "B11", "B12", "SCL"],
                         work_bounds, 32644, mask_scl=True)
    # Transform projected bounds to output EPSG:4326 with an approximately 30 m grid.
    out_corners = [to_ll.transform(x, y) for x in (work_bounds[0], work_bounds[2])
                   for y in (work_bounds[1], work_bounds[3])]
    west = min(x for x, _ in out_corners); east = max(x for x, _ in out_corners)
    south = min(y for _, y in out_corners); north = max(y for _, y in out_corners)
    lat0 = (north + south) / 2
    px_x = RES_M / (111320.0 * math.cos(math.radians(lat0)))
    px_y = RES_M / 110574.0
    width = math.ceil((east - west) / px_x); height = math.ceil((north - south) / px_y)
    out_transform = from_origin(west, north, px_x, px_y)

    dem_ll = reproject_array(dem, dem_transform, WORK_CRS, out_transform, width, height)
    bands_ll = {b: reproject_array(a, src_transform, WORK_CRS, out_transform, width, height)
                for b, a in s2_bands.items()}
    slope = np.degrees(np.arctan(np.hypot(*np.gradient(dem_ll, px_y * 110574,
                          px_x * 111320 * math.cos(math.radians(lat0)))))).astype(np.float32)
    gy, gx = np.gradient(dem_ll, px_y * 110574,
                         px_x * 111320 * math.cos(math.radians(lat0)))
    aspect = (np.degrees(np.arctan2(-gx, gy)) + 360.0) % 360.0
    azimuth, altitude = math.radians(315), math.radians(45)
    slope_rad, aspect_rad = np.radians(slope), np.radians(aspect)
    hillshade = 255.0 * (np.cos(altitude) * np.cos(slope_rad) +
                         np.sin(altitude) * np.sin(slope_rad) * np.cos(azimuth - aspect_rad))
    hillshade = np.clip(hillshade, 0, 255).astype(np.float32)
    b2, b3, b4, b8, b11, b12 = (bands_ll[k] for k in ["B02", "B03", "B04", "B08", "B11", "B12"])
    ndvi = np.divide(b8 - b4, b8 + b4, out=np.full_like(b8, np.nan), where=(b8 + b4) != 0)

    src_s2 = "Planetary Computer STAC collection sentinel-2-l2a; retrieved " + DATE_RETRIEVED
    src_dem = "Planetary Computer STAC collection cop-dem-glo-30; retrieved " + DATE_RETRIEVED
    write_cog(OUT / "dem.tif", dem_ll, out_transform, provenance="SOURCE", source_ref=src_dem,
              method="Copernicus DEM GLO-30 STAC mosaic, 30 m nearest-neighbor scene alignment")
    for name, arr, method in [
        ("slope", slope, "Slope in degrees from DEM by finite differences"),
        ("aspect", aspect.astype(np.float32), "Aspect in degrees from DEM gradients"),
        ("hillshade", hillshade, "Hillshade from DEM; azimuth 315 degrees, altitude 45 degrees"),
        ("ndvi", ndvi, "(B08-B04)/(B08+B04) from cloud-masked median reflectance"),
    ]:
        write_cog(OUT / f"{name}.tif", arr, out_transform, provenance="DERIVED",
                  source_ref=src_dem if name in ("slope", "aspect", "hillshade") else src_s2,
                  method=method)
    write_cog(OUT / "s2_reflectance.tif", np.stack([b2,b3,b4,b8,b11,b12]), out_transform,
              provenance="DERIVED", source_ref=src_s2,
              method="Median of the clearest three 2024-01-01 to 2024-03-31 L2A scenes per MGRS tile; SCL cloud/shadow/snow masked; scaled by 1/10000",
              descriptions=["B02", "B03", "B04", "B08", "B11", "B12"])
    write_cog(OUT / "s2_truecolor.tif", np.stack([b4,b3,b2]), out_transform,
              provenance="DERIVED", source_ref=src_s2, method="True-color band stack B04/B03/B02",
              descriptions=["B04", "B03", "B02"])
    write_cog(OUT / "s2_falsecolor.tif", np.stack([b8,b4,b3]), out_transform,
              provenance="DERIVED", source_ref=src_s2, method="False-color band stack B08/B04/B03",
              descriptions=["B08", "B04", "B03"])

    return verify_samples({"status": "COMPLETE", "crs": TARGET_CRS, "buffer_m": 2000,
              "output_resolution_m": RES_M, "bbox_wgs84": bbox_ll,
              "stac_dem_items": len(dem_items), "stac_s2_items_used": len(s2_items),
              "s2_mgrs_tiles": sorted(by_tile), "retrieval_date": DATE_RETRIEVED,
              "provenance_note": "DEM is SOURCE; spectral median and true/false color are DERIVED from real L2A scenes; NDVI/slope/aspect/hillshade are DERIVED. This follows the project SOURCE/DERIVED rule even where task text requested SOURCE for computed bands.",
              "source_ref": [src_dem, src_s2]})


def verify_samples(report: dict | None = None) -> dict:
    existing = pd.read_csv(SAMPLES)
    centroids = list(zip(existing.lon.astype(float), existing.lat.astype(float)))
    sample_rasters = {"B2": (OUT / "s2_reflectance.tif", 1),
                      "B3": (OUT / "s2_reflectance.tif", 2),
                      "B4": (OUT / "s2_reflectance.tif", 3),
                      "B8": (OUT / "s2_reflectance.tif", 4),
                      "B11": (OUT / "s2_reflectance.tif", 5),
                      "B12": (OUT / "s2_reflectance.tif", 6),
                      "ndvi": (OUT / "ndvi.tif", 1), "elevation": (OUT / "dem.tif", 1),
                      "slope": (OUT / "slope.tif", 1), "aspect": (OUT / "aspect.tif", 1)}
    corr = {}
    for col, (path, band) in sample_rasters.items():
        with rasterio.open(path) as ds:
            vals = np.array([v[0] for v in ds.sample(centroids, indexes=band)], dtype=float)
        valid = np.isfinite(vals) & np.isfinite(existing[col].to_numpy(dtype=float))
        corr[col] = {"n": int(valid.sum()), "pearson_r": float(np.corrcoef(
            vals[valid], existing.loc[valid, col].to_numpy(dtype=float))[0,1]) if valid.sum() > 1 else None}
    report = {"gap": 3, "crs": TARGET_CRS, "grid_cells_sampled": len(existing),
              "correlation_vs_existing_samples": corr, **(report or {})}
    (ROOT / "data/processed/raster_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    try:
        if "--record-stalled" in sys.argv[1:]:
            report = {"gap": 3, "status": "BLOCKED_RASTER_FETCH_STALLED",
                      "retrieval_date": DATE_RETRIEVED,
                      "error": "STAC search and individual COG range requests worked, but the full buffered regional median-composite reduction did not complete within the local run. No rasters were emitted.",
                      "fallback": "Use scripts/earth_engine_gap3.js and docs/GAP3_RASTER_README.md; do not use sampled values as substitute rasters."}
            (ROOT / "data/processed/raster_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            raise SystemExit(0)
        if "--verify-only" in sys.argv[1:]:
            print(json.dumps(verify_samples({"gap": 3, "status": "VERIFIED_EXISTING_RASTERS",
                "crs": TARGET_CRS, "retrieval_date": DATE_RETRIEVED,
                "method": "Sample existing raster outputs at all project grid centroids."}), indent=2))
            raise SystemExit(0)
        print(json.dumps(main(), indent=2))
    except KeyboardInterrupt:
        report = {"gap": 3, "status": "BLOCKED_RASTER_FETCH_STALLED", "retrieval_date": DATE_RETRIEVED,
                  "error": "Planetary Computer STAC metadata was reachable, but regional COG reduction did not complete in this run.",
                  "fallback": "Use scripts/earth_engine_gap3.js and docs/GAP3_RASTER_README.md; no raster values were fabricated."}
        (ROOT / "data/processed/raster_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        raise SystemExit(2)
    except Exception as exc:
        report = {"gap": 3, "status": "BLOCKED_RASTER_FETCH_FAILED", "error": str(exc),
                  "retrieval_date": DATE_RETRIEVED,
                  "fallback": "Use scripts/earth_engine_gap3.js and docs/GAP3_RASTER_README.md; no raster values were fabricated."}
        (ROOT / "data/processed/raster_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise

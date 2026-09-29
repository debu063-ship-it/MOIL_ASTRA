"""Run all five data-gap workflows, then build the provenance manifest and reports."""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import rasterio

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCRIPTS = [
    ("Gap 1 - boreholes", "scripts/close_gap1_boreholes.py", "data/processed/borehole_validation.json"),
    ("Gap 2 - block model", "scripts/close_gap2_block_model.py", "data/processed/block_model_validation.json"),
    ("Gap 3 - rasters", "scripts/close_gap3_rasters.py", "data/processed/raster_validation.json"),
    ("Gap 4 - priority polygons", "scripts/close_gap4_priority_polygons.py", "data/processed/priority_zone_validation.json"),
    ("Gap 5 - production scenario", "scripts/close_gap5_production_scenario.py", "data/processed/production_scenario_validation.json"),
]


def run_workflows() -> list[dict]:
    statuses = []
    for label, script, status_path in SCRIPTS:
        status_file = ROOT/status_path
        status = json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else {}
        if label == "Gap 3 - rasters" and status.get("status") == "BLOCKED_RASTER_FETCH_STALLED":
            # Gap 3 was already attempted interactively; avoid repeating a known-stalled regional download.
            statuses.append({"label": label, "script": script, "returncode": 0,
                             "details": status, "skipped_retry": True})
            print(f"{label}: skipped retry, status={status['status']}")
            continue
        proc = subprocess.run([sys.executable, str(ROOT/script)], cwd=ROOT,
                              capture_output=True, text=True)
        status = json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else status
        if proc.returncode:
            status.setdefault("status", "FAILED")
            status["process_error"] = (proc.stderr or proc.stdout)[-2500:]
        statuses.append({"label": label, "script": script,
                         "returncode": proc.returncode, "details": status})
        print(f"{label}: exit={proc.returncode}, status={status.get('status','missing status')}")
        if proc.returncode:
            print((proc.stderr or proc.stdout)[-1200:])
    return statuses


def manifest() -> dict:
    rows = []
    for p in sorted(DATA.rglob("*")):
        if not p.is_file() or p.name == "MANIFEST.json":
            continue
        rel = p.relative_to(ROOT).as_posix()
        suffix = p.suffix.lower()
        count = None
        crs = None
        provenance_mix = {}
        bands = None
        shape = None
        generator = None
        if suffix == ".csv":
            with p.open("r", encoding="utf-8-sig", newline="") as f:
                raw_rows = list(csv.DictReader(f))
            if p.name.startswith(("weather_daily_", "soilmoisture_hourly_")):
                # API files have a two-line location preamble, blank separator, then observation header.
                count = sum(1 for line in p.read_text(encoding="utf-8-sig").splitlines()
                            if line and line[0].isdigit() and "T" in line.split(",",1)[0] or
                               (line and len(line.split(",",1)[0]) == 10 and line[0].isdigit()))
            else:
                count = len(raw_rows)
            if raw_rows and "provenance" in raw_rows[0]:
                provenance_mix = dict(Counter(r.get("provenance", "") or "UNSPECIFIED" for r in raw_rows))
            else:
                provenance_mix = legacy_provenance(rel, count)
            if any(k in raw_rows[0] for k in ("lat", "latitude")) if raw_rows else False:
                crs = "EPSG:4326"
            generator = script_for(rel)
        elif suffix in (".json", ".geojson"):
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
                if doc.get("type") == "FeatureCollection":
                    count = len(doc.get("features", [])); crs = "EPSG:4326"
                    values = [f.get("properties", {}).get("provenance") for f in doc.get("features", [])]
                    if values:
                        provenance_mix = dict(Counter(v or "UNSPECIFIED" for v in values))
                    elif doc.get("metadata", {}).get("provenance"):
                        provenance_mix = {doc["metadata"]["provenance"]: 0}
                    else:
                        provenance_mix = legacy_provenance(rel, count)
                else:
                    count = len(doc.get("features", [])) if isinstance(doc.get("features"), list) else None
                    provenance_mix = {"DERIVED": 1} if rel.startswith("data/processed/") else legacy_provenance(rel, count)
            except Exception:
                pass
            generator = script_for(rel)
        elif suffix == ".parquet":
            pf = pq.ParquetFile(p); count = pf.metadata.num_rows
            meta = pf.schema_arrow.metadata or {}
            crs = meta.get(b"crs", b"").decode() or None
            if rel.startswith("data/external/"):
                provenance_mix = {"SOURCE": count} if count else {"SOURCE": 0}
                if p.name == "NGDR_Mining_Exploration_Drilling_Boreholes.parquet":
                    crs = "EPSG:4326"
            else:
                provenance_mix = {"DERIVED": count} if count else {"DERIVED": 0}
            generator = script_for(rel)
        elif suffix == ".tif":
            with rasterio.open(p) as ds:
                count = ds.height; crs = ds.crs.to_string() if ds.crs else None
                bands = ds.count; shape = [ds.height, ds.width]
                tags = ds.tags(); provenance_mix = {tags.get("provenance", "UNSPECIFIED"): ds.count}
            generator = script_for(rel)
        elif suffix == ".pdf":
            provenance_mix = {"SOURCE": 1}; generator = "official NGDR/GSI or IBM source document"
        elif suffix == ".xlsx":
            # These official workbooks contain several unrelated sheets, so
            # count only the current core-assay intervals relevant to Gap 1.
            audit_path = DATA / "processed" / "borehole_validation.json"
            audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
            book_audit = audit.get("registered_workbook_audit") or {}
            block = "Gudma" if "CRO-23394-2017" in p.name else "Western Ukwa" if "CRO-23290-2016" in p.name else None
            count = (book_audit.get("assay_intervals_by_block", {}).get(block)
                     if block else None)
            provenance_mix = {"SOURCE": count} if count is not None else {"SOURCE": 1}
            generator = "official NGDR registered-user workbook"
        elif suffix == ".png":
            provenance_mix = legacy_provenance(rel, 1); generator = script_for(rel)
        elif suffix in (".md", ".txt"):
            count = 1
            provenance_mix = {"DERIVED": 1}
            generator = script_for(rel)
        else:
            generator = script_for(rel)
        rows.append({"path": rel, "row_count": count, "crs": crs,
                     "provenance_mix": provenance_mix,
                     "provenance_assessment": "Row/feature tags when present; otherwise file-level legacy assessment.",
                     "generating_script": generator, "raster_bands": bands,
                     "raster_shape_rows_cols": shape})
    rows.append({"path":"data/MANIFEST.json", "row_count":1, "crs":None,
                 "provenance_mix":{"DERIVED":1}, "provenance_assessment":"Manifest generated by this runner.",
                 "generating_script":"scripts/run_data_gaps.py", "raster_bands":None,
                 "raster_shape_rows_cols":None})
    doc = {"manifest_version":1, "generated_by":"scripts/run_data_gaps.py",
           "generated_date":"2026-09-29", "grid_crs":"EPSG:4326",
           "grid_rows":5568, "files":rows,
           "notes":["Legacy files were not altered to retrofit row provenance.",
                    "SOURCE/DERIVED/SYNTHETIC tags are emitted on all newly generated tabular and feature outputs.",
                    "Empty schema outputs are listed with row_count 0 where the required source inputs are unavailable."]}
    (DATA/"MANIFEST.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return doc


def legacy_provenance(rel: str, count) -> dict:
    lower = rel.lower()
    if "/synthetic/" in lower or "synthetic" in lower:
        cls = "SYNTHETIC"
    elif any(t in lower for t in ["region_grid_predictions", "grid_scores", "feature_importance",
                                   "training_labels", "labeled_samples", "grid.csv", "priority_zones"]):
        cls = "DERIVED"
    elif "imagery/" in lower or "hillshade" in lower:
        cls = "DERIVED"
    else:
        cls = "SOURCE"
    return {cls: count or 0}


def script_for(rel: str):
    name = Path(rel).name
    mapping = {
        "gsi_geology_grid.csv":"scripts/build_gsi_geology_grid.py",
        "gsi_geology_raw.json":"public GSI feature service",
        "s2_dem_grid_samples.csv":"scripts/fetch_s2_dem_grid.py",
        "ndvi_monthly_balaghat_2015_2026.csv":"scripts/fetch_ndvi_gee.py",
        "ndvi_monthly_bhandara_2015_2026.csv":"scripts/fetch_ndvi_gee.py",
        "ndvi_monthly_nagpur_2015_2026.csv":"scripts/fetch_ndvi_gee.py",
        "ndvi_monthly_ukwa_2015_2026.csv":"scripts/fetch_ndvi_gee.py",
        "belt_truecolor.png":"scripts/fetch_belt_imagery.py",
        "belt_falsecolor.png":"scripts/fetch_belt_imagery.py",
        "belt_hillshade.png":"scripts/fetch_belt_imagery.py",
        "monthly_ops_synthetic_2015_2026.csv":"scripts/generate_synthetic_ops.py",
        "boreholes_source.csv":"scripts/close_gap1_boreholes.py",
        "borehole_assays_source.csv":"scripts/close_gap1_boreholes.py",
        "published_drilling_summaries.csv":"scripts/close_gap1_boreholes.py",
        "NGDR_Mining_Exploration_Drilling_Boreholes.parquet":"scripts/close_gap1_boreholes.py",
        "boreholes_synthetic.csv":"scripts/close_gap1_boreholes.py",
        "20250708115140.988_CRO-23394-2017.xlsx":"official NGDR registered-user download; parsed by scripts/close_gap1_boreholes.py",
        "20250708115140.923_CRO-23394-2017.pdf":"official NGDR registered-user download",
        "20240724141822.249_CRO-23290-2016.xlsx":"official NGDR registered-user download; parsed by scripts/close_gap1_boreholes.py",
        "20240724141822.027_CRO-23290-2016.pdf":"official NGDR registered-user download",
        "priority_zones.geojson":"scripts/close_gap4_priority_polygons.py",
        "production_scenario.csv":"scripts/close_gap5_production_scenario.py",
        "block_model.parquet":"scripts/close_gap2_block_model.py",
        "block_model.geojson":"scripts/close_gap2_block_model.py",
        "dem.tif":"scripts/close_gap3_rasters.py",
        "slope.tif":"scripts/close_gap3_rasters.py",
        "aspect.tif":"scripts/close_gap3_rasters.py",
        "hillshade.tif":"scripts/close_gap3_rasters.py",
        "ndvi.tif":"scripts/close_gap3_rasters.py",
        "s2_truecolor.tif":"scripts/close_gap3_rasters.py",
        "s2_falsecolor.tif":"scripts/close_gap3_rasters.py",
        "s2_reflectance.tif":"scripts/close_gap3_rasters.py",
    }
    return mapping.get(name, "scripts/run_data_gaps.py" if name in ("MANIFEST.json", "GAPS_LOG.md") else None)


def reports(statuses, man) -> None:
    d = {x["label"].split(" - ")[0]:x["details"] for x in statuses}
    s1,s2,s3,s4,s5 = (d.get(f"Gap {i}",{}) for i in range(1,6))
    gap_log = f'''# Data gaps closeout log\n\nGenerated by `scripts/run_data_gaps.py` on 2026-09-29. Existing raw files were read-only.\n\n## Gap 1 - drill-hole logs and assays\n\n**Status: {s1.get('status','unknown')}.** A SHA-256-pinned public GitHub release attributed to NGDR was filtered to the project grid bounds. It supplies {s1.get('imported_ngdr_collar_rows', 0)} Gudma manganese collar SOURCE rows with borehole names, coordinates, collar elevations, and total depths in `data/processed/boreholes_source.csv`; assay interval fields remain blank. The seven collar depths sum to 1009.7 m, matching the IBM 2018 Gudma drilling total. Source-specific IBM and Lok Sabha drilling/resource summaries are in `data/processed/published_drilling_summaries.csv`. The previous extracted summary and IBM 2018 report differ slightly on Gudma drilling/horizon figures, and the mirror labels six collars G2 with one stage blank while IBM/Lok Sabha summaries report G3; source-specific figures/stages are retained separately in the validation JSON. The public mirror does not supply grade assays or from/to intervals. NGDR workbook/report/map downloads for Gudma CRO-23394-2017 and Western Ukwa CRO-23290-2016 remain registered-user-only. No synthetic boreholes were generated because lease boundaries and assay constraints are unavailable. See `data/processed/borehole_validation.json`.\n\n## Gap 2 - 3D block model\n\n**Status: {s2.get('status','unknown')}.** Seven located Gudma collars are available, but there are no assay intervals, Western Ukwa collars, or lease outlines. No interpolation was run. Empty Parquet/GeoJSON schema artifacts are present. Cross-validation RMSE is not computable. The required note is embedded in the Parquet/GeoJSON metadata. See `data/processed/block_model_validation.json`.\n\n## Gap 3 - standalone DEM and imagery rasters\n\n**Status: {s3.get('status','unknown')}.** Public Planetary Computer data was attempted for Copernicus GLO-30 and cloud-filtered Sentinel-2 L2A over the grid bounds plus 2 km. CRS target is EPSG:4326. DEM observations are SOURCE; median reflectance and the derived slope/aspect/hillshade/NDVI/RGB products are marked DERIVED under the provenance rule. No rasters were emitted and no sample correlations were computed because the full regional composite stalled; details/fallback are `data/processed/raster_validation.json`. If blocked, Earth Engine fallback instructions are in `docs/GAP3_RASTER_README.md`.\n\n## Gap 4 - exploration-priority polygons\n\n**Status: {s4.get('status','unknown')}.** Top-decile and top-quartile cells were selected from the current 5,568-cell ensemble score grid, grouped by 8-neighbor connectivity, and single-cell speckles removed. GeoJSON features carry `provenance=DERIVED`, method, source references, and fixed random seed. The coverage vs 1,000-trial random-cell baseline is in `data/processed/priority_zone_validation.json`. Only 6 of the 11 occurrence rows have coordinates, so occurrence coverage uses six mappable locations. Scores are not independent validation because occurrences may inform existing training labels. Existing data has no explicit grid IDs, so stable IDs are formed from centroid latitude/longitude to preserve cell identity.\n\n## Gap 5 - mine-wise production targets and shortfalls\n\n**Status: {s5.get('status','unknown')}.** A new file `data/synthetic/production_scenario.csv` was generated; the existing 1,188-row synthetic operations file was left untouched. All new rows are `SYNTHETIC`; public company annual totals calibrate aggregate fiscal-year output, rainfall comes from the existing daily series, and mine allocations/targets/monthly shortfalls are explicitly scenario assumptions. There are no real mine-wise targets or shortfalls in the project. Validation is in `data/processed/production_scenario_validation.json`.\n\n## Still requires MOIL/GSI internal or registered-user data\n\n- NGDR drill-hole workbooks/report maps and lease boundary polygons.\n- Measured collar locations, assay intervals, ore thickness/grade intervals.\n- A defensible 3D geological/block model and spatial ore reserve estimate.\n- Mine-wise operational production plans/actuals and real shortfalls.\n\nThe public IBM yearbook lease reserve table is a summary, not a block model; see `data/external/exploration/ibm_moil_reserves_2024.csv` and `docs/ibm_moil_reserves_dataset.md`.\n'''
    workbook_audit = s1.get("registered_workbook_audit") or {}
    by_block = workbook_audit.get("assay_intervals_by_block", {})
    grade_checks = workbook_audit.get("source_grade_checks", {})
    gap1_text = (f"**Status: {s1.get('status','unknown')}.** Official NGDR workbooks for Gudma and Western Ukwa are archived unchanged with SHA-256 checksums. "
        f"The project now has {workbook_audit.get('collar_rows', 0)} located hole records ({workbook_audit.get('gudma_collars', 0)} Gudma and {workbook_audit.get('western_ukwa_collars', 0)} Western Ukwa) and "
        f"{s1.get('assay_interval_rows', 0)} matched core assay intervals ({by_block.get('Gudma', 0)} Gudma; {by_block.get('Western Ukwa', 0)} Western Ukwa). "
        "Per-hole intersections/weighted grades are in `data/processed/boreholes_source.csv`; sample-level intervals and chemistry are in `data/processed/borehole_assays_source.csv`. "
        f"Gudma interval-sheet and elemental Mn values agree within {grade_checks.get('gudma_table_v_vs_annexure_v_mn_pct_max_abs_difference', 'n/a')} percentage points; Western Ukwa matches exactly. "
        f"Validation flags {workbook_audit.get('sample_interval_overlap_pair_count', 0)} overlapping interval pairs and {workbook_audit.get('sample_interval_rows_with_to_not_after_from', 0)} reversed interval; source values were retained without repair. "
        f"There are {len(workbook_audit.get('reported_intersection_thickness_discrepancies', []))} reported per-hole thickness values that differ from their listed from/to span. "
        "Sample widths are not necessarily ore thickness, and sample grades include non-ore lithologies, so these are not resource estimates. Official map/GDB files and lease polygons remain unavailable. See `data/processed/borehole_validation.json`.")
    gap2_text = (f"**Status: {s2.get('status','unknown')}.** Real collar locations, per-hole mineralized-zone summaries, and 88 drill sample assays are now available. "
        "No 3D blocks were generated because complete downhole XYZ traces and mine lease polygons are still missing; sample depths are along-hole depths. "
        "The Parquet/GeoJSON remain empty and cross-validation RMSE is not computable until the model domain and hole traces are verified. See `data/processed/block_model_validation.json`.")
    def replace_gap_section(document, title, next_title, paragraph):
        start = document.index(f"## {title}")
        end = document.index(f"\n## {next_title}", start)
        return document[:start] + f"## {title}\n\n{paragraph}\n" + document[end:]
    gap_log = replace_gap_section(gap_log, "Gap 1 - drill-hole logs and assays", "Gap 2 - 3D block model", gap1_text)
    gap_log = replace_gap_section(gap_log, "Gap 2 - 3D block model", "Gap 3 - standalone DEM and imagery rasters", gap2_text)
    gap_log = gap_log.replace("- NGDR drill-hole workbooks/report maps and lease boundary polygons.",
                              "- NGDR georeferenced map/GDB files and MOIL mine lease boundary polygons.")
    gap_log = gap_log.replace("- Measured collar locations, assay intervals, ore thickness/grade intervals.",
                              "- Complete downhole survey/trajectory XYZ data and additional mine-specific drilling outside Gudma and Western Ukwa.")
    (DATA/"GAPS_LOG.md").write_text(gap_log, encoding="utf-8")
    # Regenerate manifest after adding closeout log; then recreate it once more to list itself.
    manifest()
    data_card = f'''# Data card: MOIL manganese prospectivity dashboard\n\n## Purpose\n\nExploratory mapping and data integration for manganese prospectivity in the Balaghat, Bhandara, Nagpur, and Ukwa area. Outputs support screening and discussion; they do not establish a mineral resource or replace field exploration.\n\n## Coverage and coordinate system\n\nThe project grid contains 5,568 centroids in geographic coordinates (EPSG:4326), spanning 21.100-22.045° N and 79.200-80.490° E.\n\n## Data included\n\n- GSI regional geology, mine and occurrence points, NGDR report metadata, seven NGDR-mirrored Gudma borehole collars, and published drilling/resource summary records.\n- Sentinel-2/Copernicus sampled reflectance/terrain values, four-site monthly NDVI, daily weather/rainfall, and hourly soil moisture.\n- Model labels, current prospectivity scores, and derived priority-zone polygons.\n- Official exploration/reserve summary records and public company-level annual production anchors.\n- Clearly labeled synthetic operations/production scenarios.\n\n## Limitations\n\nSeven public Gudma collar records are available with locations, collar elevations, and total depths, but there are no interval-level Mn/Fe assays or from/to depths. Mine lease outlines and a defensible 3D block model are unavailable. Regional geology is generalized; grid scores and priority zones are screening outputs. Mine-wise production allocations, planned targets, and shortfalls in synthetic files are illustrative and must never be reported as observed MOIL operating data. The block-model output is intentionally empty until suitable located assays and lease geometry are supplied.\n\n## Provenance\n\nNew generated rows/features carry one of `SOURCE`, `DERIVED`, or `SYNTHETIC`, with source references or a method and seed. See `data/MANIFEST.json` and `data/GAPS_LOG.md`. Existing legacy raw files were left unchanged and may not contain row-level provenance fields.\n'''
    data_card = data_card.replace("Â°", "°")
    data_card = data_card.replace("- GSI regional geology, mine and occurrence points, NGDR report metadata, seven NGDR-mirrored Gudma borehole collars, and published drilling/resource summary records.",
        "- GSI regional geology, mine and occurrence points, NGDR report metadata, and published drilling/resource summary records.\n- Thirteen located Gudma/Western Ukwa hole records and 88 official NGDR sample-assay intervals from the registered-user reports.")
    data_card = data_card.replace("Seven source Gudma collar records are available, but no interval-level Mn/Fe assays or from/to depths are available. Western Ukwa collar records, mine lease outlines, and a defensible 3D block model are still unavailable.",
        "The drill sample intervals include ore and non-ore lithologies, overlapping records, and one reversed from/to interval retained and flagged as reported. They must not be treated as independent clean ore widths or as a resource grade. Complete downhole XYZ traces, georeferenced map/GDB assets, and MOIL mine lease polygons remain unavailable, so the 3D block model is empty.")
    data_card = (
        "# Data card: MOIL manganese prospectivity dashboard\n\n"
        "## Purpose\n\n"
        "Exploratory mapping and data integration for manganese prospectivity in the Balaghat, Bhandara, Nagpur, and Ukwa area. Outputs support screening and discussion; they do not establish a mineral resource or replace field exploration.\n\n"
        "## Coverage and coordinate system\n\n"
        "The project grid contains 5,568 centroids in EPSG:4326, spanning latitude 21.100 to 22.045 N and longitude 79.200 to 80.490 E.\n\n"
        "## Data included\n\n"
        "- GSI regional geology, mine and occurrence points, NGDR report metadata, and published drilling/resource summaries.\n"
        "- Thirteen located Gudma/Western Ukwa drill holes and 88 official NGDR sample-assay intervals from the registered-user reports.\n"
        "- Sentinel-2/Copernicus sampled reflectance and terrain values, four-site monthly NDVI, daily rainfall/weather, and hourly soil moisture.\n"
        "- Prospectivity scores, model labels, and derived priority-zone polygons.\n"
        "- Public company-level production anchors and clearly labeled synthetic production scenarios.\n\n"
        "## Limitations\n\n"
        "The sample intervals include ore and non-ore lithologies, overlapping records, and one reversed from/to interval retained and flagged as reported. They are not independent clean ore widths or resource grades. Complete downhole XYZ traces, georeferenced map/GDB assets, and MOIL mine lease polygons remain unavailable, so the 3D block model is empty. Priority zones are screening outputs. Mine-wise production allocations, planned targets, and shortfalls in synthetic files are illustrative, not observed MOIL operating data.\n\n"
        "## Provenance\n\n"
        "New generated rows/features carry one of SOURCE, DERIVED, or SYNTHETIC, with source references or a method and seed. See data/MANIFEST.json and data/GAPS_LOG.md. Existing legacy raw files were left unchanged and may not contain row-level provenance fields.\n"
    )
    (ROOT/"DATA_CARD.md").write_text(data_card, encoding="utf-8")
    manifest()


def main():
    statuses = run_workflows()
    man = manifest()
    reports(statuses, man)
    print("\nSummary")
    print("-"*64)
    for s in statuses:
        print(f"{s['label']:<32} {s['details'].get('status','FAILED')}")
    print(f"{'Manifest files':<32} {len(man['files'])}")


if __name__ == "__main__":
    main()

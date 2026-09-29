"""Import public NGDR collar records and preserve published manganese summaries.

The public GitHub release is an NGDR-attributed mirror. This script pins the
download by SHA-256, filters it to the project's 5,568-cell bounding box, and
emits collar-only SOURCE rows. It never fabricates interval assays.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "data/external/exploration/reports"
OUT = ROOT / "data/processed"
SYN = ROOT / "data/synthetic"
SUMMARY_SOURCE = ROOT / "data/external/exploration/manganese_drilling_resource_summary.csv"
MANIFEST = ROOT / "data/external/exploration/ngdr_report_manifest.csv"
GRID_SAMPLES = ROOT / "data/external/satellite/s2_dem_grid_samples.csv"
NGDR_DIR = ROOT / "data/external/geology/ngdr"
NGDR_FILE = NGDR_DIR / "NGDR_Mining_Exploration_Drilling_Boreholes.parquet"
REGISTERED_DIR = ROOT / "data/external/exploration/ngdr_registered_downloads"
GUDMA_DIR = REGISTERED_DIR / "Gudma_CRO-23394-2017"
UKWA_DIR = REGISTERED_DIR / "Western_Ukwa_CRO-23290-2016"
GUDMA_WORKBOOK = GUDMA_DIR / "20250708115140.988_CRO-23394-2017.xlsx"
GUDMA_REPORT = GUDMA_DIR / "20250708115140.923_CRO-23394-2017.pdf"
UKWA_WORKBOOK = UKWA_DIR / "20240724141822.249_CRO-23290-2016.xlsx"
UKWA_REPORT = UKWA_DIR / "20240724141822.027_CRO-23290-2016.pdf"
NGDR_URL = ("https://github.com/ramSeraph/indian_land_features/releases/download/mining/"
            "NGDR_Mining_Exploration_Drilling_Boreholes.parquet")
NGDR_SHA256 = "B88D0FECF564E999D052BA397992405A0EC253CF764EFD7426CD2E888303AFDA"
RETRIEVED = "2026-09-29"
IBM_MP_URL = "https://ibm.gov.in/writereaddata/files/02042020163948Madhya%20Pradesh_2018.pdf"
IBM_EXPLORATION_URL = ("https://ibm.gov.in/writereaddata/files/02282019174006Exploration%20and%20development.pdf")
LOKSABHA_URL = "https://sansad.in/getFile/loksabhaquestions/annex/178/AS211.pdf?source=pqals"

FIELDS = ["hole_id", "lease", "lat", "lon", "collar_elev", "total_depth_m",
          "from_m", "to_m", "mn_pct", "fe_pct", "thickness_m",
          "provenance", "source_ref", "method", "random_seed", "block",
          "mineralized_zone_thickness_m", "thickness_type", "grade_type",
          "latitude_longitude_dms"]
ASSAY_FIELDS = [
    "hole_id", "source_hole_id", "block", "lease", "sample_id", "lithology",
    "lat", "lon", "collar_elev", "total_depth_m", "from_m", "to_m",
    "sample_interval_m", "mn_pct", "reported_mn_pct_interval_sheet", "mn_pct_raw",
    "mno_pct", "fe_pct", "fe_pct_raw", "fe2o3_pct", "sio2_pct", "p_pct",
    "p2o5_pct", "tio2_pct", "si_pct", "ti_pct", "source_footnote_marker",
    "interval_qc", "provenance", "source_ref", "method", "random_seed",
]
XLSX_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
SUMMARY_FIELDS = [
    "source_record_id", "record_type", "block", "district", "state",
    "exploration_stage", "borehole_count", "total_drilling_m",
    "ore_thickness_min_m", "ore_thickness_max_m",
    "cumulative_intersected_ore_horizon_m", "resource_tonnage",
    "resource_tonnage_unit", "average_mn_grade_pct", "resource_class",
    "notes", "provenance", "source_ref", "method", "random_seed",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def obtain_pinned_ngdr_file() -> None:
    NGDR_DIR.mkdir(parents=True, exist_ok=True)
    if NGDR_FILE.exists():
        actual = sha256_file(NGDR_FILE)
        if actual != NGDR_SHA256:
            raise ValueError(f"Pinned NGDR parquet checksum mismatch: {actual}")
        return

    request = Request(NGDR_URL, headers={"User-Agent": "MOIL-SIH-data-import/1.0"})
    with urlopen(request, timeout=60) as response:
        payload = response.read()
    actual = hashlib.sha256(payload).hexdigest().upper()
    if actual != NGDR_SHA256:
        raise ValueError(f"Downloaded NGDR parquet checksum mismatch: {actual}")
    NGDR_FILE.write_bytes(payload)


def number_or_blank(value):
    if value is None or pd.isna(value):
        return ""
    return value.item() if hasattr(value, "item") else value


def read_xlsx_sheets(path: Path) -> dict[str, list[tuple[int, dict[str, str]]]]:
    """Read worksheet cell values using the XLSX Open XML format (stdlib only)."""
    if not path.exists():
        return {}
    with zipfile.ZipFile(path) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.findall(".//m:t", XLSX_NS))
                      for si in root.findall("m:si", XLSX_NS)]
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels}
        result = {}
        for sheet in workbook.findall("m:sheets/m:sheet", XLSX_NS):
            target = rel_targets[sheet.attrib[f"{{{XLSX_NS['r']}}}id"]].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            root = ET.fromstring(book.read(target))
            rows = []
            for row in root.findall(".//m:sheetData/m:row", XLSX_NS):
                cells = {}
                for cell in row.findall("m:c", XLSX_NS):
                    coordinate = cell.attrib.get("r", "")
                    col = re.match(r"[A-Z]+", coordinate)
                    if not col:
                        continue
                    value_node = cell.find("m:v", XLSX_NS)
                    value = value_node.text if value_node is not None else ""
                    if cell.attrib.get("t") == "s" and value:
                        value = shared[int(value)]
                    inline = cell.find("m:is", XLSX_NS)
                    if inline is not None:
                        value = "".join(t.text or "" for t in inline.findall(".//m:t", XLSX_NS))
                    cells[col.group()] = str(value).strip()
                rows.append((int(row.attrib.get("r", "0")), cells))
            result[sheet.attrib["name"]] = rows
        return result


def cell_number(value) -> float | None:
    """Parse the numeric component of an XLSX cell; keep source strings separately."""
    if value is None:
        return None
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", str(value).replace(",", ""))
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def canonical_hole(value: str) -> str:
    raw = str(value or "").strip().upper()
    match = re.search(r"(GDBH|UKBH)\s*[- ]*0*(\d+)", raw)
    if not match:
        return raw
    return f"{match.group(1)}-{int(match.group(2))}"


def normalized_sample_id(value: str) -> str:
    raw = re.sub(r"\s+", "", str(value or "").upper()).replace("*", "").replace("#", "")
    raw = raw.replace("GDBH-L", "GDBH-1")
    raw = re.sub(r"(UKBH-)0+(\d)", r"\1\2", raw)
    raw = re.sub(r"(/CS/)0+(\d)", r"\1\2", raw)
    return re.sub(r"[^A-Z0-9]", "", raw)


def dms_pair_to_decimal(value: str) -> tuple[float, float]:
    """Convert the two DMS coordinates printed in the Western Ukwa collar table."""
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(value))]
    if len(nums) < 6:
        raise ValueError(f"Could not parse latitude/longitude DMS from {value!r}")
    lat_d, lat_m, lat_s, lon_d, lon_m, lon_s = nums[:6]
    if not (0 <= lat_m < 60 and 0 <= lat_s < 60 and 0 <= lon_m < 60 and 0 <= lon_s < 60):
        raise ValueError(f"Invalid DMS minutes/seconds in {value!r}")
    lat = lat_d + lat_m / 60 + lat_s / 3600
    lon = lon_d + lon_m / 60 + lon_s / 3600
    if not (20 <= lat <= 23 and 78 <= lon <= 82):
        raise ValueError(f"Converted coordinates are outside the project region: {(lat, lon)}")
    return round(lat, 8), round(lon, 8)


def source_ref(path: Path, table_rows: list[tuple[str, int]], nuid: str) -> str:
    references = "; ".join(f"worksheet '{sheet}' row {row}" for sheet, row in table_rows)
    return (f"{path.relative_to(ROOT).as_posix()}; {references}; NGDR NUID {nuid}; "
            f"downloaded/retrieved {RETRIEVED}; https://geodataindia.gov.in/guestuser")


def find_rows(sheets: dict, sheet_name: str) -> list[tuple[int, dict[str, str]]]:
    if sheet_name not in sheets:
        raise ValueError(f"Expected worksheet {sheet_name!r} is missing")
    return sheets[sheet_name]


def interval_overlap_flags(rows: list[dict]) -> tuple[int, int]:
    """Flag reported sample intervals that overlap; do not alter source depths."""
    grouped = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[row["hole_id"]].append((index, row))
    pair_count = 0
    flagged = set()
    for records in grouped.values():
        for pos, (left_index, left) in enumerate(records):
            left_from, left_to = left.get("from_m"), left.get("to_m")
            if left_from is None or left_to is None or left_to <= left_from:
                continue
            for right_index, right in records[pos + 1:]:
                right_from, right_to = right.get("from_m"), right.get("to_m")
                if right_from is None or right_to is None or right_to <= right_from:
                    continue
                if max(left_from, right_from) < min(left_to, right_to):
                    pair_count += 1
                    flagged.add(left_index)
                    flagged.add(right_index)
    for index, row in enumerate(rows):
        notes = [note for note in row.get("interval_qc", "").split(";") if note]
        if row.get("from_m") is not None and row.get("to_m") is not None:
            if row["to_m"] < row["from_m"]:
                notes.append("FROM_NOT_BEFORE_TO")
            elif index in flagged:
                notes.append("OVERLAPS_ANOTHER_REPORTED_SAMPLE")
        row["interval_qc"] = ";".join(dict.fromkeys(notes))
    return pair_count, len(flagged)


def registered_workbook_outputs(mirror_rows: list[dict]) -> tuple[list[dict], list[dict], dict] | None:
    """Build integrated hole summaries and sample assays from downloaded NGDR workbooks."""
    if not GUDMA_WORKBOOK.exists() or not UKWA_WORKBOOK.exists():
        return None
    gudma = read_xlsx_sheets(GUDMA_WORKBOOK)
    ukwa = read_xlsx_sheets(UKWA_WORKBOOK)
    mirror_by_hole = {canonical_hole(r["hole_id"]): r for r in mirror_rows}
    hole_rows: list[dict] = []
    assay_rows: list[dict] = []
    comparisons = {}

    # Gudma collars/depths are from the pinned NGDR feature layer. Interval and
    # weighted-grade facts are direct workbook values joined by the printed ID.
    gd_intersections = {}
    for row_no, cells in find_rows(gudma, "Table- VI"):
        hole = canonical_hole(cells.get("C", ""))
        if hole.startswith("GDBH-") and cell_number(cells.get("E")) is not None:
            gd_intersections[hole] = (row_no, cells)
    gd_weighted = {}
    for row_no, cells in find_rows(gudma, "Annexure-VII"):
        sample_id = cells.get("B", "")
        hole = canonical_hole(sample_id)
        if hole.startswith("GDBH-") and cell_number(cells.get("J")) is not None:
            gd_weighted[hole] = (row_no, cells)
    if len(gd_intersections) != 7 or len(gd_weighted) != 7:
        raise ValueError(f"Gudma workbook expected 7 holes/weighted grades; found {len(gd_intersections)}/{len(gd_weighted)}")

    gudma_hole_depths = {}
    thickness_discrepancies = []
    for hole, (intersection_row, cells) in sorted(gd_intersections.items()):
        collar = mirror_by_hole.get(hole)
        if collar is None:
            raise ValueError(f"NGDR mirror collar is missing for workbook hole {hole}")
        weighted_row, weighted_cells = gd_weighted[hole]
        total_depth = cell_number(cells.get("D"))
        from_m, to_m = cell_number(cells.get("E")), cell_number(cells.get("F"))
        reported_thickness = cell_number(cells.get("G"))
        mn = cell_number(weighted_cells.get("J"))
        if None in (total_depth, from_m, to_m, reported_thickness, mn):
            raise ValueError(f"Gudma workbook has incomplete intersection/grade fields for {hole}")
        calculated_width = to_m - from_m
        if abs(reported_thickness - calculated_width) > 0.005:
            thickness_discrepancies.append({
                "block": "Gudma", "hole_id": hole, "table_reported_thickness_m": reported_thickness,
                "from_to_difference_m": round(calculated_width, 6),
                "source_ref": source_ref(GUDMA_WORKBOOK, [("Table- VI", intersection_row)], "CRO-23394-2017"),
            })
        gudma_hole_depths[hole] = total_depth
        refs = [
            f"{NGDR_FILE.relative_to(ROOT).as_posix()}; feature borehole_name={hole}; "
            f"{NGDR_URL}; retrieved {RETRIEVED}",
            source_ref(GUDMA_WORKBOOK, [("Table- VI", intersection_row), ("Annexure-VII", weighted_row)],
                       "CRO-23394-2017"),
        ]
        hole_rows.append({
            **{k: collar.get(k, "") for k in ("hole_id", "lat", "lon", "collar_elev")},
            "lease": "", "block": "Gudma", "total_depth_m": total_depth,
            "from_m": from_m, "to_m": to_m, "mn_pct": mn, "fe_pct": "",
            "thickness_m": reported_thickness,
            "mineralized_zone_thickness_m": reported_thickness,
            "thickness_type": "reported mineralized-zone thickness; includes ore and interbanded waste",
            "grade_type": "reported weighted average from Annexure-VII",
            "provenance": "DERIVED", "source_ref": " || ".join(refs),
            "method": "Joined the NGDR collar feature to Table- VI and Annexure-VII by canonical borehole ID. All depths, thickness and grade are transcribed source values; no grade or thickness was modeled.",
            "random_seed": "",
        })

    # Gudma Table-V holds intervals/lithology and the rounded Mn grade.
    # Annexure-V repeats each sample in an oxide block and an elemental block.
    gd_assays_by_id = defaultdict(list)
    for row_no, cells in find_rows(gudma, "Annexure-V"):
        sample_id = cells.get("B", "")
        if sample_id:
            gd_assays_by_id[normalized_sample_id(sample_id)].append((row_no, cells))
    gd_table_rows = [
        (row_no, cells) for row_no, cells in find_rows(gudma, "Table-V")[2:]
        if cells.get("E") and cell_number(cells.get("C")) is not None and
        cell_number(cells.get("D")) is not None
    ]
    gd_grade_differences = []
    gd_seen = set()
    for row_no, cells in gd_table_rows:
        sample_id = cells["E"]
        key = normalized_sample_id(sample_id)
        matched = gd_assays_by_id.get(key, [])
        oxide_rows = [(n, d) for n, d in matched if cell_number(d.get("H")) is not None]
        element_rows = [(n, d) for n, d in matched if cell_number(d.get("J")) is not None]
        if len(oxide_rows) != 1 or len(element_rows) != 1 or key in gd_seen:
            raise ValueError(f"Gudma sample crosswalk failed for {sample_id!r}: {len(oxide_rows)} oxide, {len(element_rows)} elemental")
        gd_seen.add(key)
        oxide_no, oxide = oxide_rows[0]
        element_no, element = element_rows[0]
        hole = canonical_hole(cells.get("B", ""))
        summary = next((r for r in hole_rows if r["hole_id"] == hole), None)
        if summary is None:
            raise ValueError(f"No Gudma hole summary for sample {sample_id}")
        grade = cell_number(element.get("J"))
        reported_grade = cell_number(cells.get("G"))
        if grade is None or reported_grade is None:
            raise ValueError(f"Gudma Mn grade is missing for sample {sample_id}")
        gd_grade_differences.append(abs(grade - reported_grade))
        assay_rows.append({
            "hole_id": hole, "source_hole_id": cells.get("B", ""), "block": "Gudma", "lease": "",
            "sample_id": sample_id, "lithology": cells.get("F", ""),
            "lat": cell_number(oxide.get("C")), "lon": cell_number(oxide.get("D")),
            "collar_elev": summary.get("collar_elev", ""), "total_depth_m": summary["total_depth_m"],
            "from_m": cell_number(cells.get("C")), "to_m": cell_number(cells.get("D")),
            "sample_interval_m": round(cell_number(cells.get("D")) - cell_number(cells.get("C")), 6),
            "mn_pct": grade, "reported_mn_pct_interval_sheet": reported_grade,
            "mn_pct_raw": element.get("J", ""), "mno_pct": cell_number(oxide.get("H")),
            "fe_pct": cell_number(element.get("L")), "fe_pct_raw": element.get("L", ""),
            "fe2o3_pct": cell_number(oxide.get("F")), "sio2_pct": cell_number(oxide.get("E")),
            "p_pct": cell_number(element.get("M")), "p2o5_pct": cell_number(oxide.get("G")),
            "tio2_pct": cell_number(oxide.get("I")), "si_pct": cell_number(element.get("K")),
            "ti_pct": cell_number(element.get("N")), "source_footnote_marker": "",
            "interval_qc": "", "provenance": "DERIVED",
            "source_ref": source_ref(GUDMA_WORKBOOK,
                [("Table-V", row_no), ("Annexure-V", oxide_no), ("Annexure-V", element_no)],
                "CRO-23394-2017"),
            "method": "Matched Table-V sample intervals to the paired oxide and elemental rows in Annexure-V by normalized sample ID. mn_pct and fe_pct use elemental percent columns (not MnO or Fe2O3); sample_interval_m is to_m minus from_m. No assays were estimated.",
            "random_seed": "",
        })
    if len(gd_table_rows) != 37:
        raise ValueError(f"Expected 37 Gudma core sample intervals in Table-V; found {len(gd_table_rows)}")

    # Western Ukwa collar coordinates are printed in DMS in Table-10. Convert
    # only coordinates; retain the exact report text in each source reference.
    ukwa_collars = {}
    for row_no, cells in find_rows(ukwa, "Table-10"):
        source_id = cells.get("B", "").strip()
        hole = canonical_hole(source_id)
        if not hole.startswith("UKBH-"):
            continue
        lat, lon = dms_pair_to_decimal(cells.get("C", ""))
        elev = cell_number(cells.get("D"))
        total_depth = cell_number(cells.get("G"))
        if elev is None or total_depth is None:
            raise ValueError(f"Western Ukwa collar table is incomplete for {hole}")
        ukwa_collars[hole] = {"row": row_no, "source_hole_id": source_id, "lat": lat,
                              "lon": lon, "elev": elev, "depth": total_depth,
                              "dms": cells.get("C", "")}
    if len(ukwa_collars) != 6:
        raise ValueError(f"Expected 6 Western Ukwa collar records in Table-10; found {len(ukwa_collars)}")

    ukwa_intersections = {}
    for row_no, cells in find_rows(ukwa, "Table-14"):
        hole = canonical_hole(cells.get("C", ""))
        if hole.startswith("UKBH-") and cells.get("E"):
            depths = [float(v) for v in re.findall(r"\d+(?:\.\d+)?", cells["E"])]
            if len(depths) < 2:
                raise ValueError(f"Could not parse Western Ukwa interval for {hole}: {cells['E']}")
            ukwa_intersections[hole] = (row_no, cells, depths[0], depths[1])
    ukwa_ore_widths = {}
    for row_no, cells in find_rows(ukwa, "Table-7"):
        hole = canonical_hole(cells.get("C", ""))
        if hole.startswith("UKBH-") and cells.get("F"):
            ukwa_ore_widths[hole] = (row_no, cells)
    ukwa_weighted = {}
    for row_no, cells in find_rows(ukwa, "Annexure II(B)"):
        hole = canonical_hole(cells.get("B", ""))
        if hole.startswith("UKBH-") and cell_number(cells.get("F")) is not None:
            ukwa_weighted[hole] = (row_no, cells)
    if not (len(ukwa_intersections) == len(ukwa_ore_widths) == len(ukwa_weighted) == 6):
        raise ValueError("Western Ukwa workbook does not contain complete per-hole intersection/grade tables")

    ukwa_hole_depths = {}
    table7_grade_differences = []
    for hole, collar in sorted(ukwa_collars.items()):
        intersection_row, intersection, from_m, to_m = ukwa_intersections[hole]
        ore_row, ore_cells = ukwa_ore_widths[hole]
        grade_row, grade_cells = ukwa_weighted[hole]
        mineralized_thickness = cell_number(intersection.get("F"))
        ore_thickness = cell_number(ore_cells.get("F"))
        total_depth = collar["depth"]
        mn = cell_number(grade_cells.get("F"))
        fe = cell_number(grade_cells.get("E"))
        if None in (mineralized_thickness, ore_thickness, mn, fe):
            raise ValueError(f"Western Ukwa intersection/grade is incomplete for {hole}")
        if abs(mineralized_thickness - (to_m - from_m)) > 0.005:
            thickness_discrepancies.append({
                "block": "Western Ukwa", "hole_id": hole,
                "table_reported_thickness_m": mineralized_thickness,
                "from_to_difference_m": round(to_m - from_m, 6),
                "source_ref": source_ref(UKWA_WORKBOOK, [("Table-14", intersection_row)], "CRO-23290-2016"),
            })
        ukwa_hole_depths[hole] = total_depth
        reported_fraction = cell_number(ore_cells.get("G"))
        if reported_fraction is not None:
            table7_grade_differences.append(abs(reported_fraction * 100 - mn))
        refs = source_ref(UKWA_WORKBOOK,
            [("Table-10", collar["row"]), ("Table-14", intersection_row),
             ("Table-7", ore_row), ("Annexure II(B)", grade_row)], "CRO-23290-2016")
        hole_rows.append({
            "hole_id": hole, "lease": "", "block": "Western Ukwa", "lat": collar["lat"],
            "lon": collar["lon"], "collar_elev": collar["elev"], "total_depth_m": total_depth,
            "from_m": from_m, "to_m": to_m, "mn_pct": mn, "fe_pct": fe,
            "thickness_m": ore_thickness, "mineralized_zone_thickness_m": mineralized_thickness,
            "thickness_type": "actual ore thickness from Table-7; mineralized zone also retained separately",
            "grade_type": "reported per-hole weighted average from Annexure II(B)",
            "latitude_longitude_dms": collar["dms"], "provenance": "DERIVED",
            "source_ref": refs,
            "method": "Joined Table-10 collar, Table-14 mineralized-zone interval, Table-7 actual ore thickness and Annexure II(B) weighted assays by borehole ID. Converted the printed DMS collar coordinates to decimal degrees; reported assay and thickness numbers were not modeled.",
            "random_seed": "",
        })

    # Western Ukwa Table-6 sample intervals pair one-to-one with Annexure II
    # chemical assays. Keep the footnote marker so core-loss assays stay flagged.
    ukwa_assays_by_id = defaultdict(list)
    for row_no, cells in find_rows(ukwa, "Annexure II"):
        sample_id = cells.get("B", "")
        if sample_id:
            ukwa_assays_by_id[normalized_sample_id(sample_id)].append((row_no, cells))
    wk_table_rows = [
        (row_no, cells) for row_no, cells in find_rows(ukwa, "Table-6")[2:]
        if cells.get("E") and cell_number(cells.get("C")) is not None and
        cell_number(cells.get("D")) is not None
    ]
    wk_seen = set()
    wk_mn_mismatches = []
    for row_no, cells in wk_table_rows:
        sample_id = cells["E"]
        key = normalized_sample_id(sample_id)
        matched = ukwa_assays_by_id.get(key, [])
        if len(matched) != 1 or key in wk_seen:
            raise ValueError(f"Western Ukwa sample crosswalk failed for {sample_id!r}: {len(matched)} assay rows")
        wk_seen.add(key)
        assay_no, assay = matched[0]
        hole = canonical_hole(sample_id)
        collar = ukwa_collars.get(hole)
        if collar is None:
            raise ValueError(f"Western Ukwa sample has no collar record: {sample_id}")
        grade = cell_number(assay.get("H"))
        reported_grade = cell_number(cells.get("G"))
        if grade is None or reported_grade is None:
            raise ValueError(f"Western Ukwa Mn assay is missing for sample {sample_id}")
        if abs(grade - reported_grade) > 0.0001:
            wk_mn_mismatches.append({"sample_id": sample_id, "table6_mn_pct": reported_grade,
                                     "annexure_mn_pct": grade})
        raw_mn = assay.get("H", "")
        marker = "".join(ch for ch in raw_mn if ch in "#*")
        qc = []
        if "#" in marker:
            qc.append("DILUTED_DUE_TO_CORE_LOSS_NOT_USED_IN_RESOURCE_CALCULATION")
        if "*" in marker:
            qc.append("MARKED_AS_ORE_USED_FOR_WEIGHTED_AVERAGE")
        assay_rows.append({
            "hole_id": hole, "source_hole_id": cells.get("B", "") or collar["source_hole_id"],
            "block": "Western Ukwa", "lease": "", "sample_id": sample_id,
            "lithology": cells.get("F", ""), "lat": collar["lat"], "lon": collar["lon"],
            "collar_elev": collar["elev"], "total_depth_m": collar["depth"],
            "from_m": cell_number(cells.get("C")), "to_m": cell_number(cells.get("D")),
            "sample_interval_m": round(cell_number(cells.get("D")) - cell_number(cells.get("C")), 6),
            "mn_pct": grade, "reported_mn_pct_interval_sheet": reported_grade,
            "mn_pct_raw": raw_mn, "mno_pct": cell_number(re.sub(r"[#*]", "", assay.get("E", ""))),
            "fe_pct": cell_number(assay.get("K")), "fe_pct_raw": assay.get("K", ""),
            "fe2o3_pct": cell_number(assay.get("D")), "sio2_pct": cell_number(assay.get("C")),
            "p_pct": cell_number(assay.get("J")), "p2o5_pct": cell_number(assay.get("F")),
            "tio2_pct": cell_number(assay.get("G")), "si_pct": cell_number(assay.get("L")),
            "ti_pct": "", "source_footnote_marker": marker,
            "interval_qc": ";".join(qc), "provenance": "DERIVED",
            "source_ref": source_ref(UKWA_WORKBOOK,
                [("Table-6", row_no), ("Annexure II", assay_no), ("Table-10", collar["row"])],
                "CRO-23290-2016"),
            "method": "Matched Table-6 sample intervals to Annexure II chemistry using normalized sample ID and joined the Table-10 collar. Numeric assays were parsed from the report cells; original Mn marker is preserved. sample_interval_m is to_m minus from_m. No assays were estimated.",
            "random_seed": "",
        })
    if len(gd_seen) != len(gd_table_rows) or len(wk_seen) != len(wk_table_rows):
        raise ValueError("A source sample interval did not crosswalk to an assay row")
    if len(wk_table_rows) != 51:
        raise ValueError(f"Expected 51 Western Ukwa core sample intervals; found {len(wk_table_rows)}")

    overlap_pairs, overlap_rows = interval_overlap_flags(assay_rows)
    for row in assay_rows:
        row["interval_qc"] = ";".join(filter(None, [row.get("interval_qc", "")]))
    source_grade_check = {
        "gudma_table_v_vs_annexure_v_mn_pct_max_abs_difference": round(max(gd_grade_differences), 6),
        "western_table_6_vs_annexure_ii_mn_pct_mismatch_count": len(wk_mn_mismatches),
        "western_table_7_fraction_times_100_vs_annexure_ii_b_max_abs_difference": round(max(table7_grade_differences), 6),
        "western_mn_mismatches": wk_mn_mismatches,
    }
    audit = {
        "registered_downloads": [
            {"block": "Gudma", "nuid": "CRO-23394-2017",
             "workbook": GUDMA_WORKBOOK.relative_to(ROOT).as_posix(),
             "workbook_sha256": sha256_file(GUDMA_WORKBOOK),
             "report_pdf": GUDMA_REPORT.relative_to(ROOT).as_posix() if GUDMA_REPORT.exists() else None,
             "report_sha256": sha256_file(GUDMA_REPORT) if GUDMA_REPORT.exists() else None},
            {"block": "Western Ukwa", "nuid": "CRO-23290-2016",
             "workbook": UKWA_WORKBOOK.relative_to(ROOT).as_posix(),
             "workbook_sha256": sha256_file(UKWA_WORKBOOK),
             "report_pdf": UKWA_REPORT.relative_to(ROOT).as_posix() if UKWA_REPORT.exists() else None,
             "report_sha256": sha256_file(UKWA_REPORT) if UKWA_REPORT.exists() else None},
        ],
        "collar_rows": len(hole_rows),
        "gudma_collars": sum(r["block"] == "Gudma" for r in hole_rows),
        "western_ukwa_collars": sum(r["block"] == "Western Ukwa" for r in hole_rows),
        "assay_interval_rows": len(assay_rows),
        "assay_intervals_by_block": {
            "Gudma": sum(r["block"] == "Gudma" for r in assay_rows),
            "Western Ukwa": sum(r["block"] == "Western Ukwa" for r in assay_rows),
        },
        "gudma_drilled_depth_sum_m": round(sum(gudma_hole_depths.values()), 3),
        "western_ukwa_drilled_depth_sum_m": round(sum(ukwa_hole_depths.values()), 3),
        "gudma_borehole_ids": sorted(k for k in gudma_hole_depths),
        "western_ukwa_borehole_ids": sorted(k for k in ukwa_hole_depths),
        "sample_interval_overlap_pair_count": overlap_pairs,
        "sample_interval_rows_flagged_overlap": overlap_rows,
        "overlapping_sample_ids": sorted(r["sample_id"] for r in assay_rows
                                          if "OVERLAPS_ANOTHER_REPORTED_SAMPLE" in r.get("interval_qc", "")),
        "reversed_intervals": [{"hole_id": r["hole_id"], "sample_id": r["sample_id"],
                                "from_m": r["from_m"], "to_m": r["to_m"]}
                               for r in assay_rows if "FROM_NOT_BEFORE_TO" in r.get("interval_qc", "")],
        "reported_intersection_thickness_discrepancies": thickness_discrepancies,
        "sample_interval_rows_with_to_not_after_from": sum(r["interval_qc"].startswith("FROM_NOT_BEFORE_TO") or ";FROM_NOT_BEFORE_TO" in r["interval_qc"] for r in assay_rows),
        "source_grade_checks": source_grade_check,
        "notes": [
            "Detailed worksheets contain both current core intervals and non-hole check samples; only intervals with borehole/sample ID and numeric from/to were imported.",
            "The Gudma Annexure-V repeats each sample in oxide and elemental result blocks; both rows are joined and elemental Mn%/Fe% are kept distinct from MnO%/Fe2O3%.",
            "Western Ukwa # and * assay markers are retained; the report says # denotes dilution from core loss and * marks samples used in weighted-average calculations.",
            "Sample intervals are not necessarily ore thickness. Overlaps and a reversed interval are retained and flagged rather than repaired.",
            "Western Ukwa DMS coordinates were converted to decimal degrees; the original DMS text is retained in the hole summary and source reference.",
        ],
    }
    return hole_rows, assay_rows, audit


def write_assay_csv(path: Path, new_rows: list[dict]) -> list[dict]:
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_files = (GUDMA_WORKBOOK.name, UKWA_WORKBOOK.name)
    existing = []
    if path.exists():
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            existing = list(csv.DictReader(f))
    existing = [r for r in existing if not any(name in r.get("source_ref", "") for name in generated_files)]
    rows = existing + new_rows
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ASSAY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def public_collar_rows() -> tuple[list[dict], dict]:
    obtain_pinned_ngdr_file()
    df = pd.read_parquet(NGDR_FILE)
    grid = pd.read_csv(GRID_SAMPLES, usecols=["lat", "lon"])
    bounds = {
        "lat_min": float(grid["lat"].min()), "lat_max": float(grid["lat"].max()),
        "lon_min": float(grid["lon"].min()), "lon_max": float(grid["lon"].max()),
        "crs": "EPSG:4326",
    }

    manganese = df["commodity_name"].fillna("").str.contains("manganese", case=False)
    lat = pd.to_numeric(df["latitude_dd"], errors="coerce")
    lon = pd.to_numeric(df["longitude_dd"], errors="coerce")
    inside = lat.between(bounds["lat_min"], bounds["lat_max"]) & lon.between(
        bounds["lon_min"], bounds["lon_max"])
    selected = df.loc[manganese & inside].copy()
    selected = selected.sort_values("borehole_name", kind="stable")

    if len(selected) != 7 or not selected["block_name_other"].fillna("").str.contains(
            "Gudma", case=False).all():
        raise ValueError(
            "Expected the seven Gudma manganese collars inside the project grid; "
            f"found {len(selected)} rows. Review the NGDR release or grid bounds."
        )

    source_rows = []
    for _, row in selected.iterrows():
        hole_name = str(row["borehole_name"])
        unique_id = str(row["unique_id"])
        source_code = str(row["source_of_data"])
        block_name = "" if pd.isna(row["block_name_other"]) else str(row["block_name_other"])
        prospect_name = "" if pd.isna(row["prospect_name_other"]) else str(row["prospect_name_other"])
        source_stage = "" if pd.isna(row["stage_of_investigation"]) else str(row["stage_of_investigation"])
        source_ref = (
            f"{NGDR_FILE.name}; feature borehole_name={hole_name}, unique_id={unique_id}, "
            f"block_name_other={block_name}, prospect_name_other={prospect_name}, "
            f"stage_of_investigation={source_stage or 'blank'}, source_of_data={source_code}; "
            f"{NGDR_URL}; retrieved {RETRIEVED}"
        )
        source_rows.append({
            "hole_id": hole_name,
            # This layer identifies an exploration block/prospect, not the mine lease.
            "lease": "",
            "lat": number_or_blank(row["latitude_dd"]),
            "lon": number_or_blank(row["longitude_dd"]),
            "collar_elev": number_or_blank(row["rl_collar_m"]),
            "total_depth_m": number_or_blank(row["length_m"]),
            "from_m": "", "to_m": "", "mn_pct": "", "fe_pct": "",
            "thickness_m": "", "provenance": "SOURCE", "source_ref": source_ref,
            "method": "", "random_seed": "",
        })

    depths = pd.to_numeric(selected["length_m"], errors="coerce")
    audit = {
        "source_file": NGDR_FILE.relative_to(ROOT).as_posix(),
        "source_url": NGDR_URL,
        "retrieved": RETRIEVED,
        "sha256": NGDR_SHA256,
        "national_source_rows": int(len(df)),
        "manganese_collar_rows_inside_project_bbox": int(len(selected)),
        "selected_hole_ids": selected["borehole_name"].astype(str).tolist(),
        "selected_ngdr_ids": selected["unique_id"].astype(str).tolist(),
        "drilled_length_sum_m": round(float(depths.sum()), 3),
        "grid_bounds": bounds,
        "source_data_code": sorted(selected["source_of_data"].dropna().astype(str).unique().tolist()),
        "source_stage_values": {str(k) if k else "MISSING": int(v) for k, v in
                                selected["stage_of_investigation"].fillna("").value_counts().items()},
        "license_note": "GitHub release states CC0 1.0 and requests attribution to datameet and the original government source where possible; verify official NGDR reuse terms before external publication.",
    }
    return source_rows, audit


def write_source_csv(path: Path, new_rows: list[dict]) -> list[dict]:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if path.exists():
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            existing = list(csv.DictReader(f))
    # Replace only rows generated from these known sources; preserve other sources.
    generated_sources = (NGDR_FILE.name, GUDMA_WORKBOOK.name, UKWA_WORKBOOK.name)
    existing = [r for r in existing if not any(name in r.get("source_ref", "") for name in generated_sources)]
    rows = existing + new_rows
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def published_summary_rows() -> list[dict]:
    return [
        {
            "source_record_id": "IBM-2018-MP-GUDMA-DRILLING",
            "record_type": "drilling_summary", "block": "Gudma", "district": "Balaghat",
            "state": "Madhya Pradesh", "exploration_stage": "G3",
            "borehole_count": 7, "total_drilling_m": 1009.7,
            "ore_thickness_min_m": 0.25, "ore_thickness_max_m": 1.38,
            "cumulative_intersected_ore_horizon_m": 5.74,
            "resource_tonnage": "", "resource_tonnage_unit": "",
            "average_mn_grade_pct": "", "resource_class": "",
            "notes": "Published aggregate; 5.74 m includes manganiferous quartzite.",
            "provenance": "SOURCE",
            "source_ref": (f"IBM_Indian_Minerals_Yearbook_2018_Madhya_Pradesh.pdf; Table 3, printed p. 11-7 (PDF p. 7); {IBM_MP_URL}; retrieved {RETRIEVED}"),
            "method": "", "random_seed": "",
        },
        {
            "source_record_id": "IBM-2017-UKWA-DRILLING",
            "record_type": "drilling_summary", "block": "Western Ukwa", "district": "Balaghat",
            "state": "Madhya Pradesh", "exploration_stage": "G2",
            "borehole_count": 6, "total_drilling_m": 1071.35,
            "ore_thickness_min_m": 0.15, "ore_thickness_max_m": 3.61,
            "cumulative_intersected_ore_horizon_m": 10.015,
            "resource_tonnage": "", "resource_tonnage_unit": "",
            "average_mn_grade_pct": "", "resource_class": "",
            "notes": "Published aggregate; no hole-wise assay intervals in this summary.",
            "provenance": "SOURCE",
            "source_ref": (f"IBM_Exploration_and_Development_2017.pdf; Manganese Ore/GSI, PDF p. 34, Western Ukwa paragraph; {IBM_EXPLORATION_URL}; retrieved {RETRIEVED}"),
            "method": "", "random_seed": "",
        },
        {
            "source_record_id": "LOKSABHA-2017-18-GUDMA-RESOURCE",
            "record_type": "resource_summary", "block": "Gudma", "district": "Balaghat",
            "state": "Madhya Pradesh", "exploration_stage": "G3",
            "borehole_count": "", "total_drilling_m": "",
            "ore_thickness_min_m": "", "ore_thickness_max_m": "",
            "cumulative_intersected_ore_horizon_m": "",
            "resource_tonnage": 0.168, "resource_tonnage_unit": "million tonnes",
            "average_mn_grade_pct": 21.65, "resource_class": "",
            "notes": "Published rounded resource and grade; this is not an assay interval dataset.",
            "provenance": "SOURCE",
            "source_ref": (f"LokSabha_Mn_resources_MP_annex.pdf; Annexure-II, p. 8, row 15; {LOKSABHA_URL}; retrieved {RETRIEVED}"),
            "method": "", "random_seed": "",
        },
        {
            "source_record_id": "LOKSABHA-2016-17-UKWA-RESOURCE",
            "record_type": "resource_summary", "block": "Ukwa (annexure scope)", "district": "Balaghat",
            "state": "Madhya Pradesh", "exploration_stage": "G2",
            "borehole_count": "", "total_drilling_m": "",
            "ore_thickness_min_m": "", "ore_thickness_max_m": "",
            "cumulative_intersected_ore_horizon_m": "",
            "resource_tonnage": 2.60, "resource_tonnage_unit": "million tonnes",
            "average_mn_grade_pct": 35.138, "resource_class": "",
            "notes": "Annexure calls the block Ukwa; do not assume identical scope to the Western Ukwa drilling summary.",
            "provenance": "SOURCE",
            "source_ref": (f"LokSabha_Mn_resources_MP_annex.pdf; Annexure-II, p. 8, row 5; {LOKSABHA_URL}; retrieved {RETRIEVED}"),
            "method": "", "random_seed": "",
        },
    ]


def write_summaries() -> list[dict]:
    path = OUT / "published_drilling_summaries.csv"
    rows = published_summary_rows()
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    SYN.mkdir(parents=True, exist_ok=True)
    src_path = OUT / "boreholes_source.csv"
    syn_path = SYN / "boreholes_synthetic.csv"
    # Keep the documented source/synthetic schemas available even if empty.
    if not syn_path.exists():
        with syn_path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
    else:
        with syn_path.open("r", newline="", encoding="utf-8-sig") as f:
            synthetic_rows = list(csv.DictReader(f))
        if not synthetic_rows:
            with syn_path.open("w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=FIELDS).writeheader()

    mirror_rows, ngdr_audit = public_collar_rows()
    registered = registered_workbook_outputs(mirror_rows)
    if registered:
        hole_rows, assay_rows, workbook_audit = registered
        output_hole_rows = hole_rows
    else:
        output_hole_rows, assay_rows, workbook_audit = mirror_rows, [], None
    all_source_rows = write_source_csv(src_path, output_hole_rows)
    assay_path = OUT / "borehole_assays_source.csv"
    all_assay_rows = write_assay_csv(assay_path, assay_rows)
    summaries = write_summaries()

    pdf_audit = []
    table_candidates = []
    pdf_paths = [] if workbook_audit else sorted(PDF_DIR.glob("*.pdf"))
    for path in pdf_paths:
        pages_scanned = 0
        hits = []
        try:
            with pdfplumber.open(path) as pdf:
                pages_scanned = len(pdf.pages)
                for page_no, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    low = text.lower()
                    drilling_terms = any(t in low for t in ("borehole", "bore hole", "drill hole", "assay interval"))
                    if drilling_terms:
                        hits.append(page_no)
                    if not drilling_terms:
                        continue
                    for table in page.extract_tables() or []:
                        flat = " ".join(str(x or "") for row in table for x in row).lower()
                        has_interval_header = all(k in flat for k in ("from", "to"))
                        has_grade_header = any(k in flat for k in ("mn%", "mn %", "manganese"))
                        has_hole_header = any(k in flat for k in ("borehole id", "borehole no", "borehole number",
                                                                   "bh no", "hole id", "hole no"))
                        if has_interval_header and has_grade_header and has_hole_header:
                            table_candidates.append({"file": path.name, "page": page_no,
                                                     "rows": len(table)})
        except Exception as exc:
            pdf_audit.append({"file": path.name, "error": str(exc)})
            continue
        pdf_audit.append({"file": path.name, "pages_scanned": pages_scanned,
                          "pages_with_drilling_terms": hits,
                          "candidate_interval_tables": [t for t in table_candidates if t["file"] == path.name]})

    manifest_rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8-sig"))) if MANIFEST.exists() else []
    unavailable_ngdr = [r for r in manifest_rows if "required" in r.get("download_status", "").lower()]
    existing_summaries = list(csv.DictReader(SUMMARY_SOURCE.open(encoding="utf-8-sig"))) if SUMMARY_SOURCE.exists() else []
    expected_depth_m = 1009.7
    actual_depth_m = float(ngdr_audit["drilled_length_sum_m"])
    ukwa_expected_depth_m = 1071.35
    if workbook_audit:
        status = "SOURCE_COLLARS_AND_ASSAYS_IMPORTED"
        ukwa_actual_depth_m = workbook_audit["western_ukwa_drilled_depth_sum_m"]
        assay_grades = defaultdict(list)
        for row in all_assay_rows:
            if row.get("mn_pct") not in (None, ""):
                assay_grades[row["block"]].append(float(row["mn_pct"]))
        grade_ranges = {
            block: {"sample_count": len(values), "min_mn_pct": min(values), "max_mn_pct": max(values),
                    "unweighted_mean_mn_pct": round(sum(values) / len(values), 6),
                    "method": "Descriptive range and arithmetic mean over reported core-sample Mn% rows; samples include ore and non-ore lithologies and are not a resource grade.",
                    "provenance": "DERIVED",
                    "source_ref": (f"{GUDMA_WORKBOOK.name}; Table-V/Annexure-V; NGDR CRO-23394-2017; retrieved {RETRIEVED}" if block == "Gudma"
                                   else f"{UKWA_WORKBOOK.name}; Table-6/Annexure II; NGDR CRO-23290-2016; retrieved {RETRIEVED}")}
            for block, values in assay_grades.items()
        }
    else:
        status = "PARTIAL_SOURCE_COLLARS_ONLY_NO_ASSAYS"
        ukwa_actual_depth_m = None
        grade_ranges = {}
    result = {
        "gap": 1,
        "status": status,
        "source_rows": len(all_source_rows),
        "imported_ngdr_collar_rows": len(mirror_rows),
        "imported_workbook_hole_rows": len(output_hole_rows) if workbook_audit else 0,
        "synthetic_rows": 0,
        "assay_interval_rows": len(all_assay_rows),
        "source_csv": str(src_path.relative_to(ROOT)),
        "assay_csv": str(assay_path.relative_to(ROOT)),
        "published_summary_csv": "data/processed/published_drilling_summaries.csv",
        "synthetic_csv": str(syn_path.relative_to(ROOT)),
        "ngdr_source_audit": ngdr_audit,
        "registered_workbook_audit": workbook_audit,
        "assay_grade_ranges": grade_ranges,
        "validation": {
            "seven_gudma_collars_found_inside_grid": len(mirror_rows) == 7,
            "ngdr_depth_sum_m": actual_depth_m,
            "ibm_2018_published_depth_sum_m": expected_depth_m,
            "depth_sum_matches_published_total": abs(actual_depth_m - expected_depth_m) < 0.05,
            "depth_difference_m": round(actual_depth_m - expected_depth_m, 3),
            "western_ukwa_depth_sum_m": ukwa_actual_depth_m,
            "ibm_2017_western_ukwa_published_depth_sum_m": ukwa_expected_depth_m if workbook_audit else None,
            "western_ukwa_depth_sum_matches_published_total": (abs(ukwa_actual_depth_m - ukwa_expected_depth_m) < 0.05) if workbook_audit else None,
            "interval_assays_available": bool(all_assay_rows),
            "assay_rows_have_source_reference_and_method": all(
                r.get("provenance") == "DERIVED" and r.get("source_ref") and r.get("method")
                for r in all_assay_rows),
            "all_assay_sample_ids_crosswalked": bool(workbook_audit) and len(all_assay_rows) == 88,
            "synthetic_assays_generated": False,
        },
        "published_summary_records": summaries,
        "existing_summary_records_preserved_separately": existing_summaries,
        "published_summary_discrepancy_note": ("The pre-existing extracted summary reports Gudma drilling as 1009.53 m, 5.73 m cumulative horizon, and 0.24-1.38 m thickness; the separate IBM 2018 table reports 1009.7 m, 5.74 m, and 0.25-1.38 m. Both source-specific records are retained; the collar depths match the IBM 2018 total. The GitHub mirror labels six collars G2 and leaves one stage blank, while IBM/Lok Sabha summaries identify Gudma as G3; preserve these source-specific stage values rather than reconciling them without the primary workbook."),
        "source_pdf_audit": pdf_audit,
        "pdf_scan_note": ("The official NGDR XLSX tables were extracted directly; the older broad scan of unrelated reference PDFs was skipped on this run." if workbook_audit else "Reference PDFs were scanned for tables that might contain interval assays."),
        "candidate_interval_tables": table_candidates,
        "ngdr_file_assets_still_registered_user_required": [
            {k: r.get(k, "") for k in ("block", "accession", "file_kind", "portal_file_path", "expected_contents")}
            for r in unavailable_ngdr
        ],
        "synthetic_summary_validation": {"status": "NO_SYNTHETIC_REQUIRED_SOURCE_ASSAYS_AVAILABLE" if workbook_audit else "NOT_RUN_NO_SYNTHETIC_ROWS",
            "tolerance_fraction": 0.05,
            "reason": "No synthetic collars or assays were generated because official NGDR core-sample intervals and assays were recovered from both registered-user workbooks." if workbook_audit else "No synthetic collars or grade intervals were generated; official workbook files are not staged in the project."},
        "reason": ("Official NGDR workbooks now provide Gudma and Western Ukwa assay intervals and per-hole intersections. Thirteen located collars and 88 sample-assay intervals are available. Reported overlapping Gudma samples and the Western Ukwa interval anomaly remain source-faithful and flagged. No synthetic assays were generated." if workbook_audit else "The pinned NGDR-attributed mirror supplies seven Gudma collar locations, collar elevations, and total depths but no assay intervals; the registered-user workbooks have not been staged."),
        "method": "SHA-256 verified the pinned NGDR-attributed Parquet release, parsed the registered NGDR XLSX workbooks using the Open XML format, joined sample intervals to laboratory chemistry by normalized sample ID, and converted published Western Ukwa DMS collar coordinates to decimal degrees. No assay grades were estimated.",
        "source_ref": [
            f"{NGDR_FILE.name}; {NGDR_URL}; retrieved {RETRIEVED}; SHA-256 {NGDR_SHA256}",
            f"IBM_Indian_Minerals_Yearbook_2018_Madhya_Pradesh.pdf, Table 3, printed p. 11-7 (PDF p. 7); {IBM_MP_URL}; retrieved {RETRIEVED}",
            f"IBM_Exploration_and_Development_2017.pdf, Manganese Ore/GSI, PDF p. 34; {IBM_EXPLORATION_URL}; retrieved {RETRIEVED}",
            f"LokSabha_Mn_resources_MP_annex.pdf, Annexure-II, p. 8; {LOKSABHA_URL}; retrieved {RETRIEVED}",
            f"{GUDMA_WORKBOOK.relative_to(ROOT).as_posix()}; Table-V, Table- VI, Annexure-V and Annexure-VII; NGDR NUID CRO-23394-2017; retrieved {RETRIEVED}",
            f"{UKWA_WORKBOOK.relative_to(ROOT).as_posix()}; Table-6, Table-7, Table-10, Table-14, Annexure II and Annexure II(B); NGDR NUID CRO-23290-2016; retrieved {RETRIEVED}",
            "data/external/exploration/ngdr_report_manifest.csv; workbook/PDF rows marked downloaded; georeferenced map/GDB files remain registered-user downloads; retrieved 2026-09-29",
        ],
    }
    (OUT / "borehole_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))

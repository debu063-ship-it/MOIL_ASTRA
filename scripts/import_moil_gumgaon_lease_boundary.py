"""Extract the published Gumgaon lease-pillar coordinates from MOIL's PFR.

The polygon is DERIVED by connecting the published pillar coordinates in numeric
order. The applicant report's mapped area fields conflict (126.84 vs 126.46 ha),
so both are retained and the computed geometry area is reported separately.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

import pdfplumber
from pyproj import Geod
from shapely.geometry import Polygon, mapping

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/external/exploration/public_sources/MOIL_Gumgaon_Khodegaon_Tegai_PFR_2017.pdf"
REGISTER = ROOT / "data/processed/moil_manganese_lease_register_2025.csv"
POINTS_OUT = ROOT / "data/processed/gumgaon_lease_pillars_source.csv"
POLYGON_OUT = ROOT / "data/processed/gumgaon_lease_boundary.geojson"
AUDIT_OUT = ROOT / "data/processed/gumgaon_lease_boundary_validation.json"
SOURCE_URL = "https://environmentclearance.nic.in/writereaddata/Online/TOR/01_Aug_2017_113719740WC70Q0QJPFR.pdf"
RETRIEVED = "2026-09-29"
EXPECTED_PILLARS = 126


def dms_to_decimal(value: str) -> float:
    normalized = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", value)
    normalized = re.sub(r"(\d+\.\d+)\s+(\d+)", r"\1\2", normalized)
    parts = re.findall(r"\d+(?:\.\d+)?", normalized)
    if len(parts) != 3:
        raise ValueError(f"Cannot parse DMS coordinate: {value!r}")
    degrees, minutes, seconds = map(float, parts)
    return degrees + minutes / 60 + seconds / 3600


def extract_pillars() -> list[dict]:
    pillars: dict[int, dict] = {}
    with pdfplumber.open(SOURCE) as pdf:
        for page_index in (5, 6):  # PDF pages 6-7
            for table in pdf.pages[page_index].extract_tables():
                for row in table:
                    if len(row) < 6:
                        continue
                    for start in (0, 3):
                        match = re.fullmatch(r"BP\s*(\d+)", (row[start] or "").strip())
                        if not match:
                            continue
                        number = int(match.group(1))
                        lat_dms, lon_dms = (row[start + 1] or "").strip(), (row[start + 2] or "").strip()
                        record = {
                            "pillar_id": f"BP{number}",
                            "pillar_number": number,
                            "latitude_dms_as_reported": lat_dms,
                            "longitude_dms_as_reported": lon_dms,
                            "latitude": dms_to_decimal(lat_dms),
                            "longitude": dms_to_decimal(lon_dms),
                            "provenance": "SOURCE",
                            "source_ref": (
                                "MOIL_Gumgaon_Khodegaon_Tegai_PFR_2017.pdf; "
                                f"PDF page {page_index + 1}, table 'Co-ordinates of the Mining Lease area'; "
                                f"{SOURCE_URL}; retrieved {RETRIEVED}"
                            ),
                        }
                        if number in pillars and pillars[number] != record:
                            raise RuntimeError(f"Conflicting source coordinates for BP{number}")
                        pillars[number] = record
    ordered = [pillars[number] for number in sorted(pillars)]
    expected_ids = list(range(1, EXPECTED_PILLARS + 1))
    if [row["pillar_number"] for row in ordered] != expected_ids:
        raise RuntimeError(
            f"Expected sequential BP1-BP{EXPECTED_PILLARS}; extracted "
            f"{len(ordered)} pillars with IDs {sorted(pillars)}"
        )
    return ordered


def gumgaon_register_ref() -> str:
    if not REGISTER.is_file():
        return ""
    with REGISTER.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            locality = row["village_or_locality_as_reported"].lower()
            if "gumgaon" in locality and "kodegaon" in locality and "126.84" == row["lease_area_ha"]:
                return row["source_ref"]
    return ""


def main() -> dict:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Archive the source PFR first: {SOURCE}")
    pillars = extract_pillars()
    POINTS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with POINTS_OUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pillars[0]))
        writer.writeheader()
        writer.writerows(pillars)

    coords = [(row["longitude"], row["latitude"]) for row in pillars]
    coords.append(coords[0])
    polygon = Polygon(coords)
    if not polygon.is_valid:
        raise RuntimeError("Pillar sequence does not form a valid polygon; GeoJSON was not written")
    geod = Geod(ellps="WGS84")
    computed_area_ha = abs(geod.polygon_area_perimeter(
        [xy[0] for xy in coords[:-1]], [xy[1] for xy in coords[:-1]]
    )[0]) / 10_000
    register_ref = gumgaon_register_ref()
    method = (
        "Converted the report's DMS boundary pillars to decimal degrees, sorted BP1-BP126 by "
        "pillar number, linked them in that order, and closed the ring; computed geodesic area "
        "on the WGS84 ellipsoid."
    )
    pfr_ref = (
        "MOIL_Gumgaon_Khodegaon_Tegai_PFR_2017.pdf; PDF pages 6-7, "
        "'Co-ordinates of the Mining Lease area' and page 7 'Land Detail'; "
        f"{SOURCE_URL}; retrieved {RETRIEVED}"
    )
    feature = {
        "type": "Feature",
        "properties": {
            "lease_name": "Gumgaon-Khodegaon-Tegai Manganese Ore Mine",
            "operator": "MOIL Limited",
            "district": "Nagpur",
            "state": "Maharashtra",
            "pillar_count": len(pillars),
            "pfr_title_area_ha": 126.84,
            "pfr_land_detail_area_ha": 126.46,
            "dgm_register_area_ha": 126.84,
            "computed_geodesic_area_ha": round(computed_area_ha, 4),
            "geometry_status": "PFR applicant-reported boundary; verify against approved DGPS/cadastral plan before legal or resource use",
            "provenance": "DERIVED",
            "method": method,
            "source_ref": pfr_ref + (" | DGM register: " + register_ref if register_ref else ""),
        },
        "geometry": mapping(polygon),
    }
    collection = {"type": "FeatureCollection", "name": "Gumgaon lease boundary", "features": [feature]}
    POLYGON_OUT.write_text(json.dumps(collection, indent=2), encoding="utf-8")

    audit = {
        "status": "COMPLETE_PUBLISHED_PILLARS_IMPORTED",
        "pillar_count": len(pillars),
        "pillar_ids_sequential": True,
        "polygon_valid": polygon.is_valid,
        "computed_geodesic_area_ha": round(computed_area_ha, 4),
        "pfr_title_area_ha": 126.84,
        "pfr_land_detail_area_ha": 126.46,
        "dgm_register_area_ha": 126.84,
        "area_discrepancy_ha": round(126.84 - 126.46, 4),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "outputs": [
            str(POINTS_OUT.relative_to(ROOT)).replace("\\", "/"),
            str(POLYGON_OUT.relative_to(ROOT)).replace("\\", "/"),
        ],
        "provenance": "DERIVED",
        "method": method,
        "source_ref": pfr_ref + (" | DGM register: " + register_ref if register_ref else ""),
        "limitations": [
            "The PFR describes the lease coordinates, but the resulting polygon should be verified against an approved DGPS/cadastral plan before legal boundary use.",
            "The PFR has conflicting area fields: 126.84 ha in the title and 126.46 ha in its land-detail table; both source values are preserved.",
            "Lease area is not proven ore area or a reserve estimate.",
        ],
    }
    AUDIT_OUT.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))
    return audit


if __name__ == "__main__":
    main()

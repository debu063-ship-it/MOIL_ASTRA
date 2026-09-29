"""Import MOIL manganese lease rows from Maharashtra DGM's public 2025 register.

The register reports lease parcels, localities, and hectares but does not include
GIS boundary coordinates. Source PDF is archived unchanged under data/external.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/external/exploration/public_sources/maharashtra_working_major_mineral_leases_2025.pdf"
OUTPUT = ROOT / "data/processed/moil_manganese_lease_register_2025.csv"
AUDIT = ROOT / "data/processed/moil_manganese_lease_register_2025_validation.json"
SOURCE_URL = "https://mahadgm.gov.in/writereaddata/fckimagefile/WORKING%20MINE%20LIST%20%20Major%20minerals.pdf"
RETRIEVED = "2026-09-29"
EXPECTED_ROWS = 18

FIELDS = [
    "source_serial",
    "district",
    "state",
    "lessee_as_reported",
    "tehsil_as_reported",
    "mineral_as_reported",
    "village_or_locality_as_reported",
    "lease_area_ha",
    "original_lease_grant_date",
    "lease_period_as_reported",
    "operating_status_as_reported",
    "remarks_as_reported",
    "provenance",
    "source_ref",
]


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def source_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    districts = {0: "Nagpur", 1: "Bhandara"}
    with pdfplumber.open(SOURCE) as pdf:
        for page_index, district in districts.items():
            page = pdf.pages[page_index]
            tables = page.extract_tables()
            if not tables:
                raise RuntimeError(f"No lease table found on PDF page {page_index + 1}")
            for raw in tables[0]:
                cells = list(raw) + [None] * max(0, 11 - len(raw))
                owner, mineral = clean(cells[2]), clean(cells[4])
                if "manganese" not in owner.lower() and "m.o.i.l" not in owner.lower() and "moil" not in owner.lower():
                    continue
                if mineral.lower() != "manganese ore":
                    continue
                area_text = clean(cells[6]).replace(",", "")
                try:
                    area = f"{float(area_text):.3f}".rstrip("0").rstrip(".")
                except ValueError as exc:
                    raise RuntimeError(f"Could not parse lease area {cells[6]!r}") from exc
                serial = "/".join(part for part in (clean(cells[0]), clean(cells[1])) if part)
                rows.append({
                    "source_serial": serial,
                    "district": district,
                    "state": "Maharashtra",
                    "lessee_as_reported": owner,
                    "tehsil_as_reported": clean(cells[3]),
                    "mineral_as_reported": mineral,
                    "village_or_locality_as_reported": clean(cells[5]),
                    "lease_area_ha": area,
                    "original_lease_grant_date": clean(cells[7]),
                    "lease_period_as_reported": clean(cells[8]),
                    "operating_status_as_reported": clean(cells[9]),
                    "remarks_as_reported": clean(cells[10]),
                    "provenance": "SOURCE",
                    "source_ref": (
                        "maharashtra_working_major_mineral_leases_2025.pdf; "
                        f"page {page_index + 1}, table 'LIST OF WORKING MINING LEASES "
                        "FOR MAJOR MINERALS AS ON 01.04.2025'; "
                        f"{SOURCE_URL}; retrieved {RETRIEVED}"
                    ),
                })
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_ROWS} MOIL manganese lease rows; extracted {len(rows)}")
    return rows


def main() -> dict:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Archive the source PDF first: {SOURCE}")
    rows = source_rows()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    report = {
        "status": "COMPLETE_SOURCE_REGISTER_IMPORTED",
        "row_count": len(rows),
        "rows_by_district": dict(Counter(row["district"] for row in rows)),
        "output": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "source_file": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": source_hash,
        "retrieved": RETRIEVED,
        "provenance": "DERIVED",
        "method": "Extracted the MOIL manganese ore rows from pages 1-2 of the Maharashtra DGM working major-mineral lease PDF using pdfplumber; preserved reported parcel areas and wording without summing amalgamated parcels.",
        "source_ref": f"{SOURCE.name}; pages 1-2; {SOURCE_URL}; retrieved {RETRIEVED}",
        "limitations": [
            "The register contains lease areas and village/locality text, not boundary coordinates or GIS polygons.",
            "Lease area is not the area proven to contain ore.",
            "Rows are preserved individually; amalgamation remarks may describe grouped parcels, so rows must not be summed as independent mine areas without checking the remarks.",
        ],
    }
    AUDIT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()

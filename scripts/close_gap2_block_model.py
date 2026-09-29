"""Create explicitly empty block-model deliverables when no input can support one.

Source collar and assay intervals are now available for Gudma and Western Ukwa.
The workbooks do not provide project-ready downhole XYZ traces or mine lease
polygons, so a 3D grid and defensible spatial interpolation cannot be built.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed"
NOTE = "Illustrative, based on sparse data; not a resource estimate. No blocks generated: source assays are available for 13 Gudma and Western Ukwa holes, but complete downhole XYZ traces and mine lease polygons are unavailable."


def main() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    fields = {"block_id": pd.Series(dtype="string"), "x": pd.Series(dtype="float64"),
              "y": pd.Series(dtype="float64"), "z": pd.Series(dtype="float64"),
              "geology_unit": pd.Series(dtype="string"), "est_grade": pd.Series(dtype="float64"),
              "kriging_variance": pd.Series(dtype="float64"), "provenance": pd.Series(dtype="string"),
              "method": pd.Series(dtype="string"), "random_seed": pd.Series(dtype="Int64")}
    table = pa.Table.from_pandas(pd.DataFrame(fields), preserve_index=False)
    meta = dict(table.schema.metadata or {})
    meta.update({b"note": NOTE.encode(), b"status": b"BLOCKED_NO_3D_HOLE_TRACES_OR_LEASE_POLYGONS",
                 b"crs": b"EPSG:32644; no coordinates emitted",
                 b"provenance": b"DERIVED schema only; zero data rows"})
    pq.write_table(table.replace_schema_metadata(meta), OUT / "block_model.parquet")
    fc = {"type": "FeatureCollection", "name": "empty_block_model",
          "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}},
          "metadata": {"note": NOTE, "status": "BLOCKED_NO_3D_HOLE_TRACES_OR_LEASE_POLYGONS", "provenance": "DERIVED",
                       "target_crs": "EPSG:32644; projected grid coordinates are required when inputs become available"}, "features": []}
    (OUT / "block_model.geojson").write_text(json.dumps(fc, indent=2), encoding="utf-8")
    report = {"gap": 2, "status": "BLOCKED_NO_3D_HOLE_TRACES_OR_LEASE_POLYGONS", "block_count": 0,
              "variogram": None, "fallback": None, "cross_validation_rmse": None,
              "note": NOTE,
              "reason": "Real assay intervals and collars are available for seven Gudma and six Western Ukwa holes. The sample depths are measured along the boreholes, but validated downhole XYZ traces and mine lease polygons are not in the project. A 3D 25 x 25 x 5 m grid and kriging/IDW values would require unverified hole paths and a made-up model domain.",
              "method": "No interpolation run. Empty schema artifacts are emitted until surveyed downhole traces and lease geometry are available.",
              "source_ref": ["data/processed/boreholes_source.csv; 13 joined collar/intersection rows; retrieved 2026-09-29",
                             "data/processed/borehole_assays_source.csv; 88 intervals extracted from official NGDR workbooks; retrieved 2026-09-29",
                             "data/processed/published_drilling_summaries.csv; SOURCE aggregate summaries; retrieved 2026-09-29",
                             "data/external/exploration/ibm_moil_reserves_2024.csv; IBM Indian Minerals Yearbook 2024, pp. 66-67; retrieved 2026-09-29"]}
    (OUT / "block_model_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))

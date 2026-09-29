# Data card: MOIL manganese prospectivity dashboard

## Purpose

Exploratory mapping and data integration for manganese prospectivity in the Balaghat, Bhandara, Nagpur, and Ukwa area. Outputs support screening and discussion; they do not establish a mineral resource or replace field exploration.

## Coverage and coordinate system

The project grid contains 5,568 centroids in EPSG:4326, spanning latitude 21.100 to 22.045 N and longitude 79.200 to 80.490 E.

## Data included

- GSI regional geology, mine and occurrence points, NGDR report metadata, and published drilling/resource summaries.
- Thirteen located Gudma/Western Ukwa drill holes and 88 official NGDR sample-assay intervals from the registered-user reports.
- Sentinel-2/Copernicus sampled reflectance and terrain values, four-site monthly NDVI, daily rainfall/weather, and hourly soil moisture.
- Prospectivity scores, model labels, and derived priority-zone polygons.
- Public company-level production anchors and clearly labeled synthetic production scenarios.

## Limitations

The sample intervals include ore and non-ore lithologies, overlapping records, and one reversed from/to interval retained and flagged as reported. They are not independent clean ore widths or resource grades. Complete downhole XYZ traces, georeferenced map/GDB assets, and MOIL mine lease polygons remain unavailable, so the 3D block model is empty. Priority zones are screening outputs. Mine-wise production allocations, planned targets, and shortfalls in synthetic files are illustrative, not observed MOIL operating data.

## Provenance

New generated rows/features carry one of SOURCE, DERIVED, or SYNTHETIC, with source references or a method and seed. See data/MANIFEST.json and data/GAPS_LOG.md. Existing legacy raw files were left unchanged and may not contain row-level provenance fields.

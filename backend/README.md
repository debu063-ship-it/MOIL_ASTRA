# MOIL Manganese Intelligence — Backend

FastAPI implementation of `docs/backend_architecture.md` (precompute-heavy, serve-light).

## Run

```bash
# from project root (Windows Git Bash)
export PATH="$LOCALAPPDATA/Programs/Python/Python312:$LOCALAPPDATA/Programs/Python/Python312/Scripts:$PATH"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8600
# Swagger UI: http://127.0.0.1:8600/docs
```

Tests: `python -m pytest backend/tests/test_api.py -q` (20 tests).

## API v1 (all under /api/v1)

| Feature | Endpoints |
|---|---|
| Prospectivity map | `GET /grid/summary` · `GET /grid/scores?bbox&min_prob` (GeoJSON) · `GET /grid/cell?lat&lon` |
| Production forecasting | `GET /production/mines` · `GET /production/history?mine` · `GET /production/forecast?mine&planned_tonnes` |
| Shortfall prediction | `GET /shortfall/holdout` (45-row honest holdout) |
| Dashboard metrics card | `GET /models` (registry + CV metrics + provenance) |
| Corrective action | `POST /actions/recommend?mine` (rules engine) · `GET /actions/rules` |
| What-if simulator | `POST /whatif/simulate {mine, equipment_availability, monthly_rain_mm, planned_tonnes?}` |
| Explainable AI | `GET /xai/importance` · `GET /xai/cell?lat&lon&k` (driver attribution) |
| Report export | `POST /reports/generate?scope` → `GET /reports/status/{id}` → `GET /reports/download/{id}` |
| Interactive layers | `GET /layers` · `GET /layers/{name}` (boreholes, lithology_polygons, moil_mines, priority_zones, structure) |
| Volume & area | `GET /volume/summary` (GSI tonnage/volume/SG, no double counting) |
| Grade | `GET /grade/summary` (per-block Mn/Fe/SiO₂/P/SG from 161 real assays) |
| Alerts | `GET /alerts` (threshold evaluation, persisted) · `GET /alerts/history` |

## Notes

- **Provenance is a response field** on every analytics endpoint (`real` / `SYNTHETIC-CALIBRATED`),
  sourced from `app/config.py`. UI and reports must surface it.
- SQLite DB auto-seeds on first startup from serving artifacts (`outputs/moil_dashboard.db`).
- Models load lazily from `outputs/models_v3/` via the registry singleton.
- Reports render charts via matplotlib, assemble HTML; PDF conversion activates automatically
  if `weasyprint` is installed (needs GTK runtime on Windows), otherwise HTML is served.
- Alert thresholds live in `app/config.py`; corrective-action playbook in `app/rules.yml`
  (deterministic on purpose — no action-outcome training data exists).

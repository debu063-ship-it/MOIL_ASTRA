# Backend Architecture — MOIL Manganese Intelligence Platform (SIH26009)

Date: 2026-09-29. Principle: **precompute-heavy, serve-light**. Batch pipelines do the heavy
GIS/ML work and publish versioned artifacts; the API serves them. This is the most reliable
shape for a hackathon demo and an honest starting point for production.

## 1. System diagram

```
        ┌──────────────────────────── SOURCES ────────────────────────────┐
        │ Google Earth Engine   Open-Meteo archive   NGDR/GSI (registered) │
        │ (S2, DEM, climate)    (daily/hourly)       (static packages)     │
        │ IBM/MOIL tables (curated CSV)   MOIL ops drops (future, manual)  │
        └──────────┬───────────────────────────────────────────────────────┘
                   ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ INGESTION JOBS  (Python scripts, run by APScheduler / manual CLI)  │
   │  fetch_weather · refresh_s2_ndvi · ingest_ngdr · ingest_ops_csv    │
   │  → write-once RAW ZONE  data/external/... (immutable, dated)       │
   └──────────┬────────────────────────────────────────────────────────┘
              ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ FEATURE PIPELINES (pandas / geopandas / pyogrio)                   │
   │  build_grid_features → features/grid_features.parquet  (5,568×36)  │
   │  build_ops_features  → features/ops_features.parquet               │
   └──────────┬──────────────────────────────────┬─────────────────────┘
              ▼                                  ▼
   ┌──────────────────────┐          ┌───────────────────────────────┐
   │ MODEL REGISTRY       │          │ BATCH SCORING JOBS            │
   │ outputs/models/      │─────────▶│ score_grid.py (prospectivity) │
   │  prospectivity/v3/   │ joblib   │ forecast_shortfall.py         │
   │  shortfall/v2/       │ load     │ recommend_actions.py (rules)  │
   │  + metadata/metrics  │          └──────────┬────────────────────┘
   └──────────────────────┘                     ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ SERVING STORE                                                      │
   │  SQLite: mines, ops_monthly, predictions, alerts, actions, reports │
   │  Parquet/GeoJSON: grid_scores, layers (geology, collars, plates)   │
   └──────────┬────────────────────────────────────────────────────────┘
              ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ FastAPI  /api/v1/*   (stateless; loads registry + serving store)   │
   │  scores · layers · boreholes · volume · forecast · shortfall ·     │
   │  whatif · xai · alerts · actions · reports · models                │
   └──────────┬──────────────────────────┬──────────────────────────────┘
              ▼                          ▼
      Dashboard UI (Streamlit       Report worker (BackgroundTask:
      or React+Leaflet)             matplotlib charts + HTML→PDF,
      map · panels · simulator      provenance-labeled tables)
```

## 2. Repository layout (backend slice)

```
backend/
  app/
    main.py                 # FastAPI app factory, router mounting
    config.py               # paths, thresholds, model versions (env-overridable)
    registry.py             # model registry load/hot-swap (joblib + metadata)
    db.py                   # SQLite (SQLAlchemy) session + schema
    schemas.py              # Pydantic request/response models
    routers/
      scores.py  layers.py  boreholes.py  volume.py
      production.py  shortfall.py  whatif.py  xai.py
      alerts.py  actions.py  reports.py  meta.py
    services/
      scoring.py            # grid scoring (batch + on-demand cell)
      forecast.py           # shortfall forecaster wrapper
      whatif.py             # response-model simulator
      xai.py                # per-cell driver attribution (permutation-lite / SHAP)
      rules_engine.py       # corrective-action playbook (deterministic)
      report_builder.py     # charts + PDF assembly
      alerts.py             # threshold evaluation
    jobs/
      scheduler.py          # APScheduler: nightly weather, monthly re-score
      fetch_weather.py  score_grid.py  forecast_shortfall.py
  migrations/               # alembic (optional) or schema.sql
  tests/                    # pytest: API smoke + rule-engine unit tests
```

## 3. Data & model versioning

- **Raw zone** immutable: `data/external/<source>/<date>/` — provenance preserved.
- **Feature store**: Parquet with run-date column; grid keyed by (lat, lon).
- **Model registry**: `outputs/models/<name>/<semver>/` containing
  `model.joblib`, `metadata.json` (features, CV metrics, provenance, training data hash),
  `metrics.json`. `registry.json` maps `name → active version`; config pins versions used
  by the API (currently: prospectivity v3 ensemble, shortfall v2 ExtraTrees, whatif v2 RF).
- **Serving artifacts**: `grid_scores_v3.csv` (+ future Parquet) published after each scoring run;
  API reads the active artifact, never the live working file.

## 4. API surface (per feature)

| Feature | Endpoint(s) | Backend path |
|---|---|---|
| 1 Prospectivity map | `GET /grid/scores?bbox=&min_prob=` → GeoJSON/COG tiles; `GET /grid/cell?lat=&lon=` | scoring service reads grid_scores artifact |
| 2 Production forecasting | `GET /production/forecast?mine=&horizon_m=` | forecaster (A) + plan table; provenance-labeled |
| 3 Shortfall prediction | `GET /shortfall/predict?mine=`; `GET /alerts` | forecaster + alert classifier (secondary) + thresholds |
| 4 Dashboard | consumes all endpoints | — |
| 5 Corrective action | `POST /actions/recommend {mine, context?}` | deterministic rules engine (trigger → action list) |
| 6 What-if simulator | `POST /whatif/simulate {mine, availability, rain}` → ratio Δ vs baseline | whatif response model (B) |
| 7 Explainable AI | `GET /xai/cell?lat=&lon=` (top-k drivers); `GET /xai/importance` | permutation attribution around cell + importance CSV |
| 8 Report export | `POST /reports/generate {scope}` → `GET /reports/{id}.pdf` | report worker (charts, tables, provenance footnotes) |
| 9 Interactive layers | `GET /layers` catalog; `GET /layers/{name}` (geology, collars, mines, plates, scores) | GeoJSON from serving store |
| 10 Volume & area | `GET /volume/summary?block=` → area_m2, volume_m3, tonnage, SG, grade | resource_estimates join + zone areas |
| 11 Grade | `GET /grade/summary?block=`; `GET /boreholes?block=` assays | borehole_assays + IBM context |

Meta: `GET /models` (registry + metrics for the metrics card), `GET /health`.

## 5. Corrective-action rules engine (feature 5)

Deterministic, auditable table `rules.yml`: condition (shortfall_ratio > x, rain > y,
equipment_availability < z, alert_class) → actions with priority + expected effect text +
source citation. Output stored in `actions` table with `rule_id` so every recommendation is
traceable — deliberately not ML, because no action-outcome data exists to learn from.

## 6. Jobs & freshness

| Job | Schedule | Output |
|---|---|---|
| fetch_weather (Open-Meteo/GEE) | daily 06:00 | satellite raw zone + ops features |
| refresh_ndvi | monthly (S2 16-day composite) | ndvi monthly |
| score_grid | monthly + on demand | grid_scores artifact (versioned) |
| forecast_shortfall | monthly (after plan upload) | predictions + alerts |
| model retrain | manual / quarterly | new registry version (never auto-promote) |

## 7. Deployment

- **Demo/hackathon**: single VM or laptop — `uvicorn` (API) + APScheduler in-process +
  Streamlit dashboard; SQLite; everything precomputed so no heavy compute at request time.
- **Docker-compose** (3 services): `api`, `dashboard`, `scheduler` + volume for artifacts.
- **Production path (if MOIL adopts)**: swap SQLite → Postgres/PostGIS, add auth (OIDC),
  object storage for artifacts, Airflow/Prefect for jobs, TIPI/COG tile server for rasters,
  and real ops ingestion via SFTP/API drop — architecture unchanged, components upgraded.

## 8. Cross-cutting

- **Provenance-first**: every response includes `provenance` block (real / synthetic-calibrated /
  measured) sourced from metadata — shown in UI and printed in reports.
- **Reproducibility**: scoring jobs log model version + feature artifact hash with outputs.
- **Testing**: pytest API smoke tests + golden-file tests on scoring outputs; rule engine unit tests.
- **Security (demo)**: no auth needed; production path adds OIDC + role-based access.

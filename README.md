# MOIL ASTRA — AI & Space Technology for Manganese Reserve Identification & Production Shortfalls

An intelligent 3D geospatial dashboard and analytics platform engineered for **MOIL Limited** (Balaghat Manganese Mining Belt, MP/Maharashtra, India), built for **Smart India Hackathon 2026 (SIH26009)**.

The system integrates **multi-spectral Earth observation satellite data** (Copernicus Sentinel-2, Copernicus DEM, CHIRPS rainfall) with **geological & drill-hole records** (GSI lithology, NGDR borehole collars & assays, IBM/MOIL UNFC reserves) and **machine-learning models** (XGBoost + RandomForest + HistGradientBoosting ensemble) to pinpoint prospective manganese mineralization zones, forecast production, predict shortfalls, recommend corrective actions, and export compliance-grade reports.

> **Feature completeness:** all 11 SIH26009 declared features are implemented and demonstrable end-to-end. See the feature matrix below; every claim links to the endpoint, artifact, or doc that proves it.

---

## ✅ Feature Matrix (11/11 implemented)

| # | Feature | Where it lives | Evidence |
|---|---------|----------------|----------|
| 1 | **Prospectivity map** | 160 priority zones rendered on Cesium 3D globe from `POST`-trained v3 ensemble over a 5,568-cell grid | `GET /api/v1/dashboard/zones` · `data/processed/grid_scores_v3.csv` · [docs/model_training_v3.md](docs/model_training_v3.md) |
| 2 | **Production forecasting** | Mine-level monthly target vs AI forecast chart with 12-month history + next-month prediction | `GET /api/v1/production/forecast` · Step 1 of analysis panel |
| 3 | **Shortfall prediction** | Predicted shortfall tonnage, risk index, root-cause attribution (equipment, rainfall, blast delays), alert flags | `GET /api/v1/shortfall/holdout` · `GET /api/v1/alerts` · `data/processed/shortfall_predictions_v2.csv` |
| 4 | **Dashboard** | "OrePulse" app: Cesium 3D globe, ECharts analytics, 5-step mine-intelligence workflow, layer/timeline controls | `frontend/` (React 18 + Vite + TS + Tailwind + Cesium + ECharts + Zustand) |
| 5 | **Corrective actions** | Rules engine (9 deterministic playbooks CA-001…CA-009) with quantified production gain, risk reduction, cost & duration | `GET /api/v1/actions/rules` · `POST /api/v1/actions/recommend` · [backend/app/rules.yml](backend/app/rules.yml) |
| 6 | **What-if simulator** | Sliders for blast delay / equipment availability / rainfall → trained RandomForest response model runs on the backend | `POST /api/v1/whatif/simulate` · `outputs/models_v3/whatif_response_surface.csv` |
| 7 | **Explainable AI** | SHAP-style feature importances per prediction + honest ablation narrative (evidence-only ROC 0.759) | `GET /api/v1/xai/importance` · Step 3 of analysis panel |
| 8 | **Report export** | Executive dossier → client-side PDF (jsPDF), multi-sheet Excel (.xlsx), CSV; plus server-side HTML reports with charts | Step 5 of analysis panel · `POST /api/v1/reports/generate` → `outputs/reports/` |
| 9 | **Interactive map layers** | 6 toggled layers with opacity sliders & provenance badges — Priority Zones [MODELED], Mn Mines [REAL], NGDR Drill Holes (50) [REAL], GSI Lithology (135 polygons) [REAL], Priority Zone Outlines [MODELED], Rainfall grid (monthly timeline Jan–Dec 2025) [REAL] | `GET /api/v1/layers` · `GET /api/v1/dashboard/climate/rainfall/{date}` |
| 10 | **Volume & area** | 37 GSI resource blocks rendered as 3D prisms (~120 m footprint) with tonnage & grade; zone area in hectares; IBM UNFC tonnage (111/122/211/221/332/333) | `GET /api/v1/dashboard/ore_volume` · `GET /api/v1/volume/summary` · `GET /api/v1/dashboard/grade_tonnage` |
| 11 | **Grade of ore** | Assay-backed grade summaries (161 NGDR assay intervals; 57 ore-grade averaging **34.9% Mn**), per-block grade-tonnage curves | `GET /api/v1/grade/summary` · `GET /api/v1/dashboard/grade_tonnage` |

### Verified model metrics

| Model | Metric | Value |
|---|---|---|
| Prospectivity v3 ensemble | Spatial LOGO ROC-AUC / PR-AUC | **0.997 / 0.998** |
| Prospectivity v3 — honest ablation (no proximity features) | Spatial ROC-AUC | **0.759** |
| Prospectivity v3 — top-decile precision | Cells within 3 km of known mineralization | **54%** (~40× the 3.8% base rate) |
| Shortfall forecaster v2 (ExtraTrees) | Holdout MAE | **≈736 t/month**, R² 0.656 (32% better than baseline) |
| What-if response model (RandomForest) | Holdout MAE | 0.0374 shortfall-ratio |
| Alert classifier | ROC-AUC (weak — secondary signal only) | 0.634 |

Full methodology & caveats: [docs/model_training_v3.md](docs/model_training_v3.md). Live values: `GET /api/v1/meta/models`.

---

## 🏛️ System Architecture

- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, CesiumJS 3D Globe (Resium), Apache ECharts, Zustand state management.
- **Backend API**: FastAPI (Python 3.12+), SQLite persistent store, Uvicorn ASGI server, Pydantic validation, joblib model registry.
- **AI & Analytics Engine**:
  - `Prospectivity Model v3` — soft-voting ensemble (XGBoost + RandomForest + HistGradientBoosting), selected by spatial leave-one-group-out CV over RF/ExtraTrees/HGB/XGB/LR.
  - `Production Shortfall Forecaster v2` — ExtraTrees time-series forecaster with honest 5-month holdout.
  - `What-If Response Model` — RandomForest trained without history features so operators can drive it in real time.
  - `Explainable AI` — per-cell & global feature importances with evidence-only ablation.
  - `Corrective Action Engine` — deterministic rules playbooks with tonnage/cost trade-offs.
- **Test suite**: 20 pytest tests (`python -m pytest backend/tests -q`) — all passing.

### API surface (v1)

`/health` · `/meta/models` · `/grid/summary` · `/grid/scores` · `/grid/cell` · `/layers` · `/boreholes` (+ `/assays`, `/structure`) · `/volume/summary` · `/grade/summary` · `/production/mines|history|forecast` · `/shortfall/holdout` · `/whatif/simulate` (POST) · `/xai/importance` · `/alerts` (+ `/history`) · `/actions/recommend` (POST) · `/actions/rules` · `/reports/generate` (POST) · `/dashboard/zones|boreholes|mines|production|actions|shap|ore_volume|data_sources|weather|grade_tonnage|climate/{layer}/{date}` — interactive docs at `http://127.0.0.1:8600/docs`.

---

## 📁 Repository Structure

```text
MOIL_ASTRA/
├── backend/
│   ├── app/                  # FastAPI app: 11 routers (scores, layers, production,
│   │                         #   shortfall, whatif, xai, alerts_actions, reports,
│   │                         #   meta, dashboard) + services + rules.yml
│   └── tests/                # 20 pytest tests (all passing)
├── frontend/                 # "OrePulse" 3D CesiumJS React application
│   ├── src/components/       #   CesiumMap, AnalysisPanel (5 steps), layers, modals
│   ├── src/lib/              #   API client, layer registry, simulation wiring
│   └── src/store/            #   Zustand store
├── data/
│   ├── external/             # NGDR borehole parses, IBM/MOIL UNFC reserves, GSI geology
│   ├── processed/            # grid_scores_v3.csv (5,568 cells), shortfall_predictions_v2.csv
│   └── synthetic/            # monthly_ops_synthetic_2015_2026.csv (calibrated, labeled)
├── docs/                     # model training, backend architecture, data sources & gaps
├── outputs/
│   ├── models_v3/            # trained .joblib models + metadata JSONs + response surface
│   ├── reports/              # generated HTML/PDF reports with charts
│   └── moil_dashboard.db     # auto-seeded SQLite store
├── scripts/                  # ingestion, feature engineering, model training pipelines
└── DATA_CARD.md              # provenance & data transparency declaration
```

---

## 🚀 Getting Started

### 1. Backend

```bash
pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8600
```

Swagger UI: `http://127.0.0.1:8600/docs` · Health: `http://127.0.0.1:8600/api/v1/health`

Tests: `python -m pytest backend/tests -q` (20 pass).

> The backend must be running before the frontend loads — every panel fetches live model output from port 8600. There is no bundled demo data by design.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

*(Optional)* Cesium Ion token in `frontend/.env` for world terrain; the OSM basemap works without it:

```env
VITE_CESIUM_ION_TOKEN=your_token_here
```

---

## 📊 Data Transparency & Provenance

Every metric, layer, and chart carries a provenance tag:

- `[REAL]` — NGDR borehole collars & assay intervals (50 collars, 161 assays), GSI lithology (135 polygons), GSI resource blocks (37, incl. W. Ukwa 2.18 Mt validated vs published report), IBM/MOIL UNFC reserves, Sentinel-2/Copernicus DEM indices, observed rainfall.
- `[MODELED]` — prospectivity probabilities, production forecasts, shortfall predictions, SHAP attributions, what-if outputs.
- `[SYNTHETIC]` — mine-monthly operations 2015–2026, calibrated to real MOIL annual anchors + real rainfall seasonality (no public mine-monthly data exists).

Detailed descriptions: [DATA_CARD.md](DATA_CARD.md), [docs/data_sources.md](docs/data_sources.md), [docs/feature_data_gaps.md](docs/feature_data_gaps.md), [docs/model_training_v3.md](docs/model_training_v3.md).

# MOIL ASTRA — AI & Space Technology for Manganese Reserve Identification & Production Shortfalls

An intelligent, pitch-ready 3D geospatial dashboard and analytics platform engineered for **MOIL Limited** (Balaghat Manganese Mining Belt, MP/Maharashtra, India).

The system integrates **multi-spectral Earth observation satellite data** (Copernicus Sentinel-2, Landsat-8/9, CHIRPS rainfall, SMAP soil moisture) with **geological & drill-hole records** (GSI, NGDR) and **machine learning models** (XGBoost, Random Forest, LightGBM) to pinpoint prospective manganese mineralization zones and forecast operational production shortfalls.

---

## 🏛️ System Architecture

- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, CesiumJS 3D Globe (`Resium`), Apache ECharts, Zustand state management.
- **Backend API**: FastAPI (Python 3.12+), SQLite persistent store, Uvicorn ASGI server, Pydantic data validation.
- **AI & Analytics Engine**: 
  - `Prospectivity Model v3`: Geospatial mineral probability scoring across regional EPSG:4326 grid cells.
  - `Production Shortfall Forecaster v2`: Predictive time-series shortfall regression with uncertainty intervals.
  - `Explainable AI (SHAP)`: Feature importance attribution (SWIR absorption, NDVI anomalies, soil moisture, structural lineaments).
  - `What-If Scenario Simulator`: Real-time sensitivity simulation (blast delays, equipment availability, monsoon rainfall anomalies).
  - `Corrective Action Engine`: Ranked operational mitigations with estimated tonnage recovery and cost-benefit trade-offs.

---

## 📁 Repository Structure

```text
MOIL_ASTRA/
├── backend/                  # FastAPI REST service & test suite
│   ├── app/                  # Main application routers, models & config
│   │   ├── api/              # API v1 endpoints
│   │   ├── config.py         # App configuration & data paths
│   │   └── main.py           # FastAPI entrypoint
│   └── tests/                # Automated pytest suite
├── frontend/                 # 3D CesiumJS React application
│   ├── src/                  # Components, hooks, stores & styles
│   ├── public/               # Public assets & icons
│   └── package.json          # Dependencies & scripts
├── data/                     # Geological grids, drill logs, satellite indices & models
├── docs/                     # Architecture, data sources & methodology documentation
├── outputs/                  # Trained ML models (v3), reports, charts & SQLite DB
├── scripts/                  # Data ingestion, feature engineering & model training pipelines
└── DATA_CARD.md              # Provenance & data transparency declaration
```

---

## 🚀 Getting Started

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8600 --reload
```
Swagger UI will be available at: `http://127.0.0.1:8600/docs`

To run backend tests:
```bash
python -m pytest backend/tests/test_api.py -q
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

*(Optional)* If you have a Cesium Ion token, configure it in `frontend/.env`:
```env
VITE_CESIUM_ION_TOKEN=your_token_here
```

---

## 📊 Data Transparency & Provenance

Every metric, layer, and chart in the platform carries transparent provenance tags:
- `[REAL]`: Empirical borehole assays, IBM statutory mining lease cadastre, and GSI lithological maps.
- `[MODELED]`: Geostatistical probability inferences and ML predictions.
- `[SYNTHETIC]`: Downscaled calibrated operational scenarios for air-gapped demo fidelity.

Detailed descriptions can be found in [DATA_CARD.md](DATA_CARD.md) and [docs/](docs/).

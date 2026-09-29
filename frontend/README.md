# MOIL Limited — Manganese AI & Space Intelligence Dashboard (OrePulse)

An interactive, pitch-ready, map-first 3D geospatial dashboard for **"Using AI/ML and Space Technology to Identify Manganese Reserves and Overcome Production Shortfalls"** at MOIL Limited (Balaghat Manganese Mining Lease ML-04, MP, India).

## Tech Stack
- **Framework**: React 18 + Vite + TypeScript
- **Styling**: Tailwind CSS + Custom Pitch-Ready Glassmorphism
- **Geospatial 3D Engine**: CesiumJS + Resium + vite-plugin-cesium
- **Analytics & Visualizations**: Apache ECharts (`echarts` + `echarts-for-react`)
- **State Machine**: Zustand
- **Animations**: Framer Motion
- **Data Fetching & Cache**: TanStack Query
- **Reporting & Export**: jsPDF + html2canvas + SheetJS (xlsx)
- **Icons**: Lucide Icons

---

## Key Features

### 1. Full-Screen 3D Geospatial Map
- Complete 3D terrain exploration of the MOIL Balaghat mining lease.
- Prospectivity zones colored by manganese probability:
  - **Very High (>0.8)**: Red (`#ef4444`)
  - **High (0.6 - 0.8)**: Orange (`#f97316`)
  - **Medium (0.4 - 0.6)**: Yellow (`#eab308`)
  - **Low (<0.4)**: Blue/Slate (`#3b82f6`)
- Interactive hover tooltips showing zone reserves, average grade, strike length, and probability.
- Real IBM statutory mining lease cadastre boundary.

### 2. Close-Up 3D Ore Volume & Underground Visibility
- Smooth camera flight (`camera.flyTo`) focusing directly onto the selected zone.
- **3D Extruded Voxel Block Model**: Subsurface bench layers down to -160m underground, color-coded by grade (% Mn) and geostatistical probability.
- **Terrain Transparency**: Instant toggle to make surface terrain translucent (`globe.translucency.frontFaceAlpha = 0.35`) so the underground ore body is visible.
- **Stratigraphic Core Boreholes**: 3D vertical columns cutting through the ore volume with collar elevations, total depths, and clickable grade-vs-depth core logs.

### 3. Interactive Multi-Modal Satellite & Climate Layers
- Collapsible floating **Layers Panel** (shifts dynamically when analysis panel opens).
- **Monthly Time Slider** with play/pause driving:
  - **NDVI (Sentinel-2)**: Vegetation vigor anomaly tracking manganese soil geochemical stress.
  - **Rainfall (CHIRPS / IMERG)**: Precipitation and monsoon inundation risk.
  - **Soil Moisture (SMAP proxy)**: Pit floor saturation and haul road trafficability.
  - **Land Surface Temperature (Landsat-8/9 TIRS proxy)**: Thermal inertia anomalies.
  - **Geology / Lithology**: GSI Sausar Group Mansar ore formation mapping.
- Point-and-click climate tooltip displaying observed value, units, date, and source badge.

### 4. 5-Step Guided AI Analysis Panel (~35% Width Slide-In)
- **Step 1: Production Forecast & Shortfall Prediction**
  - ECharts actual vs forecast line chart with 95% confidence bands (monthly & quarterly toggle).
  - Shortfall target vs projected bar chart, operational risk gauge, and root-cause drivers.
- **Step 2: Corrective Actions**
  - AI-ranked operational interventions (blasting schedule, excavator redeployment, dewatering pumps, blending ratios).
  - Expected impact (+MT, -% risk), lead times, costs, and Accept/Ignore decision toggles.
- **Step 3: Explainable AI (SHAP)**
  - Horizontal bar chart of feature importances (SWIR absorption, NDVI anomalies, soil moisture, structural lineaments).
  - Plain-language synthesis explaining the physical basis of the model's confidence.
- **Step 4: What-If Simulator**
  - Interactive sliders for Blast Delay (days), Equipment Count (units), and Monsoon Rainfall (%).
  - Live recalculation of production forecasts, net shortfalls, operational risk scores, and map zone risk color feedback.
- **Step 5: Compliance-Grade Export Report**
  - **PDF Export**: Executive briefing with Cesium canvas capture, active layers catalog, forecast charts, accepted actions, and XAI attribution.
  - **Excel Export (.xlsx)**: Multi-sheet workbook with Zone Summary, Monthly Forecast Table, Action Decision List, and Geospatial Metadata.
  - **CSV Export**: Direct time-series forecast export.

### 5. Strict Data Provenance & Transparency
Every single chart, layer, and UI panel carries visible provenance badges:
- `[REAL]`: Empirical measurements (drill cores, assay lab tests, IBM cadastre, GSI maps).
- `[MODELED]`: Machine learning and geostatistical inferences.
- `[SYNTHETIC]`: Downscaled climate simulations for air-gapped demo fidelity.
- Interactive **Data Sources Modal** cataloging all 9 datasets with sensors, resolution, and licensing.

---

## Setup & Running Locally

### Prerequisites
- Node.js (v18+ recommended)
- npm or yarn

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Cesium Ion Token (Optional)
Copy or edit `.env`:
```env
VITE_CESIUM_ION_TOKEN=your_cesium_ion_token_here
```
*(If left empty, the application uses local ellipsoid terrain and standard cartographic imagery without errors)*

### 3. Run Development Server
```bash
npm run dev
```
Open your browser at `http://localhost:5173`.

### 4. Build for Production
```bash
npm run build
npm run preview
```

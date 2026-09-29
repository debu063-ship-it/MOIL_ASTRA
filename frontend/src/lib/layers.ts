import { LayerDefinition } from '@/types';

/**
 * Layer registry backed by the FastAPI backend (/layers catalog).
 * Badges reflect actual provenance:
 *  - [REAL]     = measured / downloaded data on disk (NGDR, GSI, S2, mines)
 *  - [MODELED]  = outputs of the v3 ML ensemble or feature engineering
 *  - [SYNTH]    = synthetic-calibrated ops (real annual anchors, no public mine-monthly data)
 * The old demo climate folders (/data/layers/ndvi|rainfall|soil_moisture|lst) were removed —
 * the only time-varying layer now is rainfall, served from real station observations.
 */
export const LAYER_REGISTRY: LayerDefinition[] = [
  {
    id: "prospectivity",
    label: "Exploration Priority Zones (v3 model)",
    type: "geojson",
    url: "/api/v1/dashboard/zones",
    source: "[MODELED / v3 ENSEMBLE]",
    badge: "[MODELED]",
    timeVarying: false,
    defaultVisible: true,
    defaultOpacity: 0.85,
    legend: [
      { label: "Very High (>0.8)", color: "#ef4444" },
      { label: "High (0.6 - 0.8)", color: "#f97316" },
      { label: "Medium (0.4 - 0.6)", color: "#eab308" },
      { label: "Low (<0.4)", color: "#3b82f6" }
    ]
  },
  {
    id: "known_occurrences",
    label: "Known Mn Mines (MOIL/IBM)",
    type: "geojson",
    url: "/api/v1/layers/moil_mines",
    source: "[REAL / IBM & MOIL]",
    badge: "[REAL]",
    timeVarying: false,
    defaultVisible: true,
    defaultOpacity: 1.0,
    legend: [
      { label: "Active Mine (MOIL)", color: "#ef4444" },
      { label: "Confirmed Deposit", color: "#f97316" }
    ]
  },
  {
    id: "boreholes",
    label: "NGDR Drill Holes (50, real assays)",
    type: "geojson",
    url: "/api/v1/dashboard/boreholes",
    source: "[REAL / NGDR-GSI]",
    badge: "[REAL]",
    timeVarying: false,
    defaultVisible: true,
    defaultOpacity: 1.0,
    legend: [
      { label: "High Grade Core (>40% Mn)", color: "#dc2626" },
      { label: "Medium Grade Core (30-40%)", color: "#ea580c" },
      { label: "Ore Horizon (20-30%)", color: "#d97706" },
      { label: "Overburden / Host Rock", color: "#78716c" }
    ]
  },
  {
    id: "geology",
    label: "GSI Lithology (135 mapped polygons)",
    type: "geojson",
    url: "/api/v1/layers/lithology_polygons",
    source: "[REAL / GSI PLATES 64C/05]",
    badge: "[REAL]",
    timeVarying: false,
    defaultVisible: false,
    defaultOpacity: 0.5,
    legend: [
      { label: "Sausar Group (Mansar/Mn)", color: "#be123c" },
      { label: "Tirodi Gneissic Complex", color: "#334155" },
      { label: "Amgaon / Sakoli units", color: "#b45309" }
    ]
  },
  {
    id: "priority_zones",
    label: "Priority Exploration Zones (aggregated)",
    type: "geojson",
    url: "/api/v1/layers/priority_zones",
    source: "[MODELED / v2-zones]",
    badge: "[MODELED]",
    timeVarying: false,
    defaultVisible: false,
    defaultOpacity: 0.6,
    legend: [
      { label: "Top-decile cluster", color: "#ef4444" },
      { label: "Priority cell group", color: "#f97316" }
    ]
  },
  {
    id: "rainfall",
    label: "Rainfall (station observations)",
    type: "climate_grid",
    folder: "/api/v1/climate/rainfall",
    source: "[REAL / OPEN-METEO STATIONS]",
    badge: "[REAL]",
    timeVarying: true,
    defaultVisible: false,
    defaultOpacity: 0.6,
    unit: "mm/month",
    legend: [
      { label: "> 300 mm Severe Rain", color: "#1e1b4b" },
      { label: "150 - 300 mm Heavy", color: "#1d4ed8" },
      { label: "50 - 150 mm Moderate", color: "#0284c7" },
      { label: "< 50 mm Low / Dry", color: "#38bdf8" }
    ]
  }
];

/**
 * Timeline months come from the real weather archive (2015-2025).
 * The backend serves monthly rainfall rasters for these keys.
 */
export const TIMELINE_MARKS = [
  { key: "2025-01", label: "Jan 2025", season: "Winter" },
  { key: "2025-02", label: "Feb 2025", season: "Winter" },
  { key: "2025-03", label: "Mar 2025", season: "Summer" },
  { key: "2025-04", label: "Apr 2025", season: "Pre-Monsoon" },
  { key: "2025-05", label: "May 2025", season: "Peak Summer" },
  { key: "2025-06", label: "Jun 2025", season: "Monsoon Onset" },
  { key: "2025-07", label: "Jul 2025", season: "Active Monsoon" },
  { key: "2025-08", label: "Aug 2025", season: "Peak Monsoon" },
  { key: "2025-09", label: "Sep 2025", season: "Monsoon Withdrawal" },
  { key: "2025-10", label: "Oct 2025", season: "Post-Monsoon" },
  { key: "2025-11", label: "Nov 2025", season: "Winter Onset" },
  { key: "2025-12", label: "Dec 2025", season: "Winter" }
];

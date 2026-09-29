# -*- coding: utf-8 -*-
"""Central configuration: paths, active model versions, alert thresholds."""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "outputs")

GRID_SCORES = os.path.join(DATA, "processed", "grid_scores_v3.csv")
GRID_FEATURES = os.path.join(DATA, "processed", "engineered_features_integrated_grid.csv")
SHORTFALL_PRED = os.path.join(DATA, "processed", "shortfall_predictions_v2.csv")
OPS_SYNTH = os.path.join(DATA, "synthetic", "monthly_ops_synthetic_2015_2026.csv")
COLLARS = os.path.join(DATA, "external", "exploration", "ngdr_parsed", "exploration_boreholes.geojson")
ASSAYS = os.path.join(DATA, "external", "exploration", "ngdr_parsed", "borehole_assays.csv")
LITHOLOGS = os.path.join(DATA, "external", "exploration", "ngdr_parsed", "borehole_lithologs.csv")
RESOURCES = os.path.join(DATA, "external", "exploration", "ngdr_parsed", "resource_estimates.csv")
STRUCTURE = os.path.join(DATA, "external", "exploration", "ngdr_parsed", "structure_measurements.csv")
LITHO_POLY = os.path.join(DATA, "external", "exploration", "ngdr_parsed", "lithology_polygons.geojson")
MINES_GEOJSON = os.path.join(DATA, "raw", "moil_mines.geojson")
PRIORITY_ZONES = os.path.join(DATA, "processed", "priority_zones.geojson")
IMPORTANCE = os.path.join(OUT, "models_v3", "feature_importance_v3.csv")
RESPONSE_SURFACE = os.path.join(OUT, "models_v3", "whatif_response_surface.csv")
REPORTS_DIR = os.path.join(OUT, "reports")

MODELS_DIR = os.path.join(OUT, "models_v3")
MODELS = {
    "prospectivity": os.path.join(MODELS_DIR, "prospectivity_v3.joblib"),
    "shortfall_forecaster": os.path.join(MODELS_DIR, "shortfall_forecaster_v2.joblib"),
    "whatif_response": os.path.join(MODELS_DIR, "whatif_response_v2.joblib"),
    "shortfall_alert": os.path.join(MODELS_DIR, "shortfall_alert_clf_v2.joblib"),
}
METADATA = {
    "prospectivity": os.path.join(MODELS_DIR, "prospectivity_v3_metadata.json"),
    "shortfall": os.path.join(MODELS_DIR, "shortfall_v2_metadata.json"),
}

RULES_FILE = os.path.join(os.path.dirname(__file__), "rules.yml")
DB_PATH = os.environ.get("MOIL_DB", os.path.join(OUT, "moil_dashboard.db"))

# alert thresholds (documented, configurable)
ALERT_RATIO = 0.15          # shortfall ratio that constitutes a "miss"
ALERT_HEAVY_RAIN = 8        # days/month of heavy rain considered disruptive
ALERT_EQ_AVAIL = 0.85       # equipment availability floor

PROVENANCE = {
    "grid_scores": "real labels (30 known deposits + 50 NGDR collars) on real S2/DEM/GSI features",
    "production_forecast": "SYNTHETIC-CALIBRATED: mine-monthly ops anchored to real MOIL annual totals + real rainfall",
    "shortfall": "SYNTHETIC-CALIBRATED: see production_forecast; metrics validate learning, not real ops",
    "resources": "REAL: GSI exploration reports (CRO-23394-2017, CRO-23290-2016) via NGDR",
    "assays": "REAL: GSI core-sample assays via NGDR (161 samples, 2 blocks)",
}

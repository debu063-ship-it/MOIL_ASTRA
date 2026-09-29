# -*- coding: utf-8 -*-
import os, sys, time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_models_registry(client):
    r = client.get("/api/v1/models")
    assert r.status_code == 200
    reg = r.json()["registry"]
    assert all(v["exists"] for v in reg.values())
    meta = r.json()["metadata"]["prospectivity"]
    assert meta["model"] == "ensemble"


def test_grid_summary(client):
    r = client.get("/api/v1/grid/summary")
    j = r.json()
    assert r.status_code == 200 and j["cells"] == 5568


def test_grid_scores_bbox(client):
    r = client.get("/api/v1/grid/scores", params={
        "min_lat": 21.9, "min_lon": 80.4, "max_lat": 22.0, "max_lon": 80.5,
        "min_prob": 0.0, "max_cells": 500})
    j = r.json()
    assert r.status_code == 200 and j["count"] > 0
    f = j["features"][0]
    assert f["type"] == "Feature" and "prob_v3" in f["properties"]


def test_grid_cell(client):
    r = client.get("/api/v1/grid/cell", params={"lat": 21.97, "lon": 80.45})
    j = r.json()
    assert r.status_code == 200 and "prob_v3" in j


def test_layers_catalog(client):
    r = client.get("/api/v1/layers")
    names = {l["name"] for l in r.json()}
    assert {"boreholes", "lithology_polygons", "moil_mines"} <= names


def test_layer_boreholes(client):
    r = client.get("/api/v1/boreholes")
    j = r.json()
    assert j["count"] == 50
    props = j["features"][0]["properties"]
    assert "borehole" in props and "block" in props


def test_volume_summary(client):
    j = client.get("/api/v1/volume/summary").json()
    blocks = {b["block"]: b for b in j["blocks"]}
    assert "Western Ukwa" in blocks and "Gudma" in blocks
    assert blocks["Western Ukwa"]["tonnage_t"] == pytest.approx(2182604, rel=0.01)
    assert blocks["Gudma"]["avg_mn_pct"] == pytest.approx(21.65, rel=0.05)


def test_grade_summary(client):
    j = client.get("/api/v1/grade/summary").json()
    assert j["all_samples"] >= 100
    for block, v in j["blocks"].items():
        assert 15 <= v["ore_mean_mn_pct"] <= 60


def test_production_mines_and_history(client):
    mines = client.get("/api/v1/production/mines").json()["mines"]
    assert "Balaghat" in mines
    h = client.get("/api/v1/production/history",
                   params={"mine": "Balaghat", "months": 12}).json()
    assert len(h["history"]) == 12
    assert "SYNTHETIC" in h["provenance"]


def test_production_forecast(client):
    j = client.get("/api/v1/production/forecast", params={"mine": "Ukwa"}).json()
    assert 0 <= j["predicted_shortfall_ratio"] <= 1
    assert j["planned_tonnes"] > 0
    assert j["month"] > "2025-12"


def test_shortfall_holdout(client):
    j = client.get("/api/v1/shortfall/holdout").json()
    assert len(j["predictions"]) == 45
    assert "SYNTHETIC" in j["provenance"]


def test_whatif_simulate(client):
    r = client.post("/api/v1/whatif/simulate", json={
        "mine": "Balaghat", "equipment_availability": 0.8, "monthly_rain_mm": 300})
    assert r.status_code == 200
    j = r.json()
    assert j["scenario_ratio"] > j["baseline_ratio"]      # worse drivers -> worse shortfall
    r2 = client.post("/api/v1/whatif/simulate", json={
        "mine": "Balaghat", "equipment_availability": 0.98, "monthly_rain_mm": 5})
    assert r2.json()["scenario_ratio"] < j["scenario_ratio"]


def test_whatif_validation(client):
    r = client.post("/api/v1/whatif/simulate", json={
        "mine": "Balaghat", "equipment_availability": 1.4, "monthly_rain_mm": 10})
    assert r.status_code == 422


def test_alerts(client):
    j = client.get("/api/v1/alerts").json()
    assert isinstance(j["alerts"], list) and len(j["alerts"]) > 0
    kinds = {a["kind"] for a in j["alerts"]}
    assert kinds  # at least some alert kinds fired on latest month


def test_actions_recommend(client):
    j = client.post("/api/v1/actions/recommend", params={"mine": "Balaghat"}).json()
    assert j["mine"] == "Balaghat"
    assert isinstance(j["actions"], list)
    if j["actions"]:
        a = j["actions"][0]
        assert a["rule_id"].startswith("CA-") and a["action"]


def test_actions_rules_listed(client):
    rules = client.get("/api/v1/actions/rules").json()["rules"]
    assert len(rules) >= 5
    assert all(r["id"].startswith("CA-") for r in rules)


def test_xai_importance(client):
    j = client.get("/api/v1/xai/importance").json()
    top = j["importance"][0]
    assert top["feature"] == "dist_to_known_deposit_km"


def test_xai_cell(client):
    j = client.get("/api/v1/xai/cell", params={"lat": 21.97, "lon": 80.45}).json()
    assert "prob_v3" in j and len(j["top_drivers"]) > 0
    d = j["top_drivers"][0]
    assert "feature" in d and "influence" in d


def test_report_generate_and_download(client):
    r = client.post("/api/v1/reports/generate", params={"scope": "full"}).json()
    job_id = r["job_id"]
    for _ in range(60):
        st = client.get(f"/api/v1/reports/status/{job_id}").json()
        if st["status"] in ("done", "error"):
            break
        time.sleep(1)
    assert st["status"] == "done", st.get("error")
    dl = client.get(f"/api/v1/reports/download/{job_id}")
    assert dl.status_code == 200
    assert dl.headers["content-type"] in ("application/pdf", "text/html",
                                          "text/html; charset=utf-8")

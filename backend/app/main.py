# -*- coding: utf-8 -*-
"""FastAPI application: MOIL Manganese Intelligence API v1."""
import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.routing import APIRouter

from .config import ROOT
from .db import seed_if_empty
from .routers import (scores, layers, production, shortfall, whatif, xai,
                      alerts_actions, reports, meta, dashboard)

API = "/api/v1"


def _mount_frontend(app: FastAPI) -> None:
    """Single-service deploy: serve the built React app from this API.

    Activates only when frontend/dist/index.html exists (built frontend).
    The Cesium ion token is injected at request time from the
    VITE_CESIUM_ION_TOKEN env var so it never lives in git or the image.
    """
    dist = os.path.join(ROOT, "frontend", "dist")
    index_file = os.path.join(dist, "index.html")
    if not os.path.isfile(index_file):
        return

    token = os.environ.get("VITE_CESIUM_ION_TOKEN", "").strip()
    injection = ""
    if token:
        payload = json.dumps({"cesiumIonToken": token})
        injection = f"<script>window.__MOIL_ENV__ = {payload};</script>"

    spa = APIRouter()

    @spa.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        candidate = os.path.normpath(os.path.join(dist, full_path))
        if candidate == dist or candidate.startswith(dist + os.sep):
            if os.path.isfile(candidate):
                return FileResponse(candidate)
        if injection and os.path.isfile(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                html = f.read()
            return Response(html.replace("</head>", injection + "</head>", 1),
                            media_type="text/html")
        return FileResponse(index_file)

    app.include_router(spa)


def create_app() -> FastAPI:
    app = FastAPI(title="MOIL Manganese Intelligence API",
                  version="1.0.0",
                  description="Serving prospectivity, shortfall, what-if, XAI, "
                              "resources and reports for the SIH26009 dashboard.")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(meta.router, prefix=API)
    app.include_router(scores.router, prefix=API)
    app.include_router(layers.router, prefix=API)
    app.include_router(production.router, prefix=API)
    app.include_router(shortfall.router, prefix=API)
    app.include_router(whatif.router, prefix=API)
    app.include_router(xai.router, prefix=API)
    app.include_router(alerts_actions.router, prefix=API)
    app.include_router(reports.router, prefix=API)
    app.include_router(dashboard.router, prefix=API)
    _mount_frontend(app)  # no-op until frontend/ is built

    @app.on_event("startup")
    def _startup():
        seeded = seed_if_empty()
        print(f"[startup] DB seed: {'fresh' if seeded else 'existing'}")

    return app


app = create_app()

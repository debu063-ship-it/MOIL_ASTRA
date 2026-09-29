# -*- coding: utf-8 -*-
"""FastAPI application: MOIL Manganese Intelligence API v1."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import seed_if_empty
from .routers import (scores, layers, production, shortfall, whatif, xai,
                      alerts_actions, reports, meta, dashboard)

API = "/api/v1"


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

    @app.on_event("startup")
    def _startup():
        seeded = seed_if_empty()
        print(f"[startup] DB seed: {'fresh' if seeded else 'existing'}")

    return app


app = create_app()

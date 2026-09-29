# -*- coding: utf-8 -*-
from fastapi import APIRouter
from .. import config
from ..services.registry import registry

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "moil-manganese-intelligence", "version": "v1"}


@router.get("/models")
def models():
    reg = registry()
    return {"registry": reg.status(),
            "metadata": {"prospectivity": {k: v for k, v in reg.metadata("prospectivity").items()
                                           if k in ("model", "ensemble_members", "cv",
                                                    "evidence_only_no_proximity",
                                                    "top_decile_hit_rate_3km",
                                                    "validation_caveat", "positives_source")},
                         "shortfall": {k: v for k, v in reg.metadata("shortfall").items()
                                       if k in ("modelA", "modelB", "holdout", "provenance",
                                                "alert_clf")}},
            "provenance": config.PROVENANCE}

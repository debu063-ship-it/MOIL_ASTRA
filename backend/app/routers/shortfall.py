# -*- coding: utf-8 -*-
from fastapi import APIRouter
from .. import config
from ..services import forecast

router = APIRouter(prefix="/shortfall", tags=["shortfall"])


@router.get("/holdout")
def holdout():
    return {"predictions": forecast.holdout_predictions(),
            "provenance": config.PROVENANCE["shortfall"]}

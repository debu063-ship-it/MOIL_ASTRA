# -*- coding: utf-8 -*-
"""Model registry: lazy-load joblib models + metadata with cached handles."""
import json, os
from functools import lru_cache
import joblib
from .. import config


class Registry:
    def __init__(self):
        self._models = {}

    def get(self, name: str):
        if name not in self._models:
            path = config.MODELS[name]
            if not os.path.exists(path):
                raise FileNotFoundError(f"model artifact missing: {path}")
            self._models[name] = joblib.load(path)
        return self._models[name]

    def metadata(self, name: str) -> dict:
        path = config.METADATA.get(name)
        if not path or not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def status(self) -> dict:
        out = {}
        for name, path in config.MODELS.items():
            out[name] = {
                "artifact": os.path.basename(path),
                "loaded": name in self._models,
                "exists": os.path.exists(path),
                "size_mb": round(os.path.getsize(path) / 1e6, 2) if os.path.exists(path) else None,
            }
        return out


@lru_cache(maxsize=1)
def registry() -> Registry:
    return Registry()

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
import joblib


ARTIFACT_DIR = Path("artifacts")
MODEL_PATH = ARTIFACT_DIR / "delay_model.joblib"
META_PATH = ARTIFACT_DIR / "delay_model_meta.json"


class DelayModelService:
    def __init__(self):
        self.model = None
        self.meta: Dict[str, Any] = {}
        self.loaded = False

    def load(self):
        if MODEL_PATH.exists():
            self.model = joblib.load(MODEL_PATH)
            self.loaded = True
        if META_PATH.exists():
            with open(META_PATH, "r", encoding="utf-8") as f:
                self.meta = json.load(f)

    def predict_delay_hours(
        self,
        queue_index: float,
        weather_risk: float,
        news_risk: float,
        backlog_index: float,
        ops_risk: float
    ) -> Dict[str, Any]:
        # fallback формула, если модель не загружена
        if not self.loaded or self.model is None:
            composite = 0.25*queue_index + 0.20*weather_risk + 0.25*news_risk + 0.15*backlog_index + 0.15*ops_risk
            delay = round(4 + 30*composite, 1)
            return {
                "predicted_delay_hours": delay,
                "predictor": "formula_fallback",
                "model_loaded": False,
                "model_name": None
            }

        x = np.array([[queue_index, weather_risk, news_risk, backlog_index, ops_risk]], dtype=float)
        pred = float(self.model.predict(x)[0])
        pred = max(0.0, pred)

        return {
            "predicted_delay_hours": round(pred, 2),
            "predictor": "ml_model",
            "model_loaded": True,
            "model_name": self.meta.get("model_name"),
            "model_metrics": self.meta.get("metrics", {})
        }


delay_model_service = DelayModelService()
delay_model_service.load()

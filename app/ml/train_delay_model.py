from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error

import joblib


FEATURES = ["queue_index", "weather_risk", "news_risk", "backlog_index", "ops_risk"]
TARGET = "delay_hours"

ARTIFACT_DIR = Path("artifacts")
MODEL_PATH = ARTIFACT_DIR / "delay_model.joblib"
META_PATH = ARTIFACT_DIR / "delay_model_meta.json"


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    # избегаем деления на 0
    eps = 1e-6
    return float(np.mean(np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), eps))) * 100.0)


def _build_model():
    # Пытаемся XGBoost; если нет — fallback sklearn GBDT
    try:
        from xgboost import XGBRegressor
        model = XGBRegressor(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            random_state=42,
        )
        model_name = "XGBRegressor"
        return model, model_name
    except Exception:
        from sklearn.ensemble import GradientBoostingRegressor
        model = GradientBoostingRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=3,
            random_state=42
        )
        model_name = "GradientBoostingRegressor"
        return model, model_name


def load_dataset(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    missing = [c for c in FEATURES + [TARGET] if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")
    return df


def train(csv_path: str, test_size: float = 0.2, random_state: int = 42) -> Dict:
    df = load_dataset(csv_path)

    X = df[FEATURES].astype(float).values
    y = df[TARGET].astype(float).values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    model, model_name = _build_model()
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
    mape = _mape(y_test, pred)

    # feature importance (если доступно)
    feature_importance = {}
    if hasattr(model, "feature_importances_"):
        fi = model.feature_importances_
        feature_importance = {f: float(v) for f, v in zip(FEATURES, fi)}

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    meta = {
        "model_name": model_name,
        "features": FEATURES,
        "target": TARGET,
        "metrics": {
            "mae": mae,
            "rmse": rmse,
            "mape_percent": mape,
        },
        "feature_importance": feature_importance,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "source_csv": csv_path,
    }

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return meta


if __name__ == "__main__":
    # Пример:
    # python -m app.ml.train_delay_model --csv data/port_delay_training.csv
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to training CSV")
    args = parser.parse_args()

    result = train(args.csv)
    print(json.dumps(result, indent=2, ensure_ascii=False))

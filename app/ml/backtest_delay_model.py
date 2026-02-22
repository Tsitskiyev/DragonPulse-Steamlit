from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Модель и фичи из Day 5
from app.ml.train_delay_model import FEATURES, TARGET, _build_model


ARTIFACT_DIR = Path("artifacts")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

RESULTS_CSV = ARTIFACT_DIR / "backtest_results.csv"
SUMMARY_JSON = ARTIFACT_DIR / "backtest_summary.json"


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    eps = 1e-6
    return float(np.mean(np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), eps))) * 100.0)


def baseline_formula_predict(df: pd.DataFrame) -> np.ndarray:
    """
    Простой explainable baseline:
    delay ≈ 4 + 30*(0.25*queue + 0.20*weather + 0.25*news + 0.15*backlog + 0.15*ops)
    """
    composite = (
        0.25 * df["queue_index"].values
        + 0.20 * df["weather_risk"].values
        + 0.25 * df["news_risk"].values
        + 0.15 * df["backlog_index"].values
        + 0.15 * df["ops_risk"].values
    )
    return 4.0 + 30.0 * composite


def evaluate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mape_val = float(mape(y_true, y_pred))
    return {"mae": mae, "rmse": rmse, "mape_percent": mape_val}


def rolling_splits(
    n_rows: int, train_min: int = 80, test_size: int = 20, step: int = 20
) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    Expanding window:
    train: [0 : train_end), test: [train_end : train_end + test_size)
    """
    splits = []
    train_end = train_min
    while train_end + test_size <= n_rows:
        train_idx = np.arange(0, train_end)
        test_idx = np.arange(train_end, train_end + test_size)
        splits.append((train_idx, test_idx))
        train_end += step
    return splits


def train_predict_model(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    feature_cols: List[str],
) -> np.ndarray:
    model, model_name = _build_model()
    X_train = df_train[feature_cols].astype(float).values
    y_train = df_train[TARGET].astype(float).values
    X_test = df_test[feature_cols].astype(float).values

    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    return pred


def run_backtest(csv_path: str) -> Dict:
    df = pd.read_csv(csv_path).copy()

    required = set(FEATURES + [TARGET])
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")

    # если есть дата — сортируем по дате, иначе по индексу
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)

    # Rolling windows
    splits = rolling_splits(len(df), train_min=max(80, int(len(df) * 0.4)), test_size=max(20, int(len(df) * 0.1)), step=max(10, int(len(df) * 0.1)))
    if not splits:
        raise ValueError("Not enough rows for rolling backtest. Need more data.")

    rows = []

    ablations = {
        "full": FEATURES,
        "no_news_risk": [f for f in FEATURES if f != "news_risk"],
        "no_weather_risk": [f for f in FEATURES if f != "weather_risk"],
    }

    for fold_id, (train_idx, test_idx) in enumerate(splits, start=1):
        df_train = df.iloc[train_idx].copy()
        df_test = df.iloc[test_idx].copy()
        y_test = df_test[TARGET].astype(float).values

        # baseline
        base_pred = baseline_formula_predict(df_test)
        base_metrics = evaluate_metrics(y_test, base_pred)

        rows.append({
            "fold": fold_id,
            "model_variant": "baseline_formula",
            **base_metrics,
            "train_size": int(len(df_train)),
            "test_size": int(len(df_test)),
        })

        # ML full + ablations
        for variant_name, feat_cols in ablations.items():
            pred = train_predict_model(df_train, df_test, feat_cols)
            met = evaluate_metrics(y_test, pred)
            rows.append({
                "fold": fold_id,
                "model_variant": f"ml_{variant_name}",
                **met,
                "train_size": int(len(df_train)),
                "test_size": int(len(df_test)),
            })

    res = pd.DataFrame(rows)
    res.to_csv(RESULTS_CSV, index=False)

    # Summary averages
    summary = {}
    for variant in sorted(res["model_variant"].unique()):
        part = res[res["model_variant"] == variant]
        summary[variant] = {
            "mae_mean": float(part["mae"].mean()),
            "rmse_mean": float(part["rmse"].mean()),
            "mape_mean_percent": float(part["mape_percent"].mean()),
            "folds": int(part.shape[0]),
        }

    # Improvement vs baseline on MAE
    base_mae = summary["baseline_formula"]["mae_mean"]
    for variant in summary:
        if variant == "baseline_formula":
            summary[variant]["mae_improvement_vs_baseline_percent"] = 0.0
        else:
            mae_v = summary[variant]["mae_mean"]
            improv = (base_mae - mae_v) / base_mae * 100.0
            summary[variant]["mae_improvement_vs_baseline_percent"] = float(improv)

    out = {
        "dataset_rows": int(len(df)),
        "features": FEATURES,
        "target": TARGET,
        "results_csv": str(RESULTS_CSV),
        "summary_json": str(SUMMARY_JSON),
        "summary": summary,
    }

    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    return out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to training CSV")
    args = parser.parse_args()

    result = run_backtest(args.csv)
    print(json.dumps(result, ensure_ascii=False, indent=2))

import json
from pathlib import Path
import pandas as pd

SUMMARY = Path("artifacts/backtest_summary.json")
EVENTS = Path("artifacts/events_snapshot.csv")  # optional

def get_monitoring():
    out = {
        "data_drift": {"status": "not_configured"},
        "prediction_drift": {"status": "not_configured"},
        "quality": {"status": "ok"},
        "retrain_recommended": False
    }

    if SUMMARY.exists():
        d = json.load(open(SUMMARY, "r", encoding="utf-8"))
        s = d.get("summary", {})
        base = s.get("baseline_formula", {}).get("mae_mean")
        ml_key = "ml_full" if "ml_full" in s else next((k for k in s if k.startswith("ml_")), None)
        ml = s.get(ml_key, {}).get("mae_mean") if ml_key else None

        if base and ml:
            degr = (ml - base) / base * 100
            out["quality"] = {
                "baseline_mae": base,
                "ml_mae": ml,
                "degradation_vs_baseline_percent": round(degr, 2)
            }
            out["retrain_recommended"] = False if ml <= base else True

    return out

from __future__ import annotations
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import traceback

from app.ml.monitoring import get_monitoring
from app.ml.model_service import delay_model_service
from app.core.config import settings
from app.ingestion.news_ingest import fetch_rss_news, mock_news_for_testing
from app.nlp.risk_engine import score_news_batch
from pathlib import Path
import json


router = APIRouter()

# in-memory fallback journal (если БД-слой не готов)
EVENT_JOURNAL: List[Dict[str, Any]] = []


class AggregateRiskIn(BaseModel):
    port: str
    queue_index: float
    weather_risk: float
    news_risk: float
    backlog_index: float
    ops_risk: float


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _save_events(items: List[Dict[str, Any]]) -> None:
    # безопасное сохранение в in-memory журнал
    # если у тебя есть SQLAlchemy, можно заменить реализацией БД
    for i in items:
        EVENT_JOURNAL.append({
            "id": len(EVENT_JOURNAL) + 1,
            "title": str(i.get("title", "")),
            "port": str(i.get("port", "Unknown")),
            "risk_score": float(i.get("risk_score", 0.0)),
            "analyzer": str(i.get("analyzer", "unknown")),
            "published_at": i.get("published_at"),
            "created_at": i.get("published_at"),
            "matched_events": json.dumps(i.get("matched_events", []), ensure_ascii=False),
            "summary": str(i.get("summary", "")),
            "llm_status": i.get("llm_status"),
            "llm_error_type": i.get("llm_error_type"),
        })

@router.get("/risk/backtest-summary")
def backtest_summary():
    p = Path("artifacts/backtest_summary.json")
    if not p.exists():
        return {
            "status": "not_ready",
            "message": "Backtest summary not found. Run: python -m app.ml.backtest_delay_model --csv data/port_delay_training.csv"
        }
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

@router.post("/risk/predict-delay")
def predict_delay(payload: AggregateRiskIn):
    try:
        out = delay_model_service.predict_delay_hours(
            queue_index=float(payload.queue_index),
            weather_risk=float(payload.weather_risk),
            news_risk=float(payload.news_risk),
            backlog_index=float(payload.backlog_index),
            ops_risk=float(payload.ops_risk),
        )
        return {
            "port": payload.port,
            **out
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"predict-delay failed: {type(e).__name__}: {e}")


@router.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@router.get("/debug/llm-config")
def debug_llm_config():
    if settings.llm_provider == "groq":
        key = settings.groq_api_key or ""
        base = settings.groq_base_url
        model = settings.groq_model
    else:
        key = settings.deepseek_api_key or ""
        base = settings.deepseek_base_url
        model = settings.deepseek_model

    masked = (key[:6] + "..." + key[-4:]) if len(key) >= 12 else "EMPTY_OR_SHORT"
    return {
        "provider": settings.llm_provider,
        "base_url": base,
        "model": model,
        "key_masked": masked,
        "key_len": len(key),
    }

def _filter_and_sort(scored, min_relevance: float, min_impact: float, actionable_only: bool):
    items = []
    for x in scored:
        rel = float(x.get("relevance_score", 0.0))
        imp = float(x.get("impact_score", 0.0))
        action = str(x.get("recommended_action", "")).lower()
        is_actionable = ("pre-book" in action) or ("activate contingency" in action)

        if rel < min_relevance:
            continue
        if imp < min_impact:
            continue
        if actionable_only and not is_actionable:
            continue
        items.append(x)

    items.sort(key=lambda z: float(z.get("impact_score", 0.0)), reverse=True)
    return items



@router.get("/news-risk/mock")
def news_risk_mock(
    use_llm: bool = Query(default=False),
    llm_limit: int = Query(default=3, ge=0, le=10),
    min_relevance: float = Query(default=0.0, ge=0.0, le=1.0),
    min_impact: float = Query(default=0.0, ge=0.0, le=1.0),
    actionable_only: bool = Query(default=False),
):
    try:
        news = mock_news_for_testing()
        scored = score_news_batch(news, prefer_llm=use_llm, llm_limit=llm_limit)
        scored = _filter_and_sort(scored, min_relevance, min_impact, actionable_only)
        _save_events(scored)
        return {"count": len(scored), "items": scored}
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"mock endpoint failed: {type(e).__name__}: {e}")


@router.get("/news-risk/live")
def news_risk_live(
    use_llm: bool = Query(default=False),
    max_items: int = Query(default=8, ge=1, le=30),
    relevant_only: bool = Query(default=True),
    llm_limit: int = Query(default=3, ge=0, le=10),
    min_relevance: float = Query(default=0.0, ge=0.0, le=1.0),
    min_impact: float = Query(default=0.0, ge=0.0, le=1.0),
    actionable_only: bool = Query(default=False),
):
    try:
        # 1) Пытаемся взять релевантные
        news = fetch_rss_news(max_items=max_items, relevant_only=relevant_only)

        # 2) fallback: если релевантных нет, берём общий поток
        used_fallback_non_relevant = False
        if not news and relevant_only:
            news = fetch_rss_news(max_items=max_items, relevant_only=False)
            used_fallback_non_relevant = True

        if not news:
            return {
                "count": 0,
                "items": [],
                "meta": {"used_fallback_non_relevant": used_fallback_non_relevant}
            }

        scored = score_news_batch(news, prefer_llm=use_llm, llm_limit=llm_limit)

        # фильтрация/сортировка
        items = []
        for x in scored:
            rel = float(x.get("relevance_score", 0.0))
            imp = float(x.get("impact_score", 0.0))
            action = str(x.get("recommended_action", "")).lower()
            is_actionable = ("pre-book" in action) or ("activate contingency" in action)

            if rel < min_relevance:
                continue
            if imp < min_impact:
                continue
            if actionable_only and not is_actionable:
                continue
            items.append(x)

        items.sort(key=lambda z: float(z.get("impact_score", 0.0)), reverse=True)

        # fallback-2: если после фильтра стало пусто, верни top-N исходных scored
        if not items:
            items = sorted(scored, key=lambda z: float(z.get("impact_score", 0.0)), reverse=True)[:max(3, min(10, max_items))]

        try:
            _save_events(items)
        except Exception as save_err:
            print(f"[WARN] save events failed: {save_err}")

        return {
            "count": len(items),
            "items": items,
            "meta": {"used_fallback_non_relevant": used_fallback_non_relevant}
        }

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"live endpoint failed: {type(e).__name__}: {e}")


@router.post("/risk/aggregate")
def risk_aggregate(payload: AggregateRiskIn):
    try:
        q = _clamp01(payload.queue_index)
        w = _clamp01(payload.weather_risk)
        n = _clamp01(payload.news_risk)
        b = _clamp01(payload.backlog_index)
        o = _clamp01(payload.ops_risk)

        composite = 0.25*q + 0.20*w + 0.25*n + 0.15*b + 0.15*o
        composite = round(composite, 3)

        pred = delay_model_service.predict_delay_hours(
            queue_index=q,
            weather_risk=w,
            news_risk=n,
            backlog_index=b,
            ops_risk=o
        )
        predicted_delay = float(pred.get("predicted_delay_hours", 0.0))

        if composite < 0.35:
            level = "LOW"
        elif composite < 0.65:
            level = "MEDIUM"
        else:
            level = "HIGH"

        if level == "LOW":
            action = "Monitor (6h cadence)"
        elif level == "MEDIUM":
            action = "Pre-book capacity & raise safety stock for critical SKUs"
        else:
            action = "Activate contingency: reroute / expedite / alternate supplier"

        return {
            "port": payload.port,
            "composite_risk_score": composite,
            "predicted_delay_hours": round(predicted_delay, 2),
            "risk_level": level,
            "recommended_action": action,
            "predictor": pred.get("predictor"),
            "model_name": pred.get("model_name"),
            "model_metrics": pred.get("model_metrics", {})
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"aggregate failed: {type(e).__name__}: {e}")

@router.get("/risk/events")
def risk_events(limit: int = Query(default=100, ge=1, le=1000)):
    try:
        items = EVENT_JOURNAL[-limit:]
        items = list(reversed(items))
        return {"count": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"events failed: {type(e).__name__}: {e}")

@router.get("/risk/port-quality")
def port_quality(limit: int = 200):
    items = EVENT_JOURNAL[-limit:] if len(EVENT_JOURNAL) else []
    if not items:
        return {"count": 0, "unknown_port_share": None}

    ports = [str(x.get("port", "Unknown")) for x in items]
    unknown = sum(1 for p in ports if p == "Unknown")
    share = unknown / max(len(ports), 1)
    return {
        "count": len(ports),
        "unknown_port_share": round(share, 4),
        "port_distribution": {
            "Shanghai": ports.count("Shanghai"),
            "Ningbo": ports.count("Ningbo"),
            "Other-China": ports.count("Other-China"),
            "Global": ports.count("Global"),
            "Unknown": ports.count("Unknown"),
        }
    }
@router.get("/ml/monitoring")
def ml_monitoring():
    return get_monitoring()
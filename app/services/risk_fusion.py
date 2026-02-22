from __future__ import annotations


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def composite_risk_score(news_risk: float, forecast_delay_hours: float, ops_risk: float) -> float:
    """
    Composite score in [0,1]:
    - news_risk in [0,1]
    - forecast_delay_hours mapped with soft cap (0..72h -> 0..1)
    - ops_risk in [0,1] from ERP KPIs
    """
    delay_risk = clamp01(forecast_delay_hours / 72.0)
    score = 0.45 * news_risk + 0.35 * delay_risk + 0.20 * ops_risk
    return round(clamp01(score), 3)

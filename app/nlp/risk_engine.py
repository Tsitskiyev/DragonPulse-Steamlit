from __future__ import annotations
from typing import Dict, List, Any
import re

from app.core.llm_client import analyze_news_with_llm

RISK_KEYWORDS = {
    "typhoon_weather": [r"\btyphoon\b", r"台风", r"\bstorm\b"],
    "labor_strike": [r"\bstrike\b", r"罢工"],
    "bankruptcy": [r"\bbankruptcy\b", r"\binsolvency\b", r"破产"],
    "port_congestion": [r"\bcongestion\b", r"\bbacklog\b", r"拥堵"],
    "cyber_outage": [r"\bcyber\b", r"\boutage\b", r"\bransomware\b"],
    "regulatory": [r"\bcustoms\b", r"\bsanction\b", r"\bexport control\b"],
}

SC_RELEVANCE_PATTERNS = [
    r"\bport\b", r"\bshipping\b", r"\bvessel\b", r"\bcontainer\b", r"\blogistics\b",
    r"\bsupply chain\b", r"\bfreight\b", r"\bcongestion\b", r"\bcustoms\b",
    r"\bterminal\b", r"\bwarehouse\b", r"\blead time\b",
    r"港口", r"航运", r"物流", r"集装箱", r"拥堵", r"码头", r"清关"
]

def _resolve_port(text: str) -> str:
    t = (text or "").lower()
    if "shanghai" in t or "上海" in t:
        return "Shanghai"
    if "ningbo" in t or "宁波" in t or "舟山" in t:
        return "Ningbo"
    return "Unknown"

def _calc_relevance_score(title: str, summary: str) -> float:
    text = f"{title} {summary}".lower()
    hits = 0
    for p in SC_RELEVANCE_PATTERNS:
        if re.search(p, text, flags=re.IGNORECASE):
            hits += 1
    # Нормализация: 0..1 (насыщаемся на 6 совпадениях)
    return round(min(hits / 6.0, 1.0), 3)

def _port_exposure(port: str) -> float:
    # Для Unknown даем не 0, а умеренную экспозицию
    if port in ("Shanghai", "Ningbo"):
        return 1.0
    return 0.6

def _recommended_action(impact: float) -> str:
    if impact < 0.30:
        return "Monitor (6h cadence)"
    elif impact < 0.60:
        return "Pre-book capacity & raise safety stock (select SKUs)"
    else:
        return "Activate contingency: reroute / expedite / alternate supplier"

def _enrich_business_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    title = item.get("title", "")
    summary = item.get("summary", "")
    relevance = _calc_relevance_score(title, summary)

    risk_score = float(item.get("risk_score", 0.0))
    exposure = _port_exposure(item.get("port", "Unknown"))

    # impact_score = risk * relevance * exposure
    impact = round(max(0.0, min(1.0, risk_score * relevance * exposure)), 3)

    item["relevance_score"] = relevance
    item["impact_score"] = impact
    item["recommended_action"] = _recommended_action(impact)
    return item

def score_news_item_rules(item):
    import re

    title = str(item.get("title", ""))
    summary = str(item.get("summary", ""))
    text = f"{title} {summary}".lower()

    # ВАЖНО: инициализация в самом начале
    score = 0.0
    matched = []

    # 1) событийные правила
    for event_type, patterns in RISK_KEYWORDS.items():
        try:
            hit = any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)
        except re.error:
            # если вдруг кривой regex в словаре
            hit = any((p.lower() in text) for p in patterns)

        if hit:
            sev = 0.6
            conf = 0.55
            matched.append({
                "event_type": event_type,
                "severity": sev,
                "confidence": conf,
                "location": None,
                "affected_entity": None,
                "expected_duration_days": None,
            })

            # базовые веса по типу события
            if event_type in ["strike", "labor", "shutdown"]:
                score += 0.30
            elif event_type in ["weather", "typhoon", "storm"]:
                score += 0.25
            elif event_type in ["regulatory", "customs", "sanction"]:
                score += 0.20
            elif event_type in ["bankruptcy", "insolvency", "supplier_risk"]:
                score += 0.22
            else:
                score += 0.18

    # 2) fallback-лексика (если событий не поймали)
    if score == 0.0:
        logistics_terms = [
            "port", "shipping", "vessel", "container", "freight", "logistics",
            "queue", "congestion", "terminal", "backlog",
            "港口", "航运", "物流", "集装箱", "拥堵", "码头", "排队"
        ]
        weather_terms = ["typhoon", "storm", "flood", "台风", "暴雨", "风暴"]
        strike_terms = ["strike", "walkout", "罢工"]

        lt = any(k in text for k in logistics_terms)
        wt = any(k in text for k in weather_terms)
        st = any(k in text for k in strike_terms)

        if lt:
            score = max(score, 0.25)
        if wt:
            score = max(score, 0.45)
        if st:
            score = max(score, 0.55)

    # 3) гео/порт резолв
    region, port = resolve_region_and_port(
        title=title,
        summary=summary,
        llm_port="",
        llm_location=""
    )

    # hard override for Hong Kong mentions
    t = f"{title} {summary}".lower()
    if ("hong kong" in t) or ("hong-kong" in t) or ("香港" in t) or ("hk$" in t):
        region, port = "China", "Other-China"


    title_l = title.lower()
    if "zhonggu" in title_l:
        region, port = "China", "Other-China"
    if "dp world" in title_l:
        # это глобальный оператор, не Unknown
        region, port = "Global", "Global"

    score = round(min(max(score, 0.0), 0.95), 3)

    out = {
        **item,
        "affected_region": region,
        "port": port,
        "matched_events": matched,
        "risk_score": score,
        "analyzer": "rules",
        "summary": "Rule-based scoring",
    }

    # если у тебя есть пост-обогащение — оставь:
    # out = _enrich_business_fields(out)
    return out


    region, port = resolve_region_and_port(
        item.get("title", ""),
        item.get("summary", ""),
        "",   # llm_port нет в rules
        ""    # llm_location нет в rules
    )

    out = {
        **item,
        "affected_region": region,   # NEW
        "port": port,                # NEW
        "matched_events": matched,
        "risk_score": round(score, 3),
        "analyzer": "rules",
        "summary": "Rule-based scoring",
    }

    # если у тебя есть _enrich_business_fields(out), оставь:
    # return _enrich_business_fields(out)
    return out


def resolve_region_and_port(title: str, summary: str, llm_port: str = "", llm_location: str = ""):
    text = f"{title} {summary} {llm_port} {llm_location}".lower()

    # ----------------------------
    # 1) Exact target ports
    # ----------------------------
    if any(x in text for x in ["shanghai", "上海", "yangshan"]):
        return "China-East", "Shanghai"

    if any(x in text for x in ["ningbo", "宁波", "zhoushan", "舟山", "ningbo-zhoushan"]):
        return "China-East", "Ningbo"

    # ----------------------------
    # 2) Other Chinese ports (explicit)
    # ----------------------------
    if any(x in text for x in [
        "shenzhen", "yantian", "shekou", "nansha", "guangzhou",
        "xiamen", "qingdao", "tianjin", "dalian", "lianyungang",
        "rizhao", "fuzhou", "beibu", "hong kong port",
        "深圳", "盐田", "蛇口", "南沙", "广州", "厦门", "青岛", "天津", "大连", "连云港", "日照", "福州", "北部湾"
    ]):
        return "China", "Other-China"

    # ----------------------------
    # 3) China entities / China trade hints
    # ----------------------------
    # Если нет точного порта, но явно китайский контекст — лучше Other-China, чем Global/Unknown
    if any(x in text for x in [
        "zhonggu", "cosco", "sinotrans", "china shipping", "china merchants",
        "made in china", "china exports", "china imports",
        "中国", "中远", "招商局", "中国航运", "中国出口", "中国进口"
    ]):
        return "China", "Other-China"

    # ----------------------------
    # 4) Non-China regional hints (optional coarse mapping)
    # ----------------------------
    if any(x in text for x in ["singapore", "psa singapore", "tuas"]):
        return "SE-Asia", "Global"

    if any(x in text for x in ["rotterdam", "antwerp", "hamburg", "european port"]):
        return "Europe", "Global"

    if any(x in text for x in ["los angeles", "long beach", "savannah", "new york port"]):
        return "North-America", "Global"
    # Hong Kong hints -> China operational zone
    if any(x in text for x in ["hong kong", "Hong", "Kong","hong-kong", " hk ", " hk$", "香港"]):
        return "China", "Other-China"

    # ----------------------------
    # 5) Global maritime/logistics signal
    # ----------------------------
    if any(x in text for x in [
        "port", "shipping", "vessel", "container", "freight", "logistics",
        "terminal", "congestion", "backlog", "queue",
        "航运", "港口", "集装箱", "物流", "码头", "拥堵", "排队"
    ]):
        return "Global", "Global"
    # ----------------------------
    # 6) No useful signal
    # ----------------------------
    return "Unknown", "Unknown"



def score_news_item_llm(item: Dict[str, Any]) -> Dict[str, Any]:
    data = analyze_news_with_llm(item)

    events = data.get("events", [])
    if not isinstance(events, list):
        events = []

    # собираем location из events (если LLM его дал)
    locs = " ".join([
        str(ev.get("location", ""))
        for ev in events
        if isinstance(ev, dict)
    ])

    region, port = resolve_region_and_port(
        item.get("title", ""),
        item.get("summary", ""),
        str(data.get("port", "")),
        locs
    )

    raw = data.get("risk_score", 0.2)
    try:
        risk_score = float(raw)
    except Exception:
        risk_score = 0.2

    out = {
        **item,
        "affected_region": region,   # NEW
        "port": port,                # NEW (уже не только Unknown)
        "matched_events": events,
        "risk_score": round(max(0.0, min(1.0, risk_score)), 3),
        "analyzer": "llm",
        "summary": str(data.get("summary", "")),
    }

    # если у тебя есть _enrich_business_fields(out), оставь:
    # return _enrich_business_fields(out)
    return out


def score_news_item(item: Dict[str, Any], prefer_llm: bool = True) -> Dict[str, Any]:
    if prefer_llm:
        try:
            out = score_news_item_llm(item)
            out["llm_status"] = "ok"
            return out
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            out = score_news_item_rules(item)
            out["llm_status"] = "failed"
            out["llm_error"] = msg

            low = msg.lower()
            if "401" in low or "auth" in low or "invalid" in low:
                out["llm_error_type"] = "auth_invalid_key"
            elif "insufficient" in low or "balance" in low or "quota" in low:
                out["llm_error_type"] = "insufficient_quota"
            elif "timeout" in low or "connection" in low:
                out["llm_error_type"] = "network_timeout"
            else:
                out["llm_error_type"] = "unknown"
            return out

    out = score_news_item_rules(item)
    out["llm_status"] = "disabled"
    out["llm_error_type"] = "llm_disabled"
    return out

def score_news_batch(news: List[Dict[str, Any]], prefer_llm: bool = True, llm_limit: int = 3) -> List[Dict[str, Any]]:
    out = []
    for i, item in enumerate(news):
        use_llm = prefer_llm and i < llm_limit
        out.append(score_news_item(item, prefer_llm=use_llm))
    return out
def resolve_region_and_port(title: str, summary: str, llm_port: str = "", llm_location: str = ""):
    text = f"{title} {summary} {llm_port} {llm_location}".lower()

    # direct ports
    if any(x in text for x in ["shanghai", "上海"]):
        return "China-East", "Shanghai"
    if any(x in text for x in ["ningbo", "宁波", "舟山", "ningbo-zhoushan"]):
        return "China-East", "Ningbo"

    # other CN ports/regions
    if any(x in text for x in ["Hong","shenzhen", "yantian", "guangzhou", "zhonggu", "cosco", "sinotrans", "china shipping", "china merchants",
    "中国", "中远", "招商局", "中国航运", "nansha", "xiamen", "qingdao", "tianjin", "dalian", "中国", "华东", "华南"]):
        return "China", "Other-China"

    # global maritime signals
    if any(x in text for x in ["port", "shipping", "vessel", "container", "freight", "logistics","terminal", "congestion", "backlog", "queue", "航运", "港口", "集装箱", "物流"]):
        return "Global", "Global"

    return "Unknown", "Unknown"

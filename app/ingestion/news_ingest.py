from __future__ import annotations
import feedparser
from datetime import datetime, timezone
from typing import List, Dict, Set, Optional
import re

# Более широкая сетка источников: general + logistics/maritime
DEFAULT_FEEDS = [
    # Reuters (general business)
    "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    # SCMP business
    "https://www.scmp.com/rss/91/feed",
    # Lloyd's List (shipping)
    "https://lloydslist.com/LL1145143/Sections/Container-shipping/rss",
    # The Loadstar (logistics)
    "https://theloadstar.com/feed/",
    # Splash247 (shipping news)
    "https://splash247.com/feed/",
    # MarineLink News
    "https://www.marinelink.com/news/rss",
]

SUPPLY_CHAIN_PATTERNS = [
    r"\bport\b", r"\bshipping\b", r"\bvessel\b", r"\bcontainer\b",
    r"\blogistics\b", r"\bsupply chain\b", r"\bfreight\b",
    r"\bcongestion\b", r"\bcustoms\b", r"\bterminal\b",
    r"\bstrike\b", r"\btyphoon\b", r"\bwarehouse\b",
    r"\bblank sailing\b", r"\bberth\b", r"\bdemurrage\b",
    r"港口", r"航运", r"物流", r"集装箱", r"拥堵", r"码头", r"罢工", r"台风", r"清关"
]

import re

def infer_source_type(title: str, summary: str) -> str:
    t = f"{title} {summary}".lower()

    # 1) weather (самый приоритетный)
    if any(k in t for k in [
    "typhoon", "storm", "rain", "heavy rain", "flood", "flooding", "weather",
    "台风", "暴雨", "洪水", "风暴"
    ]):
        return "weather"


    # 2) customs_notice только если есть торгово-регуляторный контекст
    customs_hit = bool(re.search(r"\bcustoms?\b|海关", t))
    trade_reg_hit = bool(re.search(
        r"sanction|export control|import ban|tariff|duty|trade restriction|compliance|inspection|clearance|制裁|出口管制|关税|通关|监管",
        t
    ))
    if customs_hit and trade_reg_hit:
        return "customs_notice"

    # 3) port_index / ops signal
    if any(k in t for k in [
        "queue", "congestion", "terminal backlog", "berth", "turnaround time",
        "港口拥堵", "排队", "码头", "滞港"
    ]):
        return "port_index"

    return "news"



def _safe_text(x: Optional[str]) -> str:
    return (x or "").strip()


def _extract_summary(entry) -> str:
    """
    RSS entries бывают очень разными:
    summary / description / content[0].value
    """
    summary = _safe_text(getattr(entry, "summary", ""))
    if summary:
        return summary

    description = _safe_text(getattr(entry, "description", ""))
    if description:
        return description

    content = getattr(entry, "content", None)
    if content and isinstance(content, list):
        try:
            val = content[0].get("value", "") if isinstance(content[0], dict) else getattr(content[0], "value", "")
            return _safe_text(val)
        except Exception:
            pass

    return ""


def _extract_published_iso(entry) -> Optional[str]:
    # published_parsed
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass

    # updated_parsed
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass

    return None


def is_supply_chain_relevant(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(re.search(p, text, flags=re.IGNORECASE) for p in SUPPLY_CHAIN_PATTERNS)


def _normalize_item(source_url: str, entry) -> Dict:
    title = _safe_text(getattr(entry, "title", ""))
    link = _safe_text(getattr(entry, "link", ""))
    summary = _extract_summary(entry)
    published_at = _extract_published_iso(entry)

    return {
        "source": source_url,
        "title": title,
        "summary": summary,
        "link": link,
        "published_at": published_at,
        "lang_hint": "unknown",
    }


def fetch_rss_news(max_items: int = 20, relevant_only: bool = True) -> List[Dict]:
    """
    Возвращает до max_items новостей.
    relevant_only=True -> фильтрует по supply-chain паттернам.
    """
    items: List[Dict] = []
    seen: Set[str] = set()

    for url in DEFAULT_FEEDS:
        try:
            feed = feedparser.parse(url)
            entries = getattr(feed, "entries", []) or []
        except Exception:
            entries = []

        for e in entries:
            item = _normalize_item(url, e)

            # Пустые заголовки/ссылки - пропускаем
            if not item["title"] and not item["summary"]:
                continue

            if relevant_only and not is_supply_chain_relevant(item["title"], item["summary"]):
                continue

            # Дедуп по link или title+source
            dedup_key = (item["link"] or f'{item["source"]}::{item["title"]}').strip().lower()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            item["source_type"] = infer_source_type(item.get("title", ""), item.get("summary", ""))

            items.append(item)
            if len(items) >= max_items:
                return items

    return items


def mock_news_for_testing() -> List[Dict]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "source": "mock",
            "title": "Typhoon disrupts vessel schedule near East China Sea",
            "summary": "Severe weather warning may affect port operations and container turnaround time.",
            "link": "https://example.com/mock-1",
            "published_at": now,
            "lang_hint": "en",
        },
        {
            "source": "mock",
            "title": "Labor strike risk reported at major logistics terminal",
            "summary": "Union negotiations stalled, potential delays in loading operations.",
            "link": "https://example.com/mock-2",
            "published_at": now,
            "lang_hint": "en",
        },
        {
            "source": "mock",
            "title": "Supplier insolvency rumor impacts electronics components flow",
            "summary": "Upstream supplier bankruptcy concerns may create procurement bottlenecks.",
            "link": "https://example.com/mock-3",
            "published_at": now,
            "lang_hint": "en",
        },
    ]

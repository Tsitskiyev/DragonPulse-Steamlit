from __future__ import annotations
import json
import re
import time
from typing import Dict, Any

from openai import OpenAI
from openai import AuthenticationError, APIConnectionError, APITimeoutError, RateLimitError

from app.core.config import settings


SYSTEM_PROMPT = """
You are a supply chain risk analyst.
Return STRICT JSON only with this schema:
{
  "port": "Shanghai|Ningbo|Unknown",
  "events": [
    {
      "event_type": "bankruptcy|labor_strike|typhoon_weather|port_congestion|regulatory|cyber_outage|recovery_signal|other",
      "severity": 0.0,
      "confidence": 0.0,
      "location": null,
      "affected_entity": null,
      "expected_duration_days": null
    }
  ],
  "risk_score": 0.0,
  "summary": "short analytical summary"
}
"""


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in model response")
    return json.loads(m.group(0))


def _build_client_and_model():
    provider = settings.llm_provider

    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is empty")
        client = OpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            timeout=25.0,
            max_retries=0,
        )
        return client, settings.groq_model

    if provider == "deepseek":
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is empty")
        client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=25.0,
            max_retries=0,
        )
        return client, settings.deepseek_model

    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}")


def analyze_news_with_llm(item: Dict[str, Any]) -> Dict[str, Any]:
    client, model = _build_client_and_model()

    user_prompt = f"""
Title: {item.get("title", "")}
Summary: {item.get("summary", "")}
Link: {item.get("link", "")}
LanguageHint: {item.get("lang_hint", "unknown")}
"""

    last_err = None
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = resp.choices[0].message.content or ""
            return _extract_json(content)

        except AuthenticationError:
            raise  # 401 ретраить не нужно
        except (APIConnectionError, APITimeoutError, RateLimitError, ValueError) as e:
            last_err = e
            time.sleep(1.0 * (attempt + 1))

    raise last_err if last_err else RuntimeError("Unknown LLM error")

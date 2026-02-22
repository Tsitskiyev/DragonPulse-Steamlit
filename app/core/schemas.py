from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional


class ExtractedEvent(BaseModel):
    event_type: str
    severity: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    location: Optional[str] = None
    affected_entity: Optional[str] = None
    expected_duration_days: Optional[float] = None


class LLMNewsAnalysis(BaseModel):
    port: str
    events: List[ExtractedEvent]
    risk_score: float = Field(ge=0.0, le=1.0)
    summary: str

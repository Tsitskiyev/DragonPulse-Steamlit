from __future__ import annotations
from sqlalchemy import create_engine, String, Float, Integer, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column
from datetime import datetime
from app.core.config import settings

engine = create_engine(settings.db_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class RiskEventORM(Base):
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(Text)
    published_at: Mapped[str] = mapped_column(String(100))
    port: Mapped[str] = mapped_column(String(50))
    risk_score: Mapped[float] = mapped_column(Float)
    matched_events_json: Mapped[str] = mapped_column(Text)
    analyzer: Mapped[str] = mapped_column(String(30))  # "llm" | "rules"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

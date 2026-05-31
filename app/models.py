"""SQLAlchemy ORM models for persisted entities (cars and saved shortlists)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class CarORM(Base):
    __tablename__ = "cars"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    make: Mapped[str] = mapped_column(String, index=True)
    model: Mapped[str] = mapped_column(String)
    variant: Mapped[str] = mapped_column(String)
    price_ex_showroom_inr: Mapped[int] = mapped_column(Integer, index=True)
    body_type: Mapped[str] = mapped_column(String, index=True)
    fuel: Mapped[str] = mapped_column(String, index=True)
    transmissions: Mapped[list] = mapped_column(JSON)
    mileage_kmpl: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seating: Mapped[int] = mapped_column(Integer)
    safety_ncap_stars: Mapped[int] = mapped_column(Integer)
    boot_litres: Mapped[int] = mapped_column(Integer)
    engine_cc: Mapped[int] = mapped_column(Integer)
    power_bhp: Mapped[float] = mapped_column(Float)
    reliability_score: Mapped[float] = mapped_column(Float)
    user_rating: Mapped[float] = mapped_column(Float)
    review_snippets: Mapped[list] = mapped_column(JSON)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    key_features: Mapped[list] = mapped_column(JSON)


class ShortlistORM(Base):
    __tablename__ = "shortlists"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    profile: Mapped[dict] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(String, default="")
    results: Mapped[list] = mapped_column(JSON)
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

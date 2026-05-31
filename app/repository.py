"""Data-access layer: load the catalogue and persist shortlists.

Keeps all DB interaction in one place so services stay free of ORM details.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CarORM, ShortlistORM
from .schemas import BuyerProfile, Car, ScoredCar

_DATA_FILE = Path(__file__).parent / "data" / "cars.json"


def load_cars_from_file() -> list[Car]:
    """Read the curated dataset from disk (source of truth for seeding)."""
    raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    return [Car(**item) for item in raw]


def seed_cars(db: Session) -> int:
    """Populate the cars table from the dataset if it is empty. Idempotent."""
    existing = db.scalar(select(CarORM).limit(1))
    if existing is not None:
        return 0
    cars = load_cars_from_file()
    db.add_all(CarORM(**car.model_dump()) for car in cars)
    db.commit()
    return len(cars)


def list_cars(db: Session) -> list[Car]:
    rows = db.scalars(select(CarORM)).all()
    return [Car.model_validate(row, from_attributes=True) for row in rows]


def get_cars_by_ids(db: Session, ids: list[str]) -> list[Car]:
    rows = db.scalars(select(CarORM).where(CarORM.id.in_(ids))).all()
    by_id = {row.id: Car.model_validate(row, from_attributes=True) for row in rows}
    return [by_id[i] for i in ids if i in by_id]


def save_shortlist(
    db: Session,
    shortlist_id: str,
    profile: BuyerProfile,
    summary: str,
    cars: list[ScoredCar],
    llm_used: bool = False,
) -> None:
    db.add(
        ShortlistORM(
            id=shortlist_id,
            profile=profile.model_dump(),
            summary=summary,
            results=[c.model_dump() for c in cars],
            llm_used=llm_used,
        )
    )
    db.commit()


def get_shortlist(db: Session, shortlist_id: str) -> ShortlistORM | None:
    return db.get(ShortlistORM, shortlist_id)

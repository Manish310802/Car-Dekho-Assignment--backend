"""Standalone seed script: ``python -m app.seed``.

Creates tables and loads the curated catalogue into the configured database
(Neon Postgres or the local SQLite fallback). Safe to run repeatedly.
"""

from __future__ import annotations

from .db import Base, SessionLocal, engine
from .repository import seed_cars


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        inserted = seed_cars(db)
    if inserted:
        print(f"Seeded {inserted} cars.")
    else:
        print("Catalogue already seeded — nothing to do.")


if __name__ == "__main__":
    main()

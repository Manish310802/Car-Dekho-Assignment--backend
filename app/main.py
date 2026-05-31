"""FastAPI application: routes are thin wrappers over the service layer."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import repository, services
from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .schemas import BuyerProfile, Car, RecommendResponse, RefineRequest


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Create tables and seed the catalogue on first boot — makes local runs
    # zero-setup (no manual migration/seed step required).
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        repository.seed_cars(db)
    yield


app = FastAPI(title="CarDekho AI Advisor", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {"status": "ok", "llm_enabled": settings.llm_enabled}


@app.get("/api/cars", response_model=list[Car])
def get_cars(db: Session = Depends(get_db)) -> list[Car]:
    return repository.list_cars(db)


@app.post("/api/recommend", response_model=RecommendResponse)
def post_recommend(profile: BuyerProfile, db: Session = Depends(get_db)) -> dict:
    return services.recommend(db, profile)


@app.post("/api/refine", response_model=RecommendResponse)
def post_refine(req: RefineRequest, db: Session = Depends(get_db)) -> dict:
    result = services.refine(db, req.shortlist_id, req.message)
    if result is None:
        raise HTTPException(status_code=404, detail="Shortlist not found")
    return result


@app.get("/api/shortlist/{shortlist_id}", response_model=RecommendResponse)
def get_shortlist(shortlist_id: str, db: Session = Depends(get_db)) -> dict:
    row = repository.get_shortlist(db, shortlist_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Shortlist not found")
    return {
        "shortlist_id": row.id,
        "summary": row.summary,
        "profile": row.profile,
        "cars": row.results,
        "llm_used": row.llm_used,
    }

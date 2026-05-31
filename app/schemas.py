"""Pydantic request/response schemas — the typed API contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

UseCase = Literal["city_commute", "family", "first_car", "performance", "off_road", "long_highway"]
FuelPref = Literal["petrol", "diesel", "cng", "electric", "hybrid", "no_preference"]
TransmissionPref = Literal["manual", "automatic", "no_preference"]
Priority = Literal["mileage", "safety", "performance", "features", "low_maintenance", "resale"]


class Car(BaseModel):
    """A single car in the catalogue (mirrors the dataset / ORM)."""

    id: str
    make: str
    model: str
    variant: str
    price_ex_showroom_inr: int
    body_type: str
    fuel: str
    transmissions: list[str]
    mileage_kmpl: float | None = None
    range_km: int | None = None
    seating: int
    safety_ncap_stars: int
    boot_litres: int
    engine_cc: int
    power_bhp: float
    reliability_score: float
    user_rating: float
    review_snippets: list[str] = []
    image_url: str | None = None
    key_features: list[str] = []


class BuyerProfile(BaseModel):
    """Everything we capture from the buyer's wizard answers."""

    budget_min_inr: int = Field(default=0, ge=0)
    budget_max_inr: int = Field(..., ge=100000)
    use_case: UseCase = "family"
    seats: int = Field(default=5, ge=2, le=9)
    fuel_pref: FuelPref = "no_preference"
    transmission_pref: TransmissionPref = "no_preference"
    priorities: list[Priority] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    """Per-attribute fit scores (0-100) that explain the overall match."""

    budget: int
    use_case: int
    seats: int
    fuel: int
    transmission: int
    priorities: int


class ScoredCar(BaseModel):
    """A car plus its computed fit and the (grounded) LLM rationale."""

    car: Car
    match_score: int
    breakdown: ScoreBreakdown
    rationale: str = ""
    watch_outs: str = ""


class RecommendResponse(BaseModel):
    shortlist_id: str
    summary: str
    profile: BuyerProfile
    cars: list[ScoredCar]
    llm_used: bool


class RefineRequest(BaseModel):
    shortlist_id: str
    message: str = Field(..., min_length=1, max_length=500)

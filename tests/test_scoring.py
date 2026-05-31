"""Smoke tests for the deterministic scoring engine.

These assert ranking *sanity* (the engine surfaces sensible cars for a profile),
not exact scores — the weights are expected to be tuned over time.
"""

from __future__ import annotations

from app.repository import load_cars_from_file
from app.schemas import BuyerProfile
from app.scoring import score_cars

CARS = load_cars_from_file()


def test_returns_top_n_sorted_descending() -> None:
    profile = BuyerProfile(budget_max_inr=1500000, use_case="family")
    result = score_cars(profile, CARS, top_n=5)

    assert len(result) == 5
    scores = [c.match_score for c in result]
    assert scores == sorted(scores, reverse=True)


def test_ev_preference_surfaces_electric_cars() -> None:
    profile = BuyerProfile(
        budget_max_inr=2500000, use_case="family", fuel_pref="electric", priorities=["mileage"]
    )
    top = score_cars(profile, CARS, top_n=3)
    assert all(c.car.fuel == "electric" for c in top)


def test_safety_priority_prefers_high_ncap() -> None:
    profile = BuyerProfile(budget_max_inr=1500000, use_case="family", priorities=["safety"])
    top = score_cars(profile, CARS, top_n=5)
    # The best match should carry a strong safety rating.
    assert top[0].car.safety_ncap_stars >= 4


def test_respects_budget_ceiling() -> None:
    profile = BuyerProfile(budget_max_inr=700000, use_case="city_commute")
    top = score_cars(profile, CARS, top_n=5)
    # Nothing wildly over budget should win for a tight city-car budget.
    assert top[0].car.price_ex_showroom_inr <= 900000


def test_seven_seater_need_prefers_larger_cars() -> None:
    profile = BuyerProfile(budget_max_inr=3000000, use_case="family", seats=7)
    top = score_cars(profile, CARS, top_n=3)
    assert all(c.car.seating >= 7 for c in top)

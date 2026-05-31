"""Deterministic scoring engine — the non-trivial backend computation.

Given a :class:`BuyerProfile` and the catalogue, every car is scored on six
independent, transparent sub-scores (each 0-1) that are combined into a single
weighted match score (0-100). The per-attribute breakdown is returned alongside
so the UI can explain *why* a car ranked where it did — transparency is what
turns a confused buyer into a confident one.

This module is pure (no I/O, no DB, no LLM) which makes it trivially testable.
"""

from __future__ import annotations

from .schemas import BuyerProfile, Car, ScoreBreakdown, ScoredCar

# Relative importance of each dimension. Tuned so budget and use-case dominate
# while the buyer's chosen priorities still meaningfully move the ranking.
WEIGHTS: dict[str, float] = {
    "budget": 0.30,
    "use_case": 0.20,
    "seats": 0.15,
    "fuel": 0.12,
    "transmission": 0.05,
    "priorities": 0.18,
}

# Which body styles suit each use case, and how well (0-1).
_USE_CASE_BODY: dict[str, dict[str, float]] = {
    "city_commute": {"hatchback": 1.0, "compact_suv": 0.85, "sedan": 0.6, "suv": 0.45, "mpv": 0.4},
    "family": {"suv": 1.0, "mpv": 1.0, "sedan": 0.8, "compact_suv": 0.75, "hatchback": 0.45},
    "first_car": {"hatchback": 1.0, "compact_suv": 0.85, "sedan": 0.65, "suv": 0.4, "mpv": 0.4},
    "performance": {"sedan": 0.85, "suv": 0.8, "compact_suv": 0.7, "hatchback": 0.65, "mpv": 0.4},
    "off_road": {"suv": 1.0, "compact_suv": 0.55, "mpv": 0.4, "sedan": 0.2, "hatchback": 0.2},
    "long_highway": {"sedan": 1.0, "suv": 0.95, "mpv": 0.85, "compact_suv": 0.6, "hatchback": 0.45},
}

# Treat an EV's near-zero running cost as equivalent to a very efficient ICE car
# when the buyer prioritises mileage / low running costs.
_EV_EFFICIENCY_EQUIV_KMPL = 32.0


def _budget_fit(price: int, lo: int, hi: int) -> float:
    """1.0 inside budget; steep penalty over, mild penalty far under."""
    if price > hi:
        over = (price - hi) / hi
        return max(0.0, 1.0 - 2.0 * over)
    if lo and price < lo:
        under = (lo - price) / lo
        return max(0.4, 1.0 - 0.5 * under)
    return 1.0


def _use_case_fit(car: Car, profile: BuyerProfile, max_power: float) -> float:
    base = _USE_CASE_BODY.get(profile.use_case, {}).get(car.body_type, 0.4)
    if profile.use_case == "performance" and max_power > 0:
        # Blend body suitability with how powerful the car is.
        return 0.5 * base + 0.5 * (car.power_bhp / max_power)
    if profile.use_case == "off_road":
        # Reward genuine off-road kit when present.
        if any("4wd" in f.lower() or "off-road" in f.lower() for f in car.key_features):
            return min(1.0, base + 0.15)
    return base


def _seats_fit(car: Car, needed: int) -> float:
    if car.seating >= needed:
        return 1.0
    return max(0.0, 1.0 - 0.5 * (needed - car.seating))


def _fuel_fit(car: Car, pref: str) -> float:
    if pref == "no_preference":
        return 1.0
    return 1.0 if car.fuel == pref else 0.2


def _transmission_fit(car: Car, pref: str) -> float:
    if pref == "no_preference":
        return 1.0
    return 1.0 if pref in car.transmissions else 0.3


def _efficiency(car: Car) -> float:
    if car.fuel == "electric":
        return _EV_EFFICIENCY_EQUIV_KMPL
    return car.mileage_kmpl or 0.0


def _priority_raw(car: Car, priority: str) -> float:
    """Raw (un-normalised) value of a single priority attribute for a car."""
    if priority == "mileage":
        return _efficiency(car)
    if priority == "safety":
        return float(car.safety_ncap_stars)
    if priority == "performance":
        return car.power_bhp
    if priority == "features":
        return float(len(car.key_features))
    if priority == "low_maintenance":
        return car.reliability_score
    if priority == "resale":
        return car.reliability_score / 10 + car.user_rating / 5
    return 0.0


def _normalise(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return (value - lo) / (hi - lo)


def score_cars(profile: BuyerProfile, cars: list[Car], top_n: int = 5) -> list[ScoredCar]:
    """Rank ``cars`` for ``profile`` and return the best ``top_n`` with breakdowns."""
    if not cars:
        return []

    max_power = max(c.power_bhp for c in cars)

    # Pre-compute min/max for each chosen priority so we can min-max normalise.
    priority_bounds: dict[str, tuple[float, float]] = {}
    for priority in profile.priorities:
        values = [_priority_raw(c, priority) for c in cars]
        priority_bounds[priority] = (min(values), max(values))

    scored: list[ScoredCar] = []
    for car in cars:
        subs = {
            "budget": _budget_fit(car.price_ex_showroom_inr, profile.budget_min_inr, profile.budget_max_inr),
            "use_case": _use_case_fit(car, profile, max_power),
            "seats": _seats_fit(car, profile.seats),
            "fuel": _fuel_fit(car, profile.fuel_pref),
            "transmission": _transmission_fit(car, profile.transmission_pref),
        }

        if profile.priorities:
            normalised = [_normalise(_priority_raw(car, p), *priority_bounds[p]) for p in profile.priorities]
            subs["priorities"] = sum(normalised) / len(normalised)
        else:
            subs["priorities"] = 0.6  # neutral when the buyer states no priorities

        total = sum(WEIGHTS[k] * v for k, v in subs.items())
        scored.append(
            ScoredCar(
                car=car,
                match_score=round(total * 100),
                breakdown=ScoreBreakdown(**{k: round(v * 100) for k, v in subs.items()}),
            )
        )

    scored.sort(key=lambda s: s.match_score, reverse=True)
    return scored[:top_n]

"""Application services — orchestrate scoring, the LLM agent, and persistence.

Routes stay thin; all business logic lives here.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from . import repository
from .agent import run_agent
from .llm import templated_rationale
from .schemas import BuyerProfile, ScoredCar

_RECOMMEND_SYSTEM = (
    "You are CarDekho's expert car-buying advisor for the Indian market. You help a "
    "confused buyer reach a confident shortlist. Ground EVERY factual claim only in the "
    "data returned by the tools — never invent prices, specs or safety ratings. Call "
    "filter_and_rank_cars exactly once with the buyer's profile to get the ranked "
    "candidates. Then respond with ONLY a JSON object (no markdown, no prose) shaped as: "
    '{"summary": str, "cars": [{"id": str, "rationale": str, "watch_outs": str}]}. '
    "'summary' is one encouraging sentence addressed to the buyer. 'rationale' is two warm "
    "sentences explaining why THIS car fits THIS buyer, citing concrete specs from the tool "
    "result. 'watch_outs' is one honest caveat, or an empty string. Include every car the "
    "tool returned, in the same order."
)

_REFINE_SYSTEM = (
    _RECOMMEND_SYSTEM
    + " The buyer already has a shortlist and wants to refine it. Interpret their message as "
    "a change to their profile (e.g. 'cheaper' lowers budget_max_inr, 'more space' or "
    "'7-seater' raises seats, 'electric' sets fuel_pref). Call filter_and_rank_cars with the "
    "full UPDATED profile."
)


def _format_lakhs(amount: int) -> str:
    return f"₹{amount / 100000:.1f}L"


def _fallback_summary(profile: BuyerProfile, n: int) -> str:
    return (
        f"Based on a budget up to {_format_lakhs(profile.budget_max_inr)} and a focus on "
        f"{profile.use_case.replace('_', ' ')}, here are the {n} cars that fit you best."
    )


def _parse_llm_json(content: str | None) -> dict[str, Any] | None:
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Be forgiving if the model wrapped JSON in prose/markdown fences.
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _attach_rationale(scored: list[ScoredCar], parsed: dict[str, Any] | None) -> None:
    """Merge LLM-written rationale onto the authoritative scored cars, by id."""
    by_id = {c.get("id"): c for c in (parsed or {}).get("cars", [])}
    for s in scored:
        extra = by_id.get(s.car.id)
        if extra and extra.get("rationale"):
            s.rationale = extra.get("rationale", "")
            s.watch_outs = extra.get("watch_outs", "")
        else:
            s.rationale, s.watch_outs = templated_rationale(s)


def _advise(
    profile: BuyerProfile, cars: list, system: str, user: str
) -> tuple[list[ScoredCar], BuyerProfile, str, bool]:
    """Drive the agent (or fall back) and return (scored, profile, summary, llm_used)."""
    from .scoring import score_cars

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    result = run_agent(messages, cars)

    if result is None:  # no LLM provider configured
        scored = score_cars(profile, cars)
        _attach_rationale(scored, None)
        return scored, profile, _fallback_summary(profile, len(scored)), False

    ctx = result["ctx"]
    scored = ctx.last_scored or score_cars(profile, cars)
    final_profile = ctx.last_profile or profile
    parsed = _parse_llm_json(result["content"])
    _attach_rationale(scored, parsed)
    summary = (parsed or {}).get("summary") or _fallback_summary(final_profile, len(scored))
    return scored, final_profile, summary, True


def recommend(db: Session, profile: BuyerProfile) -> dict[str, Any]:
    cars = repository.list_cars(db)
    user = f"Here is the buyer's profile as JSON:\n{profile.model_dump_json()}\nRecommend the shortlist."
    scored, final_profile, summary, llm_used = _advise(profile, cars, _RECOMMEND_SYSTEM, user)

    shortlist_id = uuid.uuid4().hex[:10]
    repository.save_shortlist(db, shortlist_id, final_profile, summary, scored, llm_used=llm_used)
    return {
        "shortlist_id": shortlist_id,
        "summary": summary,
        "profile": final_profile,
        "cars": scored,
        "llm_used": llm_used,
    }


def refine(db: Session, shortlist_id: str, message: str) -> dict[str, Any] | None:
    existing = repository.get_shortlist(db, shortlist_id)
    if existing is None:
        return None

    profile = BuyerProfile(**existing.profile)
    cars = repository.list_cars(db)
    user = (
        f"Current profile JSON:\n{profile.model_dump_json()}\n"
        f'The buyer says: "{message}"\nUpdate the profile accordingly and re-rank.'
    )
    scored, final_profile, summary, llm_used = _advise(profile, cars, _REFINE_SYSTEM, user)

    new_id = uuid.uuid4().hex[:10]
    repository.save_shortlist(db, new_id, final_profile, summary, scored, llm_used=llm_used)
    return {
        "shortlist_id": new_id,
        "summary": summary,
        "profile": final_profile,
        "cars": scored,
        "llm_used": llm_used,
    }

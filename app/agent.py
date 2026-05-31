"""Bounded function-calling agent.

The LLM is given two typed tools and orchestrates them in a short, capped loop:

* ``filter_and_rank_cars`` — runs the deterministic scoring engine on the real
  catalogue and returns ranked candidates. The model never invents rankings.
* ``compare_cars`` — fetches full specs for specific cars (used when refining).

The model's only creative job is writing the *rationale* — and it is instructed
to ground every claim in the specs the tools return. Match scores always come
from :mod:`app.scoring`, never from the model, so correctness stays defensible.
"""

from __future__ import annotations

import json
from typing import Any

from .llm import get_client
from .schemas import BuyerProfile, Car, ScoredCar
from .scoring import score_cars

MAX_HOPS = 4
TOP_N = 5

_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "budget_min_inr": {"type": "integer", "description": "Lower budget bound (ex-showroom INR)."},
        "budget_max_inr": {"type": "integer", "description": "Upper budget bound (ex-showroom INR)."},
        "use_case": {
            "type": "string",
            "enum": ["city_commute", "family", "first_car", "performance", "off_road", "long_highway"],
        },
        "seats": {"type": "integer", "description": "Minimum seats required (2-9)."},
        "fuel_pref": {
            "type": "string",
            "enum": ["petrol", "diesel", "cng", "electric", "hybrid", "no_preference"],
        },
        "transmission_pref": {"type": "string", "enum": ["manual", "automatic", "no_preference"]},
        "priorities": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["mileage", "safety", "performance", "features", "low_maintenance", "resale"],
            },
        },
    },
    "required": ["budget_max_inr", "use_case"],
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "filter_and_rank_cars",
            "description": "Rank the real car catalogue against a buyer profile and return the top matches with scores. Call this to get candidates — never invent cars.",
            "parameters": _PROFILE_SCHEMA,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_cars",
            "description": "Fetch full specifications for specific car ids, for side-by-side comparison.",
            "parameters": {
                "type": "object",
                "properties": {"ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["ids"],
            },
        },
    },
]


def _brief(scored: ScoredCar) -> dict[str, Any]:
    """Compact, model-facing view of a scored car (specs the rationale may cite)."""
    c = scored.car
    return {
        "id": c.id,
        "name": f"{c.make} {c.model} {c.variant}",
        "price_inr": c.price_ex_showroom_inr,
        "body_type": c.body_type,
        "fuel": c.fuel,
        "transmissions": c.transmissions,
        "seating": c.seating,
        "safety_ncap_stars": c.safety_ncap_stars,
        "mileage_kmpl": c.mileage_kmpl,
        "range_km": c.range_km,
        "power_bhp": c.power_bhp,
        "boot_litres": c.boot_litres,
        "key_features": c.key_features,
        "match_score": scored.match_score,
    }


class _AgentContext:
    """Carries state across tool calls within a single agent run."""

    def __init__(self, cars: list[Car]) -> None:
        self.cars = cars
        self.last_profile: BuyerProfile | None = None
        self.last_scored: list[ScoredCar] = []

    def filter_and_rank_cars(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        profile = BuyerProfile(**args)
        self.last_profile = profile
        self.last_scored = score_cars(profile, self.cars, top_n=TOP_N)
        return [_brief(s) for s in self.last_scored]

    def compare_cars(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        wanted = set(args.get("ids", []))
        return [
            _brief(ScoredCar(car=c, match_score=0, breakdown=_ZERO_BREAKDOWN))
            for c in self.cars
            if c.id in wanted
        ]

    def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        if name == "filter_and_rank_cars":
            return self.filter_and_rank_cars(args)
        if name == "compare_cars":
            return self.compare_cars(args)
        return {"error": f"unknown tool {name}"}


# Imported lazily to avoid a circular import at module load.
from .schemas import ScoreBreakdown  # noqa: E402

_ZERO_BREAKDOWN = ScoreBreakdown(budget=0, use_case=0, seats=0, fuel=0, transmission=0, priorities=0)


def run_agent(messages: list[dict[str, Any]], cars: list[Car]) -> dict[str, Any] | None:
    """Run the capped tool-calling loop.

    Returns ``{"content": str | None, "ctx": _AgentContext}`` or ``None`` when no
    LLM provider is configured (the caller then uses the templated fallback).
    """
    client, model = get_client()
    if client is None:
        return None

    ctx = _AgentContext(cars)
    for _ in range(MAX_HOPS):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.4,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return {"content": msg.content, "ctx": ctx}

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = ctx.dispatch(tc.function.name, args)
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)}
            )

    return {"content": None, "ctx": ctx}

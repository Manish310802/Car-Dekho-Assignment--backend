"""LLM client factory and a deterministic templated fallback.

Provider order: OpenAI (``OPENAI_API_KEY``) → xAI Grok (``XAI_API_KEY``). Because
xAI is OpenAI-API compatible, a single :class:`OpenAI` client wraps both. If
neither key is configured, the app still produces useful rationale text from the
scoring breakdown via :func:`templated_rationale`.
"""

from __future__ import annotations

from openai import OpenAI

from .config import settings
from .schemas import ScoredCar


def get_client() -> tuple[OpenAI | None, str]:
    """Return an (client, model) pair for the active provider, or (None, '')."""
    if settings.openai_api_key:
        return OpenAI(api_key=settings.openai_api_key), settings.openai_model
    if settings.xai_api_key:
        return (
            OpenAI(api_key=settings.xai_api_key, base_url="https://api.x.ai/v1"),
            settings.xai_model,
        )
    return None, ""


# --- Deterministic fallback used when no LLM provider is configured ----------

_STRENGTH_PHRASES = {
    "budget": "sits comfortably within your budget",
    "use_case": "is well suited to how you'll use it",
    "seats": "has the seating you need",
    "fuel": "matches your fuel preference",
    "transmission": "offers your preferred gearbox",
    "priorities": "scores well on the things you care about most",
}
_WEAKNESS_PHRASES = {
    "budget": "is priced above your stated budget",
    "use_case": "isn't the most natural body style for your use case",
    "seats": "may be tight on seating",
    "fuel": "doesn't match your fuel preference",
    "transmission": "may not offer your preferred gearbox",
    "priorities": "is average on your stated priorities",
}


def templated_rationale(scored: ScoredCar) -> tuple[str, str]:
    """Build (rationale, watch_outs) from the score breakdown without an LLM."""
    items = scored.breakdown.model_dump()
    best = sorted(items.items(), key=lambda kv: kv[1], reverse=True)[:2]
    worst = min(items.items(), key=lambda kv: kv[1])
    car = scored.car

    strengths = " and ".join(_STRENGTH_PHRASES[k] for k, _ in best)
    rationale = f"The {car.make} {car.model} {strengths}."
    if car.safety_ncap_stars >= 4:
        rationale += f" It also carries a {car.safety_ncap_stars}-star safety rating."

    watch_outs = ""
    if worst[1] < 60:
        watch_outs = f"Worth noting: it {_WEAKNESS_PHRASES[worst[0]]}."
    return rationale, watch_outs

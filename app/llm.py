"""High-level LLM helpers used by generative stages.

Every generative stage is designed to run with *zero* external dependencies:
it supplies a deterministic ``fallback`` builder. When a free hosted model is
configured (OpenRouter) we try it first for quality, validate the output, and
fall back to the deterministic builder on any error. This keeps the pipeline
fully functional offline and in CI while still benefiting from a real model
when one is available — and it never selects a paid model.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.config import Settings, get_settings
from app.providers.llm import LLMResult, build_llm_chain


def _chain(settings: Settings | None, on_alert):
    return build_llm_chain(settings=settings, on_alert=on_alert)


def complete_json(
    prompt: str,
    *,
    system: str = "",
    fallback: Callable[[], Any],
    validate: Callable[[Any], bool] | None = None,
    settings: Settings | None = None,
    on_alert=None,
    max_tokens: int = 2000,
) -> tuple[Any, str]:
    """Return ``(value, provider_name)``.

    Tries hosted free models for JSON output; on any failure or validation miss
    returns the deterministic ``fallback()`` tagged as ``"deterministic"``.
    """
    settings = settings or get_settings()
    chain = _chain(settings, on_alert)
    # Only attempt hosted models that are actually available (configured key).
    if any(p.available() for p in chain.providers if p.name != "offline-llm"):
        try:
            outcome = chain.call(prompt, system=system, max_tokens=max_tokens)
            result: LLMResult = outcome.value
            value = result.json()
            if validate is None or validate(value):
                return value, outcome.provider
        except Exception:
            pass
    return fallback(), "deterministic"


def complete_text(
    prompt: str,
    *,
    system: str = "",
    fallback: Callable[[], str],
    settings: Settings | None = None,
    on_alert=None,
    max_tokens: int = 2000,
) -> tuple[str, str]:
    settings = settings or get_settings()
    chain = _chain(settings, on_alert)
    if any(p.available() for p in chain.providers if p.name != "offline-llm"):
        try:
            outcome = chain.call(prompt, system=system, max_tokens=max_tokens)
            text = outcome.value.text.strip()
            if text:
                return text, outcome.provider
        except Exception:
            pass
    return fallback(), "deterministic"

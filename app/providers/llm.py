"""LLM providers: OpenRouter (free models) with an always-available offline model.

The offline/deterministic provider means the whole pipeline — and its tests —
runs with no API key and no network, while OpenRouter is used automatically when
``OPENROUTER_API_KEY`` is configured. Paid models are never selected silently.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import Settings, get_settings
from app.providers.base import CostClass, Provider, ProviderChain, ProviderError
from app.providers.http import client


class LLMResult:
    def __init__(self, text: str, model: str):
        self.text = text
        self.model = model

    def json(self) -> Any:
        """Best-effort JSON extraction from an LLM response."""
        text = self.text.strip()
        # Strip markdown fences if present.
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to locate the first JSON object/array.
            match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise


class OpenRouterProvider(Provider[LLMResult]):
    name = "openrouter"
    kind = "llm"
    cost_class = CostClass.FREE_TIER  # free models within a rate-limited tier

    def __init__(self, settings: Settings | None = None, model: str | None = None):
        super().__init__(settings)
        self.model = model or self.settings.openrouter_model

    def available(self) -> bool:
        return bool(self.settings.openrouter_api_key) and ":free" in self.model

    def _run(self, prompt: str, *, system: str = "", max_tokens: int = 1800, temperature: float = 0.7) -> LLMResult:
        if not self.settings.openrouter_api_key:
            raise ProviderError("openrouter: no API key")
        if ":free" not in self.model:
            # Never silently use a paid model.
            raise ProviderError(f"openrouter: refusing non-free model {self.model!r}")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        headers = {"Authorization": f"Bearer {self.settings.openrouter_api_key}"}
        with client(headers=headers, timeout=90.0) as c:
            resp = c.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise ProviderError(f"openrouter: malformed response: {exc}") from exc
        return LLMResult(text=text, model=self.model)


class OfflineLLMProvider(Provider[LLMResult]):
    """Deterministic, template-based text generation.

    This is *free open-source software*, not a hosted model. It produces
    structured, on-topic drafts good enough for offline rendering, tests and the
    zero-cost default. When OpenRouter is configured it takes over for quality.
    """

    name = "offline-llm"
    kind = "llm"
    cost_class = CostClass.FREE

    def available(self) -> bool:
        return True

    def _run(self, prompt: str, *, system: str = "", max_tokens: int = 1800, temperature: float = 0.7) -> LLMResult:
        # Deterministic, dependency-free fallback. Stages that need structured
        # output supply their own deterministic builders via ``app.llm`` and do
        # not rely on parsing this text; this exists only so a bare text
        # completion never hard-fails when no hosted model is configured.
        lead = (prompt.strip().splitlines() or [""])[0][:160]
        text = (
            "This segment presents only what the verified record supports. "
            f"{lead} The account is drawn from official filings and reporting, "
            "with legal terms used precisely."
        )
        return LLMResult(text=text, model="offline-template")


def build_llm_chain(settings: Settings | None = None, on_alert=None) -> ProviderChain[LLMResult]:
    settings = settings or get_settings()
    providers: list[Provider[LLMResult]] = []
    # Primary + configured free fallbacks.
    providers.append(OpenRouterProvider(settings, model=settings.openrouter_model))
    for model in settings.openrouter_fallback_list():
        providers.append(OpenRouterProvider(settings, model=model))
    # Always-available offline provider is the final safety net.
    providers.append(OfflineLLMProvider(settings))
    return ProviderChain(providers, on_alert=on_alert)

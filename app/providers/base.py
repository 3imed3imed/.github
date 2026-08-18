"""Provider base classes, cost guard, and fallback chain."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

from app.config import Settings, get_settings

T = TypeVar("T")


class CostClass(str, Enum):
    """How a provider relates to money."""

    FREE = "free"  # open-source / no-key / unlimited-ish free tier
    FREE_TIER = "free_tier"  # free within a quota, paid beyond (we stop at the quota)
    PAID = "paid"  # always costs money — blocked unless ALLOW_PAID_SERVICES=true


class ProviderError(RuntimeError):
    """Recoverable provider failure — the chain should try the next provider."""


class QuotaExhausted(ProviderError):
    """The provider's free quota is used up for the current window."""


class PaidServiceBlocked(ProviderError):
    """A paid provider was asked to run while ALLOW_PAID_SERVICES=false."""


@dataclass
class ProviderStats:
    requests: int = 0
    failures: int = 0
    quota_used: int = 0

    def snapshot(self) -> dict[str, int]:
        return {"requests": self.requests, "failures": self.failures, "quota_used": self.quota_used}


class Provider(Generic[T]):
    """Base class for every external capability.

    Subclasses implement :meth:`_run`. The public :meth:`call` wraps it with the
    cost guard, quota accounting and bookkeeping every provider must expose:
    name, cost class, quota, request count, failure count and fallback.
    """

    #: Human name, e.g. ``"openrouter"`` or ``"pexels"``.
    name: str = "provider"
    #: Capability family, e.g. ``"llm"``, ``"tts"``, ``"video"``, ``"stock"``.
    kind: str = "generic"
    cost_class: CostClass = CostClass.FREE
    #: Per-window free quota. ``None`` means "effectively unlimited / unknown".
    quota: int | None = None
    #: Estimated ¥ cost of one successful call (0 for free providers).
    unit_cost_yen: float = 0.0

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.stats = ProviderStats()
        #: Optional next provider to try if this one fails/exhausts.
        self.fallback: Provider | None = None

    # -- to be implemented by subclasses ----------------------------------- #
    def available(self) -> bool:
        """Whether the provider is configured well enough to attempt a call."""
        return True

    def _run(self, *args: Any, **kwargs: Any) -> T:  # pragma: no cover - abstract
        raise NotImplementedError

    # -- public, guarded entry point --------------------------------------- #
    def call(self, *args: Any, **kwargs: Any) -> T:
        self._enforce_cost_rule()
        self._enforce_quota()
        self.stats.requests += 1
        try:
            result = self._run(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - re-raised as ProviderError below
            self.stats.failures += 1
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(f"{self.name}: {exc}") from exc
        if self.cost_class in (CostClass.FREE_TIER, CostClass.PAID):
            self.stats.quota_used += 1
        return result

    # -- guards ------------------------------------------------------------ #
    def _enforce_cost_rule(self) -> None:
        if self.cost_class is CostClass.PAID and not self.settings.safety.allow_paid_services:
            raise PaidServiceBlocked(
                f"{self.name} is a PAID provider but ALLOW_PAID_SERVICES=false. Refusing to spend."
            )

    def _enforce_quota(self) -> None:
        if self.quota is not None and self.stats.quota_used >= self.quota:
            raise QuotaExhausted(f"{self.name} quota exhausted ({self.quota}).")

    def actual_cost_yen(self) -> float:
        """Realised spend. Must be 0 while paid services are disallowed."""
        if not self.settings.safety.allow_paid_services:
            return 0.0
        if self.cost_class is CostClass.PAID:
            return self.stats.quota_used * self.unit_cost_yen
        return 0.0

    def describe(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "kind": self.kind,
            "cost_class": self.cost_class.value,
            "quota": self.quota,
            "requests": self.stats.requests,
            "failures": self.stats.failures,
            "quota_used": self.stats.quota_used,
            "available": self.available(),
            "fallback": self.fallback.name if self.fallback else None,
            "actual_cost_yen": self.actual_cost_yen(),
        }


@dataclass
class ChainOutcome(Generic[T]):
    value: T
    provider: str
    attempts: list[str] = field(default_factory=list)


class ProviderChain(Generic[T]):
    """Ordered list of providers tried free-first with automatic fallback.

    If every provider fails or is exhausted the chain raises the last error so
    the caller can pause the job and alert — it never falls back to paying money
    because paid providers are blocked at the :class:`Provider` level.
    """

    def __init__(self, providers: list[Provider[T]], on_alert: Callable[[str], None] | None = None):
        # Free providers first, then free-tier, then (blocked) paid — stable within class.
        order = {CostClass.FREE: 0, CostClass.FREE_TIER: 1, CostClass.PAID: 2}
        self.providers = sorted(providers, key=lambda p: order[p.cost_class])
        self.on_alert = on_alert

    def usable(self) -> list[Provider[T]]:
        return [p for p in self.providers if p.available()]

    def call(self, *args: Any, **kwargs: Any) -> ChainOutcome[T]:
        attempts: list[str] = []
        last_error: Exception | None = None
        for provider in self.providers:
            if not provider.available():
                continue
            # Skip paid providers entirely when spending is disallowed.
            if provider.cost_class is CostClass.PAID and not provider.settings.safety.allow_paid_services:
                attempts.append(f"{provider.name}(skipped:paid)")
                continue
            attempts.append(provider.name)
            try:
                value = provider.call(*args, **kwargs)
                return ChainOutcome(value=value, provider=provider.name, attempts=attempts)
            except (QuotaExhausted, ProviderError) as exc:
                last_error = exc
                time.sleep(0)  # cooperative yield; real backoff handled by caller
                continue
        msg = f"All providers exhausted for kind={self._kind()}: {attempts}"
        if self.on_alert:
            self.on_alert(msg)
        raise ProviderError(msg) from last_error

    def _kind(self) -> str:
        return self.providers[0].kind if self.providers else "unknown"

    def describe(self) -> list[dict[str, Any]]:
        return [p.describe() for p in self.providers]

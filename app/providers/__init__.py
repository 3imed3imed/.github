"""Provider abstraction layer.

Every external capability (LLM, TTS, video, stock media, legal lookup) is
accessed through a :class:`~app.providers.base.Provider`. The base class
enforces the hard cost rule: a paid provider cannot run unless the owner has
explicitly set ``ALLOW_PAID_SERVICES=true``. Free providers are always tried
first; when they are exhausted the job pauses and alerts instead of spending
money.
"""

from app.providers.base import (
    CostClass,
    PaidServiceBlocked,
    Provider,
    ProviderChain,
    ProviderError,
    QuotaExhausted,
)

__all__ = [
    "CostClass",
    "PaidServiceBlocked",
    "Provider",
    "ProviderChain",
    "ProviderError",
    "QuotaExhausted",
]

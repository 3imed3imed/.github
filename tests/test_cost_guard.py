"""The hard cost rule (spec §2, §36) — the single most important invariant."""

from __future__ import annotations

import pytest

from app.providers.base import (
    CostClass,
    PaidServiceBlocked,
    Provider,
    ProviderChain,
    ProviderError,
)


class _Paid(Provider[str]):
    name = "paid-thing"
    kind = "test"
    cost_class = CostClass.PAID
    unit_cost_yen = 100.0

    def _run(self, *a, **k):
        return "charged"


class _FreeButBroken(Provider[str]):
    name = "free-broken"
    kind = "test"
    cost_class = CostClass.FREE

    def _run(self, *a, **k):
        raise ProviderError("boom")


class _FreeOK(Provider[str]):
    name = "free-ok"
    kind = "test"
    cost_class = CostClass.FREE

    def _run(self, *a, **k):
        return "free-result"


def test_paid_provider_blocked_by_default(settings):
    p = _Paid(settings)
    with pytest.raises(PaidServiceBlocked):
        p.call()
    assert p.actual_cost_yen() == 0.0


def test_paid_allowed_only_when_flag_set(monkeypatch):
    from app.config import reload_settings

    monkeypatch.setenv("ALLOW_PAID_SERVICES", "true")
    s = reload_settings()
    p = _Paid(s)
    assert p.call() == "charged"
    assert p.actual_cost_yen() == 100.0
    reload_settings()


def test_chain_never_falls_back_to_paid(settings):
    # Free provider broken; paid present but must be skipped, not charged.
    chain = ProviderChain([_FreeButBroken(settings), _Paid(settings)])
    with pytest.raises(ProviderError):
        chain.call()


def test_chain_prefers_free_and_recovers(settings):
    chain = ProviderChain([_FreeButBroken(settings), _FreeOK(settings)])
    outcome = chain.call()
    assert outcome.value == "free-result"
    assert outcome.provider == "free-ok"


def test_quota_exhaustion_raises(settings):
    class _Limited(Provider[str]):
        name = "limited"
        kind = "test"
        cost_class = CostClass.FREE_TIER
        quota = 1

        def _run(self, *a, **k):
            return "ok"

    p = _Limited(settings)
    assert p.call() == "ok"
    from app.providers.base import QuotaExhausted

    with pytest.raises(QuotaExhausted):
        p.call()

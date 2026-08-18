"""State machine, duplicate protection, and secret-safety (spec §30, §31, §38)."""

from __future__ import annotations

import logging

import pytest

from app.dedupe import PublishedLedger
from app.observability import RedactingFilter
from app.state import InvalidTransition, ProductionState, StateStore
from tests import fixtures_data as fx


def test_state_transitions_and_history(settings):
    store = StateStore(settings)
    store.create("s1")
    store.transition("s1", ProductionState.RESEARCHING)
    store.transition("s1", ProductionState.VERIFIED)
    rec = store.get("s1")
    assert rec["state"] == "verified"
    assert len(rec["history"]) >= 3
    assert all("at" in h for h in rec["history"])  # every transition timestamped


def test_illegal_transition_rejected(settings):
    store = StateStore(settings)
    store.create("s2")
    with pytest.raises(InvalidTransition):
        store.transition("s2", ProductionState.PUBLISHED)  # candidate -> published not allowed


def test_duplicate_protection(settings):
    ledger = PublishedLedger(settings)
    assert not ledger.is_duplicate(fx.SOLVED_COLD_CASE)
    ledger.add(fx.SOLVED_COLD_CASE, video_id="vid123")
    assert ledger.is_duplicate(fx.SOLVED_COLD_CASE)


def test_logs_redact_secrets():
    # The RedactingFilter must strip bearer tokens, Token headers and key= params.
    f = RedactingFilter()
    cases = [
        "Authorization: Bearer sk-secret-abcdef123456",
        "auth Token deadbeefcafetoken123456",
        "https://api.example.com/x?api_key=supersecretvalue&y=1",
    ]
    for msg in cases:
        rec = logging.LogRecord("n", logging.INFO, "", 0, msg, None, None)
        f.filter(rec)
        out = rec.getMessage()
        assert "REDACTED" in out
        for leak in ("sk-secret-abcdef123456", "deadbeefcafetoken123456", "supersecretvalue"):
            assert leak not in out

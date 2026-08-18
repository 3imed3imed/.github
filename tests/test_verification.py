"""Source verification + legal-status discipline (spec §8, §44)."""

from __future__ import annotations

from app.models import ClaimStatus, Source, SourceType
from app.research import Researcher
from app.verification import Verifier
from tests import fixtures_data as fx


def test_single_source_fails_verification(settings):
    v = Verifier(settings)
    result = v.verify_sources([Source(id="S01", url="https://x", publisher="x", source_type="news")])
    assert not result.ok
    assert "insufficient" in result.reason


def test_requires_official_source(settings):
    v = Verifier(settings)
    three_news = [
        Source(id=f"S0{i}", url=f"https://n{i}", publisher=f"News{i}", source_type=SourceType.NEWS.value)
        for i in range(1, 4)
    ]
    result = v.verify_sources(three_news)
    assert not result.ok
    assert "official" in result.reason


def test_three_sources_with_official_pass(settings):
    v = Verifier(settings)
    result = v.verify_sources(fx.CONFLICTING_SOURCES)
    assert result.ok
    assert result.has_official


def test_no_legal_status_escalation(settings):
    v = Verifier(settings)
    # "arrested" must never become guilty/convicted.
    assert v.classify_status("The suspect was arrested.") == ClaimStatus.CHARGED
    assert v.classify_status("The person was accused.") == ClaimStatus.ACCUSED
    # cap_status never exceeds what is supported.
    capped = v.cap_status(ClaimStatus.CONVICTED, ClaimStatus.CHARGED)
    assert capped == ClaimStatus.CHARGED


def test_bad_source_candidate_not_verified(settings):
    r = Researcher(settings)
    output, _ = r.build_fact_database(fx.BAD_SOURCE)
    # Only one source could be collected offline -> not verified.
    assert not output.verified


def test_every_claim_has_a_source(settings):
    r = Researcher(settings)
    output, store = r.build_fact_database(fx.SOLVED_COLD_CASE, seed_sources=fx.CONFLICTING_SOURCES)
    claims = store.read_json("claims.json")
    assert claims
    for c in claims:
        assert c["sources"], f"orphan claim {c['claim_id']}"

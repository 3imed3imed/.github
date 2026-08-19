"""Regression tests for the code-review findings (provider order, QC, dedupe, audio)."""

from __future__ import annotations

from app.config import reload_settings


def test_provider_chain_prefers_real_over_offline_fallback(monkeypatch):
    # Finding #1: configured real providers (FREE_TIER) must be tried before the
    # always-available offline fallback (FREE), not after.
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-fake")
    monkeypatch.setenv("PEXELS_API_KEY", "fake")
    monkeypatch.setenv("AGNES_API_KEY", "fake")
    s = reload_settings()
    from app.providers.llm import build_llm_chain
    from app.providers.stock import build_stock_chain
    from app.providers.video import build_video_chain

    llm = [p.name for p in build_llm_chain(s).providers]
    stock = [p.name for p in build_stock_chain(s).providers]
    video = [p.name for p in build_video_chain(s).providers]
    assert llm.index("openrouter") < llm.index("offline-llm")
    assert stock.index("pexels") < stock.index("generated")
    assert stock.index("pixabay") < stock.index("generated")
    assert video.index("agnes") < video.index("still-motion")
    reload_settings()


def test_paid_provider_sorted_last(settings):
    from app.providers.base import CostClass, Provider, ProviderChain

    class _Free(Provider[str]):
        name = "free"
        kind = "t"
        cost_class = CostClass.FREE

        def _run(self, *a, **k):
            return "f"

    class _Paid(Provider[str]):
        name = "paid"
        kind = "t"
        cost_class = CostClass.PAID

        def _run(self, *a, **k):
            return "p"

    # Paid supplied first, but must be reordered to the end.
    chain = ProviderChain([_Paid(settings), _Free(settings)])
    assert [p.name for p in chain.providers] == ["free", "paid"]


def test_qc_flags_claim_citing_unknown_source(settings):
    from app.models import Asset, Claim
    from app.qc import QCGate

    asset = Asset(asset_id="a1", provider="generated", license="own", scene_id=1)
    base = dict(
        title="A Case", description="d", script_text="clean", scenes=[], assets=[asset],
        originality_ok=True, verified=True,
    )
    gate = QCGate(settings)
    # Claim cites S99 which is not in the verified source set -> orphan.
    bad = [Claim(claim_id="C1", claim="x", status="CHARGED", sources=["S99"])]
    res = gate.run(claims=bad, sources_ids={"S01", "S02"}, **base)
    assert not res.passed
    assert "C1" in res.orphan_claims
    # Same claim citing a known source -> passes.
    good = [Claim(claim_id="C1", claim="x", status="CHARGED", sources=["S01"])]
    assert gate.run(claims=good, sources_ids={"S01", "S02"}, **base).passed


def test_qc_orphan_check_with_empty_source_set(settings):
    from app.models import Asset, Claim
    from app.qc import QCGate

    asset = Asset(asset_id="a1", provider="generated", license="own", scene_id=1)
    gate = QCGate(settings)
    claims = [Claim(claim_id="C1", claim="x", status="CHARGED", sources=["S99"])]
    base = dict(
        title="t", description="d", script_text="clean", scenes=[], assets=[asset],
        claims=claims, originality_ok=True, verified=True,
    )
    # Known-but-empty source set -> a claim citing phantom ids is an orphan.
    assert not gate.run(sources_ids=set(), **base).passed
    # Unknown source set (None) -> fall back to weak "has any id" check -> passes.
    assert gate.run(sources_ids=None, **base).passed


def test_qc_rejects_invalid_status(settings):
    from app.models import Asset, Claim
    from app.qc import QCGate

    asset = Asset(asset_id="a1", provider="generated", license="own", scene_id=1)
    gate = QCGate(settings)
    bad = [Claim(claim_id="C1", claim="x", status="TOTALLY_GUILTY", sources=["S01"])]
    res = gate.run(
        title="t", description="d", script_text="clean", scenes=[], assets=[asset],
        claims=bad, sources_ids={"S01"}, originality_ok=True, verified=True,
    )
    assert not res.passed


def test_dedupe_no_false_positive_on_empty_urls(settings):
    from app.dedupe import PublishedLedger
    from app.models import Candidate

    a = Candidate(id="a", headline="A completely distinct heist in Berlin", url="").ensure_id()
    b = Candidate(id="b", headline="An unrelated fraud case in Tokyo", url="").ensure_id()
    ledger = PublishedLedger(settings)
    ledger.add(a, video_id="v1")
    # b has an empty url too, but is a different story -> not a duplicate.
    assert not ledger.is_duplicate(b)


def test_audio_mix_with_asplit_bed(settings, tmp_path):
    from app.rendering import ffmpeg

    nar = tmp_path / "n.wav"
    bed = tmp_path / "b.wav"
    out = tmp_path / "m.wav"
    ffmpeg._run(["-f", "lavfi", "-i", "sine=frequency=220:duration=2:sample_rate=24000", "-ac", "1", "-ar", "24000", str(nar)])
    ffmpeg.generate_ambient_bed(bed, duration=2.0)
    ffmpeg.mix_audio_tracks(nar, out, bed=bed)
    assert out.exists() and (ffmpeg.probe_duration(out) or 0) > 0

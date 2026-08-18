"""Provider failure handling + secret scanning (spec §35, §37, §38)."""

from __future__ import annotations

from pathlib import Path

from app.providers.stock import build_stock_chain
from app.providers.tts import build_tts_chain
from app.providers.video import build_video_chain


def test_stock_chain_falls_back_to_generated(settings):
    # No Pexels/Pixabay keys -> chain must still succeed via generated provider.
    outcome = build_stock_chain(settings).call("anything", want_video=False)
    assert outcome.value[0].provider == "generated"
    assert outcome.value[0].license  # licence manifest always present


def test_video_chain_falls_back_to_still_motion(settings, tmp_path):
    outcome = build_video_chain(settings).call("prompt", tmp_path / "clip.mp4", duration=1.0)
    assert outcome.provider == "still-motion"
    assert not outcome.value.synthetic  # Ken Burns is not synthetic media


def test_tts_chain_produces_timed_audio(settings, tmp_path):
    out = tmp_path / "n.wav"
    outcome = build_tts_chain(settings).call("This is a short line of narration.", out)
    assert out.exists()
    assert outcome.value.duration > 0


def test_no_hardcoded_secrets_in_source():
    # Basic secret scan over the app package: no obvious key material committed.
    import re

    root = Path(__file__).resolve().parent.parent / "app"
    bad = re.compile(r"(sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,}|ghp_[A-Za-z0-9]{30,})")
    for p in root.rglob("*.py"):
        text = p.read_text()
        assert not bad.search(text), f"possible secret in {p}"

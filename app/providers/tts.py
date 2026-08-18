"""Text-to-speech providers.

Default is Edge TTS (free Microsoft neural voices, no API key). A silent-WAV
provider guarantees the render pipeline always produces timed audio even with no
network, so tests and offline runs still yield a real ``final.mp4``.
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

from app.config import Settings
from app.providers.base import CostClass, Provider, ProviderChain, ProviderError


class TTSResult:
    def __init__(self, path: Path, duration: float, provider: str):
        self.path = path
        self.duration = duration
        self.provider = provider


def _estimate_duration(text: str) -> float:
    # ~155 wpm documentary pace; floor of 1.2s per clause.
    words = max(1, len(text.split()))
    return max(1.2, words / 155.0 * 60.0)


class EdgeTTSProvider(Provider[TTSResult]):
    name = "edge-tts"
    kind = "tts"
    cost_class = CostClass.FREE

    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
        except Exception:
            return False
        return self.settings.tts_provider == "edge"

    def _run(self, text: str, out_path: Path, *, voice: str | None = None) -> TTSResult:
        import asyncio

        import edge_tts

        voice = voice or self.settings.tts_voice
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mp3_path = out_path.with_suffix(".mp3")

        async def _synthesize() -> None:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(mp3_path))

        asyncio.run(_synthesize())
        # Convert to WAV master via ffmpeg for a consistent downstream format.
        from app.rendering.ffmpeg import to_wav

        to_wav(mp3_path, out_path)
        from app.rendering.ffmpeg import probe_duration

        duration = probe_duration(out_path) or _estimate_duration(text)
        return TTSResult(path=out_path, duration=duration, provider=self.name)


class SilentTTSProvider(Provider[TTSResult]):
    """Generates a correctly timed silent WAV master.

    Not a real voice — a deterministic offline fallback so the pipeline always
    yields timed audio. The narration text still drives scene timing.
    """

    name = "silent-tts"
    kind = "tts"
    cost_class = CostClass.FREE

    def available(self) -> bool:
        return True

    def _run(self, text: str, out_path: Path, *, voice: str | None = None) -> TTSResult:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        duration = _estimate_duration(text)
        sample_rate = 24000
        n_frames = int(duration * sample_rate)
        with wave.open(str(out_path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            silence = struct.pack("<h", 0)
            wf.writeframes(silence * n_frames)
        return TTSResult(path=out_path, duration=duration, provider=self.name)


def build_tts_chain(settings: Settings, on_alert=None) -> ProviderChain[TTSResult]:
    return ProviderChain([EdgeTTSProvider(settings), SilentTTSProvider(settings)], on_alert=on_alert)


__all__ = ["TTSResult", "EdgeTTSProvider", "SilentTTSProvider", "build_tts_chain", "ProviderError"]

"""Text-to-speech providers.

Default is Edge TTS (free Microsoft neural voices, no API key). A silent-WAV
provider guarantees the render pipeline always produces timed audio even with no
network, so tests and offline runs still yield a real ``final.mp4``.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
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


class EspeakTTSProvider(Provider[TTSResult]):
    """Offline synthetic voice via the free, open-source ``espeak-ng`` binary.

    Not a neural voice — it is robotic — but it is a *real spoken* narration that
    works with no network and no API key, so an offline render is audible rather
    than silent. Sits below Edge (better quality when reachable) and above the
    silent fallback.
    """

    name = "espeak-tts"
    kind = "tts"
    cost_class = CostClass.FREE

    def _binary(self) -> str | None:
        return shutil.which("espeak-ng") or shutil.which("espeak")

    def available(self) -> bool:
        return self._binary() is not None

    def _run(self, text: str, out_path: Path, *, voice: str | None = None) -> TTSResult:
        binary = self._binary()
        if not binary:
            raise ProviderError("espeak-ng not installed")
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        wpm = max(80, min(260, self.settings.narration_wpm))
        raw = out_path.with_suffix(".espeak.wav")
        # Pass the (possibly long, punctuation-heavy) text via a file, never argv.
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
            tf.write(text)
            textfile = tf.name
        try:
            proc = subprocess.run(
                [binary, "-v", self.settings.espeak_voice, "-s", str(wpm), "-p", "40",
                 "-w", str(raw), "-f", textfile],
                capture_output=True, text=True,
            )
        finally:
            Path(textfile).unlink(missing_ok=True)
        if proc.returncode != 0 or not raw.exists():
            raise ProviderError(f"espeak failed: {(proc.stderr or '')[-200:]}")
        # Normalise to the 24k mono WAV the rest of the pipeline expects.
        from app.rendering.ffmpeg import probe_duration, to_wav

        to_wav(raw, out_path)
        raw.unlink(missing_ok=True)
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
    return ProviderChain(
        [EdgeTTSProvider(settings), EspeakTTSProvider(settings), SilentTTSProvider(settings)],
        on_alert=on_alert,
    )


__all__ = [
    "TTSResult", "EdgeTTSProvider", "EspeakTTSProvider", "SilentTTSProvider",
    "build_tts_chain", "ProviderError",
]

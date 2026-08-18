"""Audio stage (spec §17, §18).

Generate the narration WAV master via the TTS chain (Edge TTS free -> silent
fallback), then mix with an optional ducked music/ambience bed. Loudness
normalisation toward ~-14 LUFS happens at mux time in the renderer.
"""

from __future__ import annotations

from pathlib import Path

from app.config import Settings, get_settings
from app.models import Scene
from app.providers.tts import build_tts_chain
from app.rendering import ffmpeg
from app.storage import ProjectStore


class AudioResult:
    def __init__(self, master: Path, per_scene: dict[int, float], provider: str, total: float):
        self.master = master
        self.per_scene = per_scene
        self.provider = provider
        self.total = total


class AudioStage:
    def __init__(self, settings: Settings | None = None, on_alert=None):
        self.settings = settings or get_settings()
        self.tts = build_tts_chain(self.settings, on_alert=on_alert)

    def synthesize(self, store: ProjectStore, scenes: list[Scene]) -> AudioResult:
        audio_dir = store.path("audio")
        audio_dir.mkdir(parents=True, exist_ok=True)
        per_scene: dict[int, float] = {}
        provider = "silent-tts"

        # Per-scene narration clips (idempotent + accurate scene timing).
        scene_wavs: list[Path] = []
        for scene in scenes:
            wav = audio_dir / f"scene_{scene.scene_id:03d}.wav"
            if not wav.exists():
                outcome = self.tts.call(scene.narration or " ", wav, voice=self.settings.tts_voice)
                provider = outcome.provider
                dur = outcome.value.duration
            else:
                dur = ffmpeg.probe_duration(wav) or scene.duration
            per_scene[scene.scene_id] = dur
            scene.duration = round(max(scene.duration, dur), 2)
            scene_wavs.append(wav)

        # Concatenate into a narration master.
        narration_master = audio_dir / "narration.wav"
        if scene_wavs:
            concat_list = audio_dir / "concat.txt"
            # Re-encode-safe concat for WAV via ffmpeg.
            self._concat_wavs(scene_wavs, narration_master, concat_list)

        # Music/ambience bed: use a supplied bed.wav if present, otherwise
        # generate a subtle license-clean one (unless disabled). Idempotent.
        master = audio_dir / "master.wav"
        bed = audio_dir / "bed.wav"
        narration_len = ffmpeg.probe_duration(narration_master) or sum(per_scene.values())
        if not bed.exists() and self.settings.music_bed_enabled and narration_len > 0:
            try:
                ffmpeg.generate_ambient_bed(bed, duration=narration_len)
            except Exception:
                bed = audio_dir / "bed.wav"  # if generation fails, mix runs without it
        ffmpeg.mix_audio_tracks(narration_master, master, bed=bed if bed.exists() else None)
        total = ffmpeg.probe_duration(master) or sum(per_scene.values())
        return AudioResult(master=master, per_scene=per_scene, provider=provider, total=total)

    def _concat_wavs(self, wavs: list[Path], out: Path, concat_list: Path) -> None:
        lines = [f"file '{w.resolve()}'\n" for w in wavs]
        concat_list.write_text("".join(lines))
        ffmpeg._run(
            ["-f", "concat", "-safe", "0", "-i", str(concat_list), "-ac", "1", "-ar", "24000", str(out)]
        )

"""Resumable render pipeline (spec §20, §35).

Each scene renders to its own cached clip. A partial failure retries only the
failed scene — successful scenes are never re-rendered. The final step
concatenates scene clips and muxes the audio master with loudness
normalisation.
"""

from __future__ import annotations

from pathlib import Path

from app.config import Settings, get_settings
from app.models import Asset, Scene, VisualType
from app.observability import get_logger
from app.providers.video import build_video_chain
from app.rendering import ffmpeg
from app.storage import ProjectStore

log = get_logger("render")

_MAX_SCENE_RETRIES = 2


class RenderResult:
    def __init__(self, final_path: Path, scene_clips: list[Path], synthetic_used: bool):
        self.final_path = final_path
        self.scene_clips = scene_clips
        self.synthetic_used = synthetic_used


class Renderer:
    def __init__(self, settings: Settings | None = None, on_alert=None):
        self.settings = settings or get_settings()
        self.video = build_video_chain(self.settings, on_alert=on_alert)

    def render(
        self, store: ProjectStore, scenes: list[Scene], assets: list[Asset], audio_master: Path
    ) -> RenderResult:
        if not ffmpeg.ffmpeg_available():
            raise RuntimeError("ffmpeg not available — cannot render")
        scenes_dir = store.path("scenes")
        scenes_dir.mkdir(parents=True, exist_ok=True)
        asset_by_scene = {a.scene_id: a for a in assets}

        synthetic_used = False
        clips: list[Path] = []
        for scene in scenes:
            clip = scenes_dir / f"scene_{scene.scene_id:03d}.mp4"
            if clip.exists() and (ffmpeg.probe_duration(clip) or 0) > 0.1:
                log.info("scene %s cached, skipping", scene.scene_id)
                clips.append(clip)
                continue
            asset = asset_by_scene.get(scene.scene_id)
            used_synthetic = self._render_scene(scene, asset, clip)
            synthetic_used = synthetic_used or used_synthetic
            clips.append(clip)

        # Concatenate scene clips (re-encode to be safe across sources).
        silent_video = store.path("silent.mp4")
        self._concat(clips, silent_video, store)

        final_path = store.path("final.mp4")
        ffmpeg.mux_audio_video(silent_video, audio_master, final_path)
        return RenderResult(final_path=final_path, scene_clips=clips, synthetic_used=synthetic_used)

    def _render_scene(self, scene: Scene, asset: Asset | None, clip: Path) -> bool:
        image_path = asset.local_path if asset and asset.local_path else None
        want_ai = scene.visual_type == VisualType.AI_RECONSTRUCTION.value
        last_err: Exception | None = None
        for attempt in range(_MAX_SCENE_RETRIES + 1):
            try:
                if want_ai:
                    outcome = self.video.call(
                        scene.ai_prompt or scene.narration, clip, duration=scene.duration, image_path=image_path
                    )
                    return outcome.value.synthetic
                # Non-AI scene: Ken Burns over the still (owned or licensed).
                if image_path and Path(image_path).exists():
                    ffmpeg.ken_burns_clip(Path(image_path), clip, duration=scene.duration)
                else:
                    ffmpeg.solid_card_clip(clip, duration=scene.duration, label=scene.narration[:60])
                return False
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                log.warning("scene %s attempt %d failed: %s", scene.scene_id, attempt + 1, exc)
        # Last resort so the whole render never dies on one scene.
        ffmpeg.solid_card_clip(clip, duration=scene.duration, label=scene.narration[:60])
        log.error("scene %s fell back to text card after failures: %s", scene.scene_id, last_err)
        return False

    def _concat(self, clips: list[Path], out: Path, store: ProjectStore) -> None:
        # Re-encode each clip to a uniform format, then concat via demuxer.
        normalized: list[Path] = []
        norm_dir = store.path("scenes")
        for clip in clips:
            norm = norm_dir / (clip.stem + "_norm.mp4")
            if not norm.exists():
                ffmpeg._run(
                    [
                        "-i", str(clip),
                        "-vf", f"scale={ffmpeg.WIDTH}:{ffmpeg.HEIGHT}:force_original_aspect_ratio=decrease,"
                               f"pad={ffmpeg.WIDTH}:{ffmpeg.HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1",
                        "-r", str(ffmpeg.FPS),
                        "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-an",
                        str(norm),
                    ]
                )
            normalized.append(norm)
        concat_file = norm_dir / "concat.txt"
        ffmpeg.concat_clips(normalized, out, concat_file)

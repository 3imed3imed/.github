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


def _card_label(narration: str, *, limit: int = 200) -> str:
    """A text-card label: the opening of the narration, cut on a word boundary
    (the card wraps it) so nothing is truncated mid-word."""
    text = " ".join((narration or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


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

        # Decide up front whether we can crossfade: every scene must be
        # comfortably longer than the transition (the same feasibility test
        # xfade_concat applies). We commit to that decision before rendering so
        # the scene padding and the concat method never disagree.
        transition = self.settings.transition_seconds if self.settings.transitions_enabled else 0.0
        use_xfade = (
            transition > 0
            and len(scenes) >= 2
            and all(s.duration > transition + 0.2 for s in scenes)
        )
        # When crossfading, every scene but the last is rendered `transition`
        # seconds longer so the xfade overlap exactly cancels: the final video
        # length stays equal to the narration (no clipped ending) and each scene
        # still occupies its intended window, so captions/chapters — timed from
        # the uncompressed scene starts — stay accurate. Without xfade there is
        # no padding, so a hard-cut concat is exactly the narration length too.

        synthetic_used = False
        clips: list[Path] = []
        for idx, scene in enumerate(scenes):
            extra = transition if (use_xfade and idx < len(scenes) - 1) else 0.0
            clip = scenes_dir / f"scene_{scene.scene_id:03d}.mp4"
            want = scene.duration + extra
            cached = ffmpeg.probe_duration(clip) if clip.exists() else None
            # Reuse a cached clip only if it was rendered under the SAME padding
            # regime (its length matches what we want now), so toggling
            # transitions between runs can't leave a mismatched-length clip.
            if cached is not None and abs(cached - want) <= 0.3:
                log.info("scene %s cached, skipping", scene.scene_id)
                clips.append(clip)
                continue
            asset = asset_by_scene.get(scene.scene_id)
            used_synthetic = self._render_scene(scene, asset, clip, extra=extra)
            synthetic_used = synthetic_used or used_synthetic
            clips.append(clip)

        # Concatenate scene clips (re-encode to be safe across sources).
        silent_video = store.path("silent.mp4")
        self._concat(clips, silent_video, store, use_xfade=use_xfade)

        final_path = store.path("final.mp4")
        ffmpeg.mux_audio_video(
            silent_video,
            audio_master,
            final_path,
            target_lufs=self.settings.target_lufs,
            film_look=self.settings.film_look_enabled,
        )
        return RenderResult(final_path=final_path, scene_clips=clips, synthetic_used=synthetic_used)

    def _render_scene(self, scene: Scene, asset: Asset | None, clip: Path, *, extra: float = 0.0) -> bool:
        image_path = asset.local_path if asset and asset.local_path else None
        want_ai = scene.visual_type == VisualType.AI_RECONSTRUCTION.value
        duration = scene.duration + extra  # crossfade padding (see render())
        last_err: Exception | None = None
        for attempt in range(_MAX_SCENE_RETRIES + 1):
            try:
                if want_ai:
                    outcome = self.video.call(
                        scene.ai_prompt or scene.narration, clip, duration=duration, image_path=image_path
                    )
                    return outcome.value.synthetic
                # Non-AI scene: Ken Burns over the still (owned or licensed).
                if image_path and Path(image_path).exists():
                    # Alternate the motion direction by scene so it isn't monotonous.
                    ffmpeg.ken_burns_clip(
                        Path(image_path), clip, duration=duration, zoom_out=bool(scene.scene_id % 2)
                    )
                else:
                    ffmpeg.solid_card_clip(clip, duration=duration, label=_card_label(scene.narration))
                return False
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                log.warning("scene %s attempt %d failed: %s", scene.scene_id, attempt + 1, exc)
        # Last resort so the whole render never dies on one scene.
        ffmpeg.solid_card_clip(clip, duration=duration, label=_card_label(scene.narration))
        log.error("scene %s fell back to text card after failures: %s", scene.scene_id, last_err)
        return False

    def _concat(self, clips: list[Path], out: Path, store: ProjectStore, *, use_xfade: bool) -> None:
        # Re-encode each clip to a uniform format, then join. ``use_xfade`` was
        # decided up front (and the scenes padded to match), so we only crossfade
        # when the clips were rendered for it; otherwise a plain hard-cut concat
        # keeps the video exactly the narration length.
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

        if use_xfade and len(normalized) >= 2:
            try:
                ffmpeg.xfade_concat(normalized, out, transition=self.settings.transition_seconds)
                return
            except Exception as exc:  # noqa: BLE001
                # Scenes were padded for xfade; a hard-cut here would run long and
                # drift. This is unexpected (feasibility was checked up front), so
                # surface it rather than ship a desynced master.
                raise RuntimeError(f"crossfade concat failed after pre-check: {exc}") from exc
        concat_file = norm_dir / "concat.txt"
        ffmpeg.concat_clips(normalized, out, concat_file)

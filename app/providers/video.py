"""AI video providers.

Agnes AI is the primary (experimental) text-to-video / image-to-video adapter.
The entire system must keep working if Agnes disappears, so a
``StillMotionProvider`` implements the fallback approach from the spec: a
high-quality still with Ken Burns motion, produced entirely locally by FFmpeg.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.providers.base import CostClass, Provider, ProviderChain, ProviderError
from app.providers.http import client


@dataclass
class VideoClip:
    path: Path
    provider: str
    synthetic: bool  # True if it is an AI reconstruction (drives disclosure)


class AgnesProvider(Provider[VideoClip]):
    """Adapter for Agnes AI. Treated as FREE_TIER by default; if the owner's
    plan is paid they must set ``ALLOW_PAID_SERVICES=true`` and mark it PAID via
    ``AGNES_COST_CLASS``. Kept isolated behind this adapter so its
    unavailability never breaks the pipeline.
    """

    name = "agnes"
    kind = "video"
    cost_class = CostClass.FREE_TIER
    quota = 30

    def available(self) -> bool:
        return bool(self.settings.agnes_api_key)

    def _run(self, prompt: str, out_path: Path, *, duration: float = 8.0, image_path: str | None = None) -> VideoClip:
        if not self.settings.agnes_api_key:
            raise ProviderError("agnes: no API key")
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Bearer {self.settings.agnes_api_key}"}
        payload = {"prompt": prompt, "duration": duration}
        if image_path:
            payload["mode"] = "image-to-video"
        else:
            payload["mode"] = "text-to-video"
        with client(headers=headers, timeout=180.0) as c:
            # NOTE: Agnes's exact endpoint/response shape may evolve; kept behind
            # this adapter so a change is a one-file edit. We request a render,
            # then download the returned asset URL.
            resp = c.post(f"{self.settings.agnes_base_url}/video/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            asset_url = data.get("url") or data.get("output", {}).get("url")
            if not asset_url:
                raise ProviderError("agnes: no asset url in response")
            dl = c.get(asset_url)
            dl.raise_for_status()
            out_path.write_bytes(dl.content)
        return VideoClip(path=out_path, provider=self.name, synthetic=True)


class StillMotionProvider(Provider[VideoClip]):
    """Local Ken-Burns fallback. Not AI; not synthetic media."""

    name = "still-motion"
    kind = "video"
    cost_class = CostClass.FREE

    def available(self) -> bool:
        return True

    def _run(self, prompt: str, out_path: Path, *, duration: float = 8.0, image_path: str | None = None) -> VideoClip:
        from app.rendering.ffmpeg import ken_burns_clip, solid_card_clip

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if image_path and Path(image_path).exists():
            ken_burns_clip(Path(image_path), out_path, duration=duration)
        else:
            solid_card_clip(out_path, duration=duration, label=prompt[:60])
        return VideoClip(path=out_path, provider=self.name, synthetic=False)


def build_video_chain(settings: Settings, on_alert=None) -> ProviderChain[VideoClip]:
    return ProviderChain([AgnesProvider(settings), StillMotionProvider(settings)], on_alert=on_alert)

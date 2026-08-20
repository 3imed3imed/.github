"""Visuals stage (spec §14, §15, §16).

For each scene, obtain a license-clean asset:
* try the free stock chain (Pexels -> Pixabay) for STOCK_* scenes;
* otherwise generate an owned asset locally (text/map/timeline/document card);
* every asset gets a full licensing manifest entry.

Copyright safety beats a perfect visual match: if the stock chain yields nothing
usable we fall back to a generated card rather than risk an unlicensed download.
"""

from __future__ import annotations

from pathlib import Path

from app.config import Settings, get_settings
from app.models import Asset, Scene, VisualType
from app.observability import get_logger
from app.providers.http import client
from app.providers.stock import build_stock_chain
from app.storage import ProjectStore

log = get_logger("visuals")

_GENERATED_TYPES = {
    VisualType.TEXT_CARD.value,
    VisualType.MAP.value,
    VisualType.TIMELINE.value,
    VisualType.DOCUMENT.value,
    VisualType.DIAGRAM.value,
    VisualType.PUBLIC_RECORD.value,
}


class VisualsCollector:
    def __init__(self, settings: Settings | None = None, on_alert=None):
        self.settings = settings or get_settings()
        self.stock = build_stock_chain(self.settings, on_alert=on_alert)

    def collect(self, store: ProjectStore, scenes: list[Scene]) -> list[Asset]:
        assets_dir = store.path("assets")
        assets_dir.mkdir(parents=True, exist_ok=True)
        manifest: list[Asset] = []
        for scene in scenes:
            asset = self._for_scene(store, scene)
            manifest.append(asset)
        store.write_json("media.json", [a.model_dump() for a in manifest])
        return manifest

    def _for_scene(self, store: ProjectStore, scene: Scene) -> Asset:
        target = store.path("assets") / f"scene_{scene.scene_id:03d}.png"
        # Idempotent: skip if the still already exists (resume support).
        if target.exists():
            existing = store.read_json("media.json") or []
            for a in existing:
                if a.get("scene_id") == scene.scene_id:
                    return Asset(**a)

        if scene.visual_type in _GENERATED_TYPES:
            return self._generate_card(store, scene, target)

        # Try the free stock chain for image scenes.
        try:
            outcome = self.stock.call(scene.visual_query, want_video=False, per_page=3)
            hits = outcome.value
            hit = hits[0]
            if hit.provider != "generated" and hit.download_url:
                self._download(hit.download_url, target)
                return Asset(
                    asset_id=f"a_{scene.scene_id:03d}",
                    provider=hit.provider,
                    source_url=hit.source_url,
                    license=hit.license,
                    creator=hit.creator,
                    attribution_required=hit.attribution_required,
                    local_path=str(target),
                    scene_id=scene.scene_id,
                    kind="image",
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("stock fetch failed for scene %s: %s", scene.scene_id, exc)

        # Copyright-safe fallback: generate our own card.
        return self._generate_card(store, scene, target)

    def _download(self, url: str, target: Path) -> None:
        with client(timeout=60.0) as c:
            resp = c.get(url)
            resp.raise_for_status()
            target.write_bytes(resp.content)
        # Normalise to PNG if needed.
        try:
            from PIL import Image

            img = Image.open(target).convert("RGB")
            img.thumbnail((1920, 1080))
            img.save(target, "PNG")
        except Exception:
            pass

    def _generate_card(self, store: ProjectStore, scene: Scene, target: Path) -> Asset:
        label_map = {
            VisualType.TEXT_CARD.value: scene.narration[:120],
            VisualType.MAP.value: f"[ MAP ]\n{scene.visual_query}",
            VisualType.TIMELINE.value: f"[ TIMELINE ]\n{scene.visual_query}",
            VisualType.DOCUMENT.value: f"[ RECORD ]\n{scene.visual_query}",
            VisualType.DIAGRAM.value: f"[ DIAGRAM ]\n{scene.visual_query}",
            VisualType.PUBLIC_RECORD.value: f"[ PUBLIC RECORD ]\n{scene.visual_query}",
        }
        label = label_map.get(scene.visual_type, scene.narration[:120])
        _render_card(target, label)
        return Asset(
            asset_id=f"a_{scene.scene_id:03d}",
            provider="generated",
            source_url="local://generated",
            license="Own generated media (channel-owned)",
            creator="Crime YouTube Factory",
            attribution_required=False,
            local_path=str(target),
            scene_id=scene.scene_id,
            kind="generated",
        )


def _render_card(target: Path, label: str) -> None:
    """Render a dark documentary card: vertical gradient, an optional kicker
    chip (``[ MAP ]`` etc.), and centred wrapped body text over an accent rule.

    A real TrueType face is used when one is installed. Everything important
    sits inside a safe area so the Ken Burns zoom never crops it, and the text is
    horizontally centred so a long line is never pushed off-screen.
    """
    try:
        import textwrap

        from PIL import Image, ImageDraw

        from app.imaging import load_font

        W, H = 1920, 1080
        bg, accent, fg = (18, 20, 26), (200, 60, 60), (232, 232, 236)

        # Separate an optional "[ KICKER ]" prefix from the body text.
        kicker = ""
        body = label.strip()
        if body.startswith("[") and "]" in body:
            head, _, rest = body.partition("]")
            kicker = head.lstrip("[").strip()
            body = rest.strip()

        img = Image.new("RGB", (W, H), bg)
        draw = ImageDraw.Draw(img)
        floor = tuple(max(0, int(c * 0.5)) for c in bg)
        for y in range(H):
            t = y / H
            draw.line([(0, y), (W, y)], fill=tuple(int(bg[i] * (1 - t) + floor[i] * t) for i in range(3)))

        body_font = load_font(58, "regular")
        kfont = load_font(34, "bold")

        # Wrap and vertically centre the body within the safe area.
        lines = textwrap.wrap(body, width=30)[:6] or [" "]
        heights = []
        for ln in lines:
            box = draw.textbbox((0, 0), ln, font=body_font)
            heights.append(box[3] - box[1])
        line_gap = 20
        block_h = sum(heights) + line_gap * (len(lines) - 1)
        y = (H - block_h) // 2
        if kicker:
            kw = int(draw.textlength(kicker, font=kfont))
            kx = (W - kw) // 2  # centred above the body block
            draw.rectangle([kx - 16, y - 96, kx + kw + 16, y - 40], fill=accent)
            draw.text((kx, y - 90), kicker, font=kfont, fill=bg)
        for ln, h in zip(lines, heights, strict=True):
            w = draw.textlength(ln, font=body_font)
            x = (W - w) / 2
            draw.text((x + 3, y + 3), ln, font=body_font, fill=(0, 0, 0))  # shadow
            draw.text((x, y), ln, font=body_font, fill=fg)
            y += h + line_gap

        draw.rectangle([(W - 360) // 2, y + 24, (W + 360) // 2, y + 30], fill=accent)
        img.save(target, "PNG")
    except Exception:
        # Absolute fallback: a tiny valid PNG so rendering can proceed.
        from app.imaging import placeholder_png

        placeholder_png(target)

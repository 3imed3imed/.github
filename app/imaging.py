"""Small shared imaging helpers used by the visuals and thumbnail stages."""

from __future__ import annotations

from pathlib import Path

# A 1x1 opaque PNG. Absolute last-resort so the render pipeline always has a
# valid image file even if Pillow is unavailable or a draw call fails.
_PLACEHOLDER_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080200000090"
    "7753de0000000c49444154789c6360000002000100ffff03000006000557"
    "bfabd40000000049454e44ae426082"
)


def placeholder_png(path: Path) -> None:
    """Write the minimal valid PNG to ``path``."""
    Path(path).write_bytes(_PLACEHOLDER_PNG)


# Common install locations for the free Liberation / DejaVu families. We ship no
# font ourselves (licence hygiene) but use a system TrueType face when present so
# thumbnails and text cards render with real weight instead of Pillow's tiny
# bitmap default. Ordered best-first (bold sans for headlines).
_FONT_CANDIDATES = {
    "bold": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
    "regular": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    ],
}


def find_font_file(weight: str = "bold") -> str | None:
    """Absolute path to a system TrueType font of the given weight, or None."""
    for candidate in _FONT_CANDIDATES.get(weight, []):
        if Path(candidate).exists():
            return candidate
    return None


def load_font(size: int, weight: str = "bold"):
    """A Pillow font at ``size`` — a real TrueType face if one is installed,
    otherwise Pillow's (small) default so callers still get a usable object."""
    from PIL import ImageFont

    path = find_font_file(weight)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

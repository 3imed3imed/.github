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

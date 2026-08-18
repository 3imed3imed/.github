"""Caption generation (spec §19): SRT, ASS, WebVTT from scene timing.

Documentary-style, clean, high-contrast — not oversized TikTok captions in the
normal 16:9 output.
"""

from __future__ import annotations

from app.models import Scene


def _ts(seconds: float, *, vtt: bool = False) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    sep = "." if vtt else ","
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(scenes: list[Scene]) -> str:
    out = []
    for i, sc in enumerate(scenes, start=1):
        start = _ts(sc.start)
        end = _ts(sc.start + sc.duration)
        out.append(f"{i}\n{start} --> {end}\n{sc.narration.strip()}\n")
    return "\n".join(out)


def to_vtt(scenes: list[Scene]) -> str:
    out = ["WEBVTT", ""]
    for sc in scenes:
        start = _ts(sc.start, vtt=True)
        end = _ts(sc.start + sc.duration, vtt=True)
        out.append(f"{start} --> {end}\n{sc.narration.strip()}\n")
    return "\n".join(out)


_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Documentary, Arial, 46, &H00FFFFFF, &H00000000, &H64000000, 0, 2, 1, 2, 120, 120, 80

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ass_ts(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def to_ass(scenes: list[Scene]) -> str:
    lines = [_ASS_HEADER]
    for sc in scenes:
        start = _ass_ts(sc.start)
        end = _ass_ts(sc.start + sc.duration)
        text = sc.narration.strip().replace("\n", " \\N ")
        lines.append(f"Dialogue: 0,{start},{end},Documentary,,0,0,0,,{text}")
    return "\n".join(lines)

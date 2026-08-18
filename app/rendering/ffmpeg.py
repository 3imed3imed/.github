"""FFmpeg command helpers.

All rendering goes through FFmpeg (free, open-source). These helpers keep the
command strings in one place, standardise the output format (1920x1080, H.264,
AAC, 30fps) and make each unit of work a single deterministic subprocess call so
scenes can be cached and retried individually.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

WIDTH = 1920
HEIGHT = 1080
FPS = 30

_FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
_FFPROBE = shutil.which("ffprobe") or "ffprobe"


class FFmpegError(RuntimeError):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _run(args: list[str]) -> None:
    proc = subprocess.run(
        [_FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr.strip()[-800:] or "ffmpeg failed")


def probe_duration(path: Path) -> float | None:
    if shutil.which("ffprobe") is None:
        return None
    proc = subprocess.run(
        [_FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        return float(json.loads(proc.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return None


def to_wav(src: Path, dst: Path, sample_rate: int = 24000) -> None:
    _run(["-i", str(src), "-ac", "1", "-ar", str(sample_rate), str(dst)])


def solid_card_clip(out_path: Path, *, duration: float, label: str = "", color: str = "0x14161a") -> None:
    """A dark text card — used for TEXT_CARD scenes and as the universal fallback
    when no licensed still is available. Purely generated, license-clean."""
    safe = _escape_drawtext(label)
    vf = (
        f"drawtext=text='{safe}':fontcolor=white:fontsize=44:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=12"
    )
    _run(
        [
            "-f", "lavfi", "-i", f"color=c={color}:s={WIDTH}x{HEIGHT}:d={duration:.2f}:r={FPS}",
            "-vf", vf,
            "-t", f"{duration:.2f}",
            "-pix_fmt", "yuv420p",
            str(out_path),
        ]
    )


def ken_burns_clip(image_path: Path, out_path: Path, *, duration: float) -> None:
    """Slow zoom/pan over a still image (the AI-free motion fallback)."""
    frames = max(1, int(duration * FPS))
    vf = (
        f"scale={WIDTH*2}:-1,"
        f"zoompan=z='min(zoom+0.0008,1.25)':d={frames}:"
        f"s={WIDTH}x{HEIGHT}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':fps={FPS},"
        f"format=yuv420p"
    )
    _run(
        [
            "-loop", "1", "-i", str(image_path),
            "-vf", vf,
            "-t", f"{duration:.2f}",
            "-r", str(FPS),
            str(out_path),
        ]
    )


def concat_clips(clip_paths: list[Path], out_path: Path, concat_file: Path) -> None:
    lines = [f"file '{p.resolve()}'\n" for p in clip_paths]
    concat_file.write_text("".join(lines))
    _run(
        [
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c", "copy",
            str(out_path),
        ]
    )


def mux_audio_video(video_path: Path, audio_path: Path, out_path: Path, *, target_lufs: float = -14.0) -> None:
    """Combine the silent video track with the narration+music master, applying
    loudness normalisation toward the target integrated LUFS."""
    _run(
        [
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex", f"[1:a]loudnorm=I={target_lufs}:TP=-1.5:LRA=11[a]",
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(out_path),
        ]
    )


def generate_ambient_bed(out_path: Path, *, duration: float, sample_rate: int = 24000) -> None:
    """Procedurally generate a subtle, license-clean ambient music bed.

    We synthesise it ourselves (two very low, quiet sine drones plus heavily
    low-passed noise), so it is copyright-clean and carries no sensational sound
    (no screaming, gunshots or stingers — spec §18). It is quiet by design and is
    further ducked under narration at mix time.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    d = max(1.0, duration)
    # Two soft detuned drones + gently filtered noise, summed and kept low.
    filter_complex = (
        f"sine=frequency=110:sample_rate={sample_rate}:duration={d:.2f}[a];"
        f"sine=frequency=146.83:sample_rate={sample_rate}:duration={d:.2f}[b];"
        f"anoisesrc=color=brown:sample_rate={sample_rate}:duration={d:.2f}:amplitude=0.2[n];"
        "[a]volume=0.12[a2];[b]volume=0.09[b2];"
        "[n]lowpass=f=500,volume=0.10[n2];"
        "[a2][b2][n2]amix=inputs=3:normalize=0,"
        "tremolo=f=0.1:d=0.3,"
        "afade=t=in:st=0:d=2,"
        f"afade=t=out:st={max(0.0, d - 2):.2f}:d=2,"
        "volume=0.5[out]"
    )
    _run(
        [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-ac", "1", "-ar", str(sample_rate),
            "-t", f"{d:.2f}",
            str(out_path),
        ]
    )


def encode_final(video_path: Path, out_path: Path) -> None:
    _run(
        [
            "-i", str(video_path),
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-s", f"{WIDTH}x{HEIGHT}",
            "-c:a", "aac", "-b:a", "192k",
            str(out_path),
        ]
    )


def mix_audio_tracks(narration: Path, out_path: Path, *, bed: Path | None = None) -> None:
    """Mix narration with an optional ducked music/ambience bed.

    Music is automatically ducked under narration via sidechaincompress so the
    voice is always intelligible.
    """
    if bed and bed.exists():
        _run(
            [
                "-i", str(narration), "-i", str(bed),
                "-filter_complex",
                "[1:a]volume=0.25[bed];"
                "[bed][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=250[ducked];"
                "[0:a][ducked]amix=inputs=2:duration=first:dropout_transition=2[out]",
                "-map", "[out]",
                str(out_path),
            ]
        )
    else:
        _run(["-i", str(narration), "-c", "copy", str(out_path)])


def _escape_drawtext(text: str) -> str:
    text = text.replace("\\", "").replace(":", "\\:").replace("'", "")
    text = text.replace("%", "\\%")
    return text[:120]

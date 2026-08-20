"""Cleanup of intermediate render files (spec §20 — do not accumulate).

Removes per-scene clips, normalized clips, silent intermediates and audio chunks
for projects that already produced a ``final.mp4``, keeping deliverables
(final.mp4, thumbnail.jpg, captions, metadata, sources, run_report).
"""

from __future__ import annotations

import sys

from app.config import Settings, get_settings
from app.observability import get_logger

log = get_logger("cleanup")

_KEEP = {
    "final.mp4", "thumbnail.jpg", "captions.srt", "captions.ass", "captions.vtt",
    "metadata.json", "sources.json", "facts.json", "people.json", "timeline.json",
    "claims.json", "run_report.json", "qc_report.json", "script.txt", "script.json",
    "storyboard.json", "media.json", "titles.json", "thumbnails.json", "description.txt",
    "upload.json",
}


def cleanup(settings: Settings | None = None, *, keep_assets: bool = True) -> int:
    settings = settings or get_settings()
    freed = 0
    if not settings.projects_dir.exists():
        return 0
    for proj in settings.projects_dir.iterdir():
        if not proj.is_dir():
            continue
        if not (proj / "final.mp4").exists():
            continue  # only clean finished productions
        for sub in ("scenes", "audio"):
            d = proj / sub
            if d.exists():
                for f in d.iterdir():
                    freed += f.stat().st_size
                    f.unlink()
                d.rmdir()
        for stray in ("silent.mp4",):
            p = proj / stray
            if p.exists():
                freed += p.stat().st_size
                p.unlink()
        if not keep_assets:
            adir = proj / "assets"
            if adir.exists():
                for f in adir.iterdir():
                    freed += f.stat().st_size
                    f.unlink()
    log.info("cleanup freed ~%.1f MB", freed / 1e6)
    print(f"Freed ~{freed/1e6:.1f} MB of intermediate files.")
    return 0


def main(argv: list[str] | None = None) -> int:
    return cleanup()


if __name__ == "__main__":
    sys.exit(main())

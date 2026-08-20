"""Description generator (spec §23, §24).

Produces a 2-line hook, an episode summary, a source note, an AI-reconstruction
disclosure when applicable, chapter markers, credits/attribution and a small set
of relevant hashtags — no keyword spam.
"""

from __future__ import annotations

from app.models import Asset, Fact, Scene, Source

AI_DISCLOSURE = (
    "Some scenes use stylised AI-assisted reconstruction to illustrate events. "
    "These are clearly non-authentic and are not real crime-scene footage."
)


def build_description(
    *,
    title: str,
    summary: str,
    scenes: list[Scene],
    sources: list[Source],
    assets: list[Asset],
    facts: list[Fact],
    synthetic_media_used: bool,
) -> str:
    hook_lines = [
        title if title.rstrip().endswith((".", "?", "!")) else f"{title}.",
        "A documented, source-checked account of a real case — no speculation beyond the record.",
    ]
    parts = ["\n".join(hook_lines), "", summary.strip()[:600], ""]

    # Chapters from scene start times (coarse, every ~5 scenes).
    parts.append("Chapters:")
    marks = _chapter_marks(scenes)
    parts.extend(marks)
    parts.append("")

    # Source note.
    parts.append("Sources:")
    for s in sources[:8]:
        label = s.title or s.publisher or "source"
        if s.url:
            parts.append(f"- {label}: {s.url}")
        else:
            parts.append(f"- {label}")
    parts.append("")

    if synthetic_media_used:
        parts.append("AI disclosure: " + AI_DISCLOSURE)
        parts.append("")

    # Attribution for any asset that requires it.
    attributions = [f"- {a.creator} via {a.provider}" for a in assets if a.attribution_required and a.creator]
    if attributions:
        parts.append("Media credits:")
        parts.extend(sorted(set(attributions)))
        parts.append("")

    parts.append("Credits: Written, narrated and edited by an automated documentary pipeline with human oversight.")
    parts.append("")
    parts.append(_hashtags())
    return "\n".join(parts).strip()


def _chapter_marks(scenes: list[Scene]) -> list[str]:
    marks = ["00:00 Introduction"]
    labels = [
        "The setting", "What happened", "The investigation", "Obstacles",
        "The breakthrough", "The outcome", "What solved it", "Aftermath",
    ]
    if not scenes:
        return marks
    step = max(1, len(scenes) // len(labels))
    li = 0
    for i in range(step, len(scenes), step):
        if li >= len(labels):
            break
        t = scenes[i].start
        marks.append(f"{_fmt(t)} {labels[li]}")
        li += 1
    return marks


def _fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _hashtags() -> str:
    return "#truecrime #coldcase #documentary #casefiles #investigation"

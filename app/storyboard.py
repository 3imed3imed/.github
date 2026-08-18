"""Storyboard engine (spec §12, §13).

Splits narration into 20-45 visual beats, assigns a visual type and query, and
applies visual-safety rules: people who were never convicted are never depicted
realistically committing a crime, and AI reconstructions are never presented as
authentic footage.
"""

from __future__ import annotations

import re

from app.config import Settings, get_settings
from app.models import Person, Scene, VisualType

# Rotation used to keep the visual mix varied and documentary-like.
_VISUAL_ROTATION = [
    VisualType.STOCK_IMAGE,
    VisualType.LOCATION,
    VisualType.MAP,
    VisualType.STOCK_VIDEO,
    VisualType.DOCUMENT,
    VisualType.TIMELINE,
    VisualType.TEXT_CARD,
    VisualType.DIAGRAM,
]

_SAFE_ALTERNATIVES = "location reconstruction, silhouette, generic hands, vehicle, building, map, timeline, object"


class StoryboardEngine:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def build(self, narration: str, *, people: list[Person], per_scene_words: int = 32) -> list[Scene]:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narration) if s.strip()]
        # Group sentences into beats of ~per_scene_words words.
        beats: list[str] = []
        buf: list[str] = []
        count = 0
        for sent in sentences:
            buf.append(sent)
            count += len(sent.split())
            if count >= per_scene_words:
                beats.append(" ".join(buf))
                buf, count = [], 0
        if buf:
            beats.append(" ".join(buf))

        # Clamp to the 20-45 beat range.
        beats = self._reshape(beats, lo=20, hi=45)

        unconvicted = {p.name for p in people if not p.convicted}
        scenes: list[Scene] = []
        t = 0.0
        for i, beat in enumerate(beats):
            duration = max(5.0, min(12.0, len(beat.split()) / 155.0 * 60.0))
            vtype = _VISUAL_ROTATION[i % len(_VISUAL_ROTATION)]
            scene = Scene(
                scene_id=i + 1,
                start=round(t, 2),
                duration=round(duration, 2),
                narration=beat,
                visual_type=vtype.value,
                visual_query=self._query(beat, vtype),
                ai_prompt="",
                source_requirement="approved facts only" if vtype in {VisualType.DOCUMENT, VisualType.PUBLIC_RECORD} else "",
                transition="crossfade" if i % 2 == 0 else "fade",
            )
            self._apply_visual_safety(scene, beat, unconvicted)
            scenes.append(scene)
            t += duration
        return scenes

    def _reshape(self, beats: list[str], *, lo: int, hi: int) -> list[str]:
        if len(beats) > hi:
            # Merge neighbours until within range.
            while len(beats) > hi:
                beats[-2] = beats[-2] + " " + beats[-1]
                beats.pop()
        while len(beats) < lo and beats:
            # Split the longest beat.
            longest = max(range(len(beats)), key=lambda k: len(beats[k].split()))
            words = beats[longest].split()
            if len(words) < 8:
                break
            mid = len(words) // 2
            beats[longest : longest + 1] = [" ".join(words[:mid]), " ".join(words[mid:])]
        return beats

    def _query(self, beat: str, vtype: VisualType) -> str:
        keywords = [w for w in re.findall(r"[a-zA-Z]{4,}", beat)][:4]
        base = " ".join(keywords).lower() or "documentary"
        hints = {
            VisualType.MAP: "map location aerial",
            VisualType.LOCATION: "establishing location exterior",
            VisualType.DOCUMENT: "official document paper",
            VisualType.TIMELINE: "timeline graphic",
            VisualType.STOCK_VIDEO: "cinematic b-roll",
            VisualType.DIAGRAM: "diagram infographic",
            VisualType.TEXT_CARD: "",
        }
        return f"{base} {hints.get(vtype, '')}".strip()

    def _apply_visual_safety(self, scene: Scene, beat: str, unconvicted: set[str]) -> None:
        mentions_unconvicted = any(name.lower() in beat.lower() for name in unconvicted)
        depicts_crime = re.search(r"\b(kill|stab|shoot|attack|assault|rob|murder)\b", beat, re.I)
        if mentions_unconvicted and depicts_crime:
            # Never a realistic depiction of an unconvicted person committing a crime.
            scene.visual_type = VisualType.LOCATION.value
            scene.visual_query = "neutral location reconstruction, no identifiable person"
            scene.ai_prompt = ""
            scene.source_requirement = (
                f"VISUAL SAFETY: use non-identifiable alternatives ({_SAFE_ALTERNATIVES}); "
                "no realistic depiction of an unconvicted person committing a crime"
            )
        elif scene.visual_type == VisualType.AI_RECONSTRUCTION.value:
            scene.ai_prompt = (
                "Stylised, clearly non-photographic reconstruction. Must NOT look like authentic "
                "crime-scene footage. " + beat[:120]
            )

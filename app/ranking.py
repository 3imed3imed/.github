"""Story ranker — scores each candidate out of 100 (spec §7).

The rubric is deterministic and explainable so every selection has a stored,
auditable reason. A hosted LLM can refine sub-scores when configured, but the
deterministic scorer is the default and the test oracle.
"""

from __future__ import annotations

import json
import re

from app.config import Settings, get_settings
from app.models import Candidate, RankedStory, ScoreBreakdown, SourceType
from app.niche import NicheFilter, NicheVerdict

_SOLVED = re.compile(r"\b(solved|convicted|sentenced|guilty|identified|captured|arrested and convicted)\b", re.I)
_TWIST = re.compile(r"\b(twist|unexpected|shocking|turned out|actually|secret|hidden)\b", re.I)
_MYSTERY = re.compile(r"\b(mystery|unsolved for|cold case|vanished|disappeared|unknown|puzzle)\b", re.I)
_INVEST = re.compile(r"\b(dna|forensic|investigat|detective|genealogy|evidence|breakthrough)\b", re.I)
_ENDING = re.compile(r"\b(finally|decades later|years later|closure|resolved|verdict)\b", re.I)
_VISUAL = re.compile(r"\b(heist|escape|robbery|chase|bank|museum|vault|border|map|location)\b", re.I)

# Coarse story categories used to connect analytics performance back to
# selection. Keep this vocabulary aligned with the `category` field written in
# performance data so the feedback loop matches.
_CATEGORY_PATTERNS = [
    ("cold_case", re.compile(r"\bcold case\b|\bunsolved\b|\bdecades? later\b|\byears later\b", re.I)),
    ("heist", re.compile(r"\bheist\b|\brobbery\b|\bburglary\b|\bmuseum\b|\bvault\b", re.I)),
    ("fraud", re.compile(r"\bfraud\b|\bscam\b|\bponzi\b|\bembezzl", re.I)),
    ("fugitive", re.compile(r"\bfugitive\b|\bmanhunt\b|\bescape\b|\bcaptured\b", re.I)),
    ("missing_person", re.compile(r"\bmissing\b|\bvanished\b|\bdisappear", re.I)),
    ("homicide", re.compile(r"\bmurder\b|\bhomicide\b|\bkilling\b", re.I)),
]

#: Advisory bias is deliberately small — analytics only nudges soft selection,
#: it never overrides the rubric, thresholds, niche policy or safety rules.
_ADVISORY_MAX_POINTS = 3


def category_for(candidate: Candidate) -> str:
    text = f"{candidate.crime_type} {candidate.headline} {candidate.summary}"
    for name, pat in _CATEGORY_PATTERNS:
        if pat.search(text):
            return name
    return "other"


class StoryRanker:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.niche = NicheFilter()
        self._advisory = self._load_advisory_weights()

    def _load_advisory_weights(self) -> dict[str, float]:
        """Load per-category advisory weights produced by weekly analytics.

        Returns an empty dict when none exist. These bias *soft* selection only.
        """
        path = self.settings.data_dir / "selection_weights.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
        weights: dict[str, float] = {}
        for rec in data.get("recommendations", []):
            if rec.get("dimension") == "category":
                try:
                    weights[str(rec["signal"])] = float(rec["weight_delta"])
                except (KeyError, TypeError, ValueError):
                    continue
        return weights

    def rank(self, candidate: Candidate) -> RankedStory:
        verdict = self.niche.evaluate(candidate)
        if not verdict.allowed:
            # Safety rejection is absolute — advisory weights can never revive it.
            return RankedStory(
                candidate=candidate,
                score=0,
                rejected=True,
                rejection_reason=verdict.reason,
                explanation=verdict.reason,
            )
        breakdown = self._score(candidate, verdict)
        base = min(100, max(0, breakdown.total() + verdict.priority_bonus))
        bias = self._advisory_bias(candidate)
        total = min(100, max(0, base + bias))
        story = RankedStory(
            candidate=candidate,
            score=total,
            breakdown=breakdown,
            explanation=self._explain(candidate, breakdown, verdict, total, bias=bias),
        )
        return story

    def _advisory_bias(self, candidate: Candidate) -> int:
        if not self._advisory:
            return 0
        delta = self._advisory.get(category_for(candidate), 0.0)
        # weight_delta is a small fraction; scale to a bounded point bias.
        points = round(delta * 10)
        return max(-_ADVISORY_MAX_POINTS, min(_ADVISORY_MAX_POINTS, points))

    def rank_all(self, candidates: list[Candidate]) -> list[RankedStory]:
        ranked = [self.rank(c) for c in candidates]
        ranked.sort(key=lambda r: (not r.rejected, r.score), reverse=True)
        return ranked

    def _score(self, c: Candidate, verdict: NicheVerdict) -> ScoreBreakdown:
        text = f"{c.headline} {c.summary}"
        b = ScoreBreakdown()

        # Solved / legally established outcome (20)
        if c.case_status in {"convicted", "solved", "closed"} or _SOLVED.search(text):
            b.solved_outcome = 20
        elif c.source_type == SourceType.COURT.value:
            b.solved_outcome = 16
        else:
            b.solved_outcome = 6

        # Mystery / curiosity (15)
        b.mystery = 15 if _MYSTERY.search(text) else 7

        # Unexpected twist (15)
        b.twist = 15 if _TWIST.search(text) else 6

        # Clear narrative ending (10)
        b.clear_ending = 10 if _ENDING.search(text) else 4

        # Interesting investigation (10)
        b.investigation = 10 if _INVEST.search(text) else 5

        # Reliable source quality (10)
        if c.source_type in {SourceType.OFFICIAL.value, SourceType.COURT.value}:
            b.source_quality = 10
        elif c.source_type == SourceType.NEWS.value:
            b.source_quality = 6
        else:
            b.source_quality = 4

        # Visual potential (8)
        b.visual_potential = 8 if _VISUAL.search(text) else 4

        # Evergreen potential (5): older / cold cases age well
        b.evergreen = 5 if _MYSTERY.search(text) or "cold case" in text.lower() else 3

        # Advertiser safety (5): no deprioritise flags => full marks
        b.advertiser_safety = 5 if verdict.priority_bonus >= 0 else 2

        # Originality (2): default modest; dedupe handles true duplicates
        b.originality = 2
        return b

    def _explain(self, c: Candidate, b: ScoreBreakdown, v: NicheVerdict, total: int, *, bias: int = 0) -> str:
        parts = [
            f"Total {total}/100 (rubric {b.total()} + niche bonus {v.priority_bonus}"
            + (f" + analytics bias {bias:+d}" if bias else "")
            + ").",
            f"Solved/outcome {b.solved_outcome}/20, mystery {b.mystery}/15, twist {b.twist}/15,"
            f" ending {b.clear_ending}/10, investigation {b.investigation}/10,"
            f" source {b.source_quality}/10, visual {b.visual_potential}/8,"
            f" evergreen {b.evergreen}/5, adv-safe {b.advertiser_safety}/5, original {b.originality}/2.",
        ]
        if bias:
            parts.append(
                f"Analytics advisory ({category_for(c)}): {bias:+d} pts (soft nudge only; "
                "safety/fact rules unchanged)."
            )
        if v.matched:
            parts.append("Niche signals: " + ", ".join(v.matched))
        thr = self.settings.scoring
        if total >= thr.preferred_story_score:
            parts.append("Above PREFERRED threshold — strong candidate.")
        elif total >= thr.min_story_score:
            parts.append("Meets production threshold.")
        else:
            parts.append(f"Below MIN_STORY_SCORE={thr.min_story_score} — not produced.")
        return " ".join(parts)

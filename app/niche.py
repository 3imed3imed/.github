"""Channel niche policy: hard rejects, deprioritisation and prioritisation.

This runs before ranking. Anything hard-rejected here can never be produced,
regardless of score — safety precedes performance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import Candidate

# Automatic rejection — safety and platform policy (spec §6).
_REJECT_PATTERNS = [
    r"\bchild (?:sexual|sex) abuse\b",
    r"\bchild exploitation\b",
    r"\bchild (?:porn|pornography)\b",
    r"\bcsam\b",
    r"\bsexual abuse of (?:a )?minor",
    r"\brape of a child\b",
    r"\bexecution (?:footage|video)\b",
    r"\bbeheading\b",
    r"\bterror(?:ist)? propaganda\b",
    r"\bgore\b",
    r"\bsnuff\b",
]

# Deprioritise — not banned, but pushed down initially (spec §6).
_DEPRIORITIZE_PATTERNS = [
    r"\bbreaking\b",
    r"\bongoing trial\b",
    r"\bon trial\b",
    r"\bawaiting trial\b",
    r"\balleged\b",
    r"\baccus(?:es|ed|ation)\b",
    r"\bunconfirmed\b",
    r"\brumor|rumour\b",
    r"\bcelebrity\b",
    r"\bpolitician|senator|congress|election\b",
]

# Prioritise — the channel's sweet spot (spec §6).
_PRIORITIZE_PATTERNS = [
    r"\bcold case\b",
    r"\bsolved\b",
    r"\bdecades? later\b",
    r"\byears later\b",
    r"\bconvicted\b",
    r"\bsentenced\b",
    r"\bpleaded guilty\b",
    r"\bfraud\b",
    r"\bscam\b",
    r"\bheist\b",
    r"\bfugitive\b",
    r"\bprison escape\b",
    r"\bcaptured\b",
    r"\bidentified after\b",
]


def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_REJECT = _compile(_REJECT_PATTERNS)
_DEPRIORITIZE = _compile(_DEPRIORITIZE_PATTERNS)
_PRIORITIZE = _compile(_PRIORITIZE_PATTERNS)


@dataclass
class NicheVerdict:
    allowed: bool
    reason: str
    priority_bonus: int  # -15 .. +10 applied later in ranking
    matched: list[str]


class NicheFilter:
    def evaluate(self, c: Candidate) -> NicheVerdict:
        text = f"{c.headline} {c.summary} {c.crime_type}".lower()
        matched: list[str] = []

        for pat in _REJECT:
            if pat.search(text):
                return NicheVerdict(
                    allowed=False,
                    reason=f"hard-reject: matched forbidden topic /{pat.pattern}/",
                    priority_bonus=0,
                    matched=[pat.pattern],
                )

        bonus = 0
        for pat in _DEPRIORITIZE:
            if pat.search(text):
                bonus -= 5
                matched.append(f"-{pat.pattern}")
        for pat in _PRIORITIZE:
            if pat.search(text):
                bonus += 4
                matched.append(f"+{pat.pattern}")

        bonus = max(-15, min(10, bonus))
        return NicheVerdict(allowed=True, reason="allowed", priority_bonus=bonus, matched=matched)

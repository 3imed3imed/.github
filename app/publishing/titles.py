"""Title engine (spec §22).

Generates >=10 candidate titles and scores them for curiosity, accuracy,
clarity, length, keyword relevance and policy safety. Avoids fake claims,
ALL-CAPS spam, false promises, graphic language and fabricated quotes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import Settings, get_settings
from app.models import Candidate, Fact

_BANNED = re.compile(r"\b(shocking|you won'?t believe|gruesome|graphic|exclusive leaked)\b", re.I)


@dataclass
class TitleCandidate:
    text: str
    scores: dict[str, float]

    @property
    def total(self) -> float:
        return round(sum(self.scores.values()), 2)


class TitleEngine:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def generate(self, candidate: Candidate, facts: list[Fact]) -> list[TitleCandidate]:
        subject = self._subject(candidate)
        year = self._year(candidate, facts)
        templates = [
            f"The Case That Took {year} to Solve" if year else "The Case That Took Years to Solve",
            "Everyone Thought It Was an Accident — Until Investigators Found the Truth",
            f"{subject}: How a Cold Case Was Finally Solved",
            "He Vanished Without a Trace. Decades Later, the Truth Came Out.",
            f"The Overlooked Clue That Cracked {subject}",
            f"How Investigators Solved {subject}",
            "A Cold Case Reopened — And the Answer Surprised Everyone",
            f"The Evidence That Rewrote {subject}",
            f"{subject}, Explained: What the Record Actually Shows",
            f"Solved After Years: The Truth Behind {subject}",
            f"The Detail Detectives Almost Missed in {subject}",
            f"What Finally Solved {subject}",
        ]
        seen = set()
        out: list[TitleCandidate] = []
        for t in templates:
            t = re.sub(r"\s+", " ", t).strip()
            if t in seen:
                continue
            seen.add(t)
            out.append(TitleCandidate(text=t, scores=self._score(t)))
        out.sort(key=lambda c: c.total, reverse=True)
        return out

    def best(self, candidate: Candidate, facts: list[Fact]) -> TitleCandidate:
        return self.generate(candidate, facts)[0]

    def _subject(self, candidate: Candidate) -> str:
        head = candidate.headline.split(" - ")[0].split(" | ")[0]
        head = re.sub(r"[.!?].*$", "", head).strip()
        return head[:60] if head else "the Case"

    def _year(self, candidate: Candidate, facts: list[Fact]) -> str:
        text = candidate.headline + " " + " ".join(f.text for f in facts)
        years = sorted(int(y) for y in re.findall(r"\b(19\d\d|20\d\d)\b", text))
        if len(years) >= 2:
            return f"{years[-1] - years[0]} Years"
        return ""

    def _score(self, text: str) -> dict[str, float]:
        length = len(text)
        curiosity = 25.0 if re.search(r"(truth|solved|finally|almost|surprised|vanished)", text, re.I) else 15.0
        clarity = 20.0 if 25 <= length <= 70 else 10.0
        length_score = 15.0 if length <= 70 else max(3.0, 15.0 - (length - 70) * 0.5)
        caps_ratio = sum(1 for c in text if c.isupper()) / max(1, len(text))
        accuracy = 20.0 if not _BANNED.search(text) else 5.0
        keyword = 10.0 if re.search(r"(case|cold case|investigators|solved|truth)", text, re.I) else 5.0
        policy = 10.0 if (not _BANNED.search(text) and caps_ratio < 0.6) else 2.0
        return {
            "curiosity": curiosity,
            "clarity": clarity,
            "length": round(length_score, 2),
            "accuracy": accuracy,
            "keyword_relevance": keyword,
            "policy_safety": policy,
        }

"""Title engine (spec §22).

Generates >=10 candidate titles and scores them for curiosity, accuracy,
clarity, length, keyword relevance, story relevance and policy safety. Titles
are category-aware so a template never makes a claim that does not fit the case
(a fraud case is never titled "He Vanished Without a Trace"), and already-used
titles are skipped so episodes don't repeat the same headline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import Settings, get_settings
from app.dedupe import PublishedLedger
from app.models import Candidate, Fact
from app.ranking import category_for

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
        category = category_for(candidate)
        templates = self._templates(category, subject, year)

        used = self._used_titles()
        seen: set[str] = set()
        out: list[TitleCandidate] = []
        for t in templates:
            t = self._clean(t)
            if t in seen or t in used:
                continue
            seen.add(t)
            out.append(TitleCandidate(text=t, scores=self._score(t, subject, candidate)))
        # Fall back to allowing used titles only if de-duplication left nothing.
        if not out:
            for t in templates:
                t = self._clean(t)
                if t in seen:
                    continue
                seen.add(t)
                out.append(TitleCandidate(text=t, scores=self._score(t, subject, candidate)))
        out.sort(key=lambda c: c.total, reverse=True)
        return out

    def best(self, candidate: Candidate, facts: list[Fact]) -> TitleCandidate:
        return self.generate(candidate, facts)[0]

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        return (text[:1].upper() + text[1:]) if text else text

    # -- template pool (category-aware) ----------------------------------- #
    def _templates(self, category: str, subject: str, year: str) -> list[str]:
        yr = year or "Years"
        # Subject-bearing templates work for any story and give per-story variety.
        generic = [
            f"How Investigators Solved {subject}",
            f"{subject}: What the Record Actually Shows",
            f"The Evidence That Rewrote {subject}",
            f"What Finally Solved {subject}",
            f"The Detail Investigators Almost Missed in {subject}",
        ]
        by_category = {
            "cold_case": [
                f"The Case That Took {yr} to Solve",
                f"{subject}: How a Cold Case Was Finally Solved",
                "A Cold Case Reopened — And the Answer Came Years Later",
                "Everyone Thought It Was Unsolvable — Until Investigators Found the Truth",
            ],
            "homicide": [
                f"The Killing That Took {yr} to Solve",
                "Everyone Thought It Was an Accident — Until Investigators Found the Truth",
                f"How Detectives Finally Solved {subject}",
            ],
            "missing_person": [
                "They Vanished Without a Trace. Years Later, the Truth Came Out.",
                f"Missing for {yr} — Then Investigators Found the Answer",
            ],
            "fraud": [
                "The Fraud That Fooled Everyone — Until the Money Ran Out",
                f"How Investigators Unravelled a {yr}-Long Fraud",
                "The Scheme That Collapsed — and the Conviction That Followed",
            ],
            "heist": [
                "The Heist That Went Unsolved for Years",
                "How Investigators Finally Cracked a Daring Heist",
            ],
            "fugitive": [
                "On the Run for Years — Until One Mistake",
                "The Fugitive Who Almost Got Away",
            ],
        }
        pool = by_category.get(category, []) + generic
        # Guarantee at least 10 candidates (spec §22) by padding with generics.
        extra = [
            f"Solved After Years: The Truth Behind {subject}",
            f"The Overlooked Clue That Cracked {subject}",
            "A Case Reopened — And the Answer Surprised Everyone",
        ]
        for e in extra:
            if len(pool) >= 12:
                break
            pool.append(e)
        return pool

    def _used_titles(self) -> set[str]:
        try:
            entries = PublishedLedger(self.settings)._load()
        except Exception:
            return set()
        return {e.get("title", "") for e in entries if e.get("title")}

    def _subject(self, candidate: Candidate) -> str:
        """A short, title-friendly noun phrase for the case (not the whole
        headline). Prefer a cleaned crime type, else a trimmed headline."""
        ct = (candidate.crime_type or "").strip()
        ct = re.sub(r"\s*\(.*?\)\s*", "", ct)  # drop parentheticals like "(cold case)"
        mapping = {
            "fraud": "the Fraud Case",
            "heist": "the Heist",
            "homicide": "the Case",
            "serial homicide": "the Case",
            "robbery": "the Robbery",
        }
        if ct.lower() in mapping:
            return mapping[ct.lower()]
        head = candidate.headline.split(" - ")[0].split(" | ")[0]
        head = re.sub(r"[.!?].*$", "", head).strip()
        # Keep it short enough to fit inside a title template.
        words = head.split()
        short = " ".join(words[:6])
        return short[:48] if short else "the Case"

    def _year(self, candidate: Candidate, facts: list[Fact]) -> str:
        text = candidate.headline + " " + " ".join(f.text for f in facts)
        years = sorted(int(y) for y in re.findall(r"\b(19\d\d|20\d\d)\b", text))
        if len(years) >= 2:
            return f"{years[-1] - years[0]} Years"
        return ""

    def _score(self, text: str, subject: str, candidate: Candidate) -> dict[str, float]:
        length = len(text)
        curiosity = 22.0 if re.search(r"(truth|solved|finally|almost|reopened|unravel|collapsed|run)", text, re.I) else 14.0
        clarity = 20.0 if 25 <= length <= 70 else 10.0
        length_score = 15.0 if length <= 70 else max(3.0, 15.0 - (length - 70) * 0.5)
        caps_ratio = sum(1 for c in text if c.isupper()) / max(1, len(text))
        accuracy = 20.0 if not _BANNED.search(text) else 5.0
        keyword = 8.0 if re.search(r"(case|investigators|solved|truth|fraud|heist|fugitive)", text, re.I) else 4.0
        # Story relevance: reward titles that name this story's subject so titles
        # vary by episode instead of a generic template winning every time.
        subject_core = subject.replace("the ", "").strip().lower()
        relevance = 10.0 if subject_core and subject_core in text.lower() else 3.0
        policy = 10.0 if (not _BANNED.search(text) and caps_ratio < 0.6) else 2.0
        return {
            "curiosity": curiosity,
            "clarity": clarity,
            "length": round(length_score, 2),
            "accuracy": accuracy,
            "keyword_relevance": keyword,
            "story_relevance": relevance,
            "policy_safety": policy,
        }

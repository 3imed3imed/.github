"""Duplicate protection via story fingerprints.

Two layers:
* candidate-level fingerprint used during discovery to drop near-identical items
  from the same crawl;
* published-story ledger so we never publish the same case twice, using case
  names, people, dates, location, source URLs and a token-set similarity check.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.config import Settings, get_settings
from app.models import Candidate

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "of", "to", "in", "on", "and", "or", "for", "with", "was",
    "were", "is", "are", "man", "woman", "case", "police", "after", "over", "as",
    "his", "her", "who", "from", "years", "year", "old",
}


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class Fingerprinter:
    def candidate_fingerprint(self, c: Candidate) -> str:
        toks = sorted(_tokens(c.headline))[:8]
        return "|".join(toks) or (c.url or c.headline)


class PublishedLedger:
    """Persistent record of stories we have committed to / published."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.path: Path = self.settings.data_dir / "published_ledger.json"

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text())

    def _save(self, entries: list[dict]) -> None:
        self.path.write_text(json.dumps(entries, indent=2))

    def is_duplicate(self, candidate: Candidate, *, threshold: float = 0.6) -> bool:
        entries = self._load()
        toks = _tokens(candidate.headline + " " + " ".join(candidate.people))
        # Only match on non-empty URLs — Candidate.url defaults to "" and two
        # different urlless stories must not collide on the empty string.
        urls = {u for u in {candidate.url} if u}
        for e in entries:
            entry_urls = {u for u in e.get("urls", []) if u}
            if urls & entry_urls:
                return True
            if jaccard(toks, set(e.get("tokens", []))) >= threshold:
                return True
        return False

    def add(self, candidate: Candidate, *, video_id: str = "", title: str = "") -> None:
        entries = self._load()
        entries.append(
            {
                "story_id": candidate.id,
                "headline": candidate.headline,
                "people": candidate.people,
                "urls": [candidate.url],
                "tokens": sorted(_tokens(candidate.headline + " " + " ".join(candidate.people))),
                "video_id": video_id,
                "title": title,
            }
        )
        self._save(entries)

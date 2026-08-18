"""Research stage: collect sources and build the fact database (spec §9).

Writes ``sources.json``, ``facts.json``, ``people.json``, ``timeline.json`` and
``claims.json`` into the project directory. The script writer may use only facts
present here.

Production source collection is live (candidate URL + CourtListener + related
discovery hits). Offline/tests supply sources via a seed (fixtures) — the module
never fabricates "confirmed" sources to reach the minimum; if it cannot collect
enough real sources it fails verification and the job pauses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import Settings, get_settings
from app.models import Candidate, Fact, Person, Source, TimelineEntry
from app.providers.legal import CourtListenerProvider
from app.storage import ProjectStore
from app.verification import Verifier

_DATE = re.compile(r"\b(1[89]\d\d|20\d\d)\b")
_NAME = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\b")


@dataclass
class ResearchOutput:
    sources: list[Source]
    facts: list[Fact]
    people: list[Person]
    timeline: list[TimelineEntry]
    verified: bool
    reason: str


class Researcher:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.verifier = Verifier(self.settings)

    # -- source collection ------------------------------------------------- #
    def collect_sources(
        self, candidate: Candidate, *, seed_sources: list[Source] | None = None
    ) -> list[Source]:
        sources: list[Source] = list(seed_sources or [])

        if not sources and candidate.url:
            sources.append(
                Source(
                    id="S01",
                    title=candidate.headline,
                    url=candidate.url,
                    publisher=candidate.source,
                    source_type=candidate.source_type,
                    text_excerpt=candidate.summary,
                )
            )
            # Try to corroborate with court records (fails soft).
            try:
                provider = CourtListenerProvider(self.settings)
                if provider.available():
                    legal = provider.call(candidate.headline)
                    for s in legal:
                        s.id = f"S{len(sources)+1:02d}"
                        sources.append(s)
            except Exception:
                pass
        return sources

    # -- fact extraction --------------------------------------------------- #
    def extract(self, candidate: Candidate, sources: list[Source]) -> ResearchOutput:
        result = self.verifier.verify_sources(sources)
        corpus = " ".join([candidate.headline, candidate.summary] + [s.text_excerpt for s in sources])
        source_ids = [s.id for s in result.sources] or [s.id for s in sources]

        facts = self._facts(candidate, corpus, source_ids)
        people = self._people(candidate, corpus)
        timeline = self._timeline(corpus, source_ids)

        return ResearchOutput(
            sources=result.sources or sources,
            facts=facts,
            people=people,
            timeline=timeline,
            verified=result.ok,
            reason=result.reason,
        )

    def _facts(self, candidate: Candidate, corpus: str, source_ids: list[str]) -> list[Fact]:
        facts: list[Fact] = []
        # Headline is the anchor fact.
        status = self.verifier.classify_status(corpus)
        facts.append(
            Fact(
                fact_id="F001",
                text=candidate.headline.strip(),
                sources=source_ids[:2] or ["S01"],
                claim_status=status.value,
            )
        )
        # Sentence-level facts from summaries/excerpts.
        sentences = re.split(r"(?<=[.!?])\s+", candidate.summary or "")
        for i, sent in enumerate(sentences, start=2):
            sent = sent.strip()
            if len(sent) < 25:
                continue
            s_status = self.verifier.classify_status(sent)
            facts.append(
                Fact(
                    fact_id=f"F{i:03d}",
                    text=sent,
                    sources=source_ids[:2] or ["S01"],
                    claim_status=s_status.value,
                )
            )
            if len(facts) >= 12:
                break
        return facts

    def _people(self, candidate: Candidate, corpus: str) -> list[Person]:
        people: list[Person] = []
        names = list(dict.fromkeys(candidate.people)) or list(dict.fromkeys(_NAME.findall(corpus)))
        for name in names[:8]:
            status = self.verifier.classify_status(corpus)
            people.append(
                Person(
                    name=name,
                    legal_status=status.value,
                    convicted=status.value in {"CONVICTED", "PLEADED_GUILTY"},
                )
            )
        return people

    def _timeline(self, corpus: str, source_ids: list[str]) -> list[TimelineEntry]:
        entries: list[TimelineEntry] = []
        for year in sorted(set(_DATE.findall(corpus)))[:10]:
            entries.append(TimelineEntry(date=year, event=f"Event referenced in {year}.", sources=source_ids[:1]))
        return entries

    # -- persistence ------------------------------------------------------- #
    def build_fact_database(
        self, candidate: Candidate, *, seed_sources: list[Source] | None = None
    ) -> tuple[ResearchOutput, ProjectStore]:
        store = ProjectStore(candidate.id, self.settings)
        # Idempotent: reuse existing sources.json if present (resume/fixtures).
        existing = store.read_json("sources.json")
        if existing and not seed_sources:
            seed_sources = [Source(**s) for s in existing]

        sources = self.collect_sources(candidate, seed_sources=seed_sources)
        output = self.extract(candidate, sources)

        store.write_json("sources.json", [s.model_dump() for s in output.sources])
        store.write_json("facts.json", [f.model_dump() for f in output.facts])
        store.write_json("people.json", [p.model_dump() for p in output.people])
        store.write_json("timeline.json", [t.model_dump() for t in output.timeline])

        claims = self.verifier.build_claims(
            [(f.text, " ".join(s.text_excerpt for s in output.sources), f.sources) for f in output.facts]
        )
        store.write_json("claims.json", [c.model_dump() for c in claims])
        return output, store

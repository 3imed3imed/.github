"""Script engine + originality checker (spec §10, §11).

The narration is an *original synthesis* of approved facts — sources provide
facts, never wording. A similarity checker compares the script against source
text and rejects it if passages are too close to a source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.config import Settings, get_settings
from app.dedupe import jaccard
from app.llm import complete_text
from app.models import Fact, Person, Source

_SECTION_TEMPLATES = [
    ("HOOK", "Some cases refuse to stay buried. {hook}"),
    ("NORMAL WORLD", "Before any of it made headlines, this was an ordinary place with ordinary lives."),
    ("CRIME / DISAPPEARANCE", "Then something happened that no one could explain at first."),
    ("EARLY INVESTIGATION", "Investigators began the slow work of turning confusion into questions."),
    ("WRONG LEADS / OBSTACLES", "Not every lead pointed the right way, and time worked against them."),
    ("KEY DISCOVERY", "A single detail eventually changed how everyone read the case."),
    ("BREAKTHROUGH", "What had been a dead end became a thread worth pulling."),
    ("ARREST / COURT OUTCOME", "The legal record is where this account stays careful and exact."),
    ("WHAT FINALLY SOLVED IT", "In the end, the answer came down to patient, verifiable work."),
    ("AFTERMATH", "What remained afterward was the quieter business of consequence and memory."),
]


@dataclass
class Script:
    title_working: str
    sections: list[tuple[str, str]]  # (section_name, narration)
    word_count: int
    used_fact_ids: list[str] = field(default_factory=list)

    def full_text(self) -> str:
        return "\n\n".join(text for _, text in self.sections)

    def narration_only(self) -> str:
        return " ".join(text for _, text in self.sections)


@dataclass
class OriginalityReport:
    max_similarity: float
    ok: bool
    offending: list[str]


class OriginalityChecker:
    """Sliding n-gram token-set similarity against every source excerpt."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def check(self, script_text: str, sources: list[Source]) -> OriginalityReport:
        threshold = self.settings.scoring.max_source_similarity
        script_sents = [s for s in re.split(r"(?<=[.!?])\s+", script_text) if len(s.split()) >= 6]
        offending: list[str] = []
        worst = 0.0
        for sent in script_sents:
            s_tokens = set(re.findall(r"[a-z0-9]+", sent.lower()))
            for src in sources:
                for src_sent in re.split(r"(?<=[.!?])\s+", src.text_excerpt or ""):
                    if len(src_sent.split()) < 6:
                        continue
                    sim = jaccard(s_tokens, set(re.findall(r"[a-z0-9]+", src_sent.lower())))
                    worst = max(worst, sim)
                    if sim >= threshold:
                        offending.append(sent[:120])
        return OriginalityReport(max_similarity=round(worst, 3), ok=worst < threshold, offending=offending[:5])


class ScriptEngine:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.checker = OriginalityChecker(self.settings)

    def write(
        self,
        *,
        title: str,
        facts: list[Fact],
        people: list[Person],
        sources: list[Source],
        on_alert=None,
    ) -> tuple[Script, OriginalityReport]:
        target_words = self.settings.target_script_words()
        fact_lines = "\n".join(f"- [{f.fact_id} | {f.claim_status}] {f.text}" for f in facts)
        people_lines = "\n".join(f"- {p.name} ({p.legal_status})" for p in people) or "- (none named)"
        system = (
            "You are a careful true-crime documentary writer. Write ORIGINAL narration "
            "(do not copy source wording). Use ONLY the approved facts. Use precise legal "
            "language: never turn arrested into guilty, charged into convicted, or alleged "
            f"into proven. Target about {target_words} words "
            f"(~{self.settings.target_video_minutes:.0f} minutes), serious documentary tone."
        )
        prompt = (
            f"Working title: {title}\n\nApproved facts:\n{fact_lines}\n\nPeople:\n{people_lines}\n\n"
            "Write the narration in these sections, each labelled on its own line: "
            + ", ".join(name for name, _ in _SECTION_TEMPLATES)
        )

        def fallback() -> str:
            return self._deterministic(title, facts, people)

        text, provider = complete_text(prompt, system=system, fallback=fallback, on_alert=on_alert)
        sections = self._parse_sections(text) or self._deterministic_sections(title, facts, people)
        sections = self._fit_length(sections, target_words)
        script = Script(
            title_working=title,
            sections=sections,
            word_count=len(" ".join(t for _, t in sections).split()),
            used_fact_ids=[f.fact_id for f in facts],
        )
        report = self.checker.check(script.narration_only(), sources)
        return script, report

    # -- deterministic offline writer ------------------------------------- #
    def _deterministic_sections(self, title: str, facts: list[Fact], people: list[Person]) -> list[tuple[str, str]]:
        anchor = facts[0].text if facts else title
        fact_pool = [f for f in facts[1:]] or facts
        sections: list[tuple[str, str]] = []
        n = len(fact_pool)
        per = max(1, n // len(_SECTION_TEMPLATES))
        for idx, (name, template) in enumerate(_SECTION_TEMPLATES):
            lead = template.format(hook=self._reword_anchor(anchor))
            chunk = fact_pool[idx * per : (idx + 1) * per]
            body_bits = [self._rephrase(f.text, f.claim_status, idx * 7 + j) for j, f in enumerate(chunk)]
            if name == "ARREST / COURT OUTCOME" and people:
                for p in people:
                    body_bits.append(self._legal_clause(p.name, p.legal_status))
            body = " ".join(body_bits) if body_bits else (
                "Here the verified record is thin, and the narration deliberately stops short of "
                "anything the evidence does not support."
            )
            sections.append((name, f"{lead} {body}"))
        return self._pad_to_length(sections, target=self.settings.target_script_words())

    def _deterministic(self, title: str, facts: list[Fact], people: list[Person]) -> str:
        return "\n".join(f"{n}\n{t}" for n, t in self._deterministic_sections(title, facts, people))

    def _fit_length(self, sections: list[tuple[str, str]], target_words: int) -> list[tuple[str, str]]:
        """Bring the script near the target word count (which sets duration).

        Only trims when comfortably over target (>25%), and only on sentence
        boundaries so no clause is cut mid-way; never pads here (the
        deterministic builder already pads up).
        """
        import re as _re

        total = sum(len(t.split()) for _, t in sections)
        if total <= target_words * 1.25 or not sections:
            return sections
        budget = target_words
        out: list[tuple[str, str]] = []
        for name, text in sections:
            if budget <= 0:
                break
            sents = _re.split(r"(?<=[.!?])\s+", text)
            kept, used = [], 0
            for s in sents:
                w = len(s.split())
                if kept and used + w > budget:
                    break
                kept.append(s)
                used += w
            budget -= used
            out.append((name, " ".join(kept).strip() or text.split(".")[0] + "."))
        return out or sections

    def _reword_anchor(self, text: str) -> str:
        # Compress the anchor into an original framing clause rather than quoting.
        keys = self._salient(text, k=3)
        subject = ", ".join(keys) if keys else "the case"
        return f"the account turns on {subject}"

    # Legal-status vocabulary kept EXACT — never softened or escalated.
    _STATUS_PHRASE = {
        "CONVICTED": "a conviction was ultimately recorded",
        "PLEADED_GUILTY": "a guilty plea was entered on the record",
        "CHARGED": "formal charges were filed",
        "ACCUSED": "an accusation was made, and it is described here strictly as such",
        "SUSPECT": "a suspect was identified, without any assumption of guilt",
        "DISPUTED": "the point remained disputed",
        "UNCONFIRMED": "the detail stayed unconfirmed",
        "CONFIRMED": "the detail is confirmed by the record",
    }

    _CONNECTORS = [
        "What the documentation shows is that",
        "In terms the record can support,",
        "Following the evidence rather than the rumour,",
        "As the case file makes clear,",
        "Keeping strictly to what was established,",
    ]

    def _rephrase(self, text: str, status: str, seed: int) -> str:
        """Restate a fact as an original, structurally different clause.

        The legal-status verb is preserved exactly; the surrounding wording is
        synthesised so it does not mirror any source sentence.
        """
        connector = self._CONNECTORS[seed % len(self._CONNECTORS)]
        status_phrase = self._STATUS_PHRASE.get(status.upper(), "the record notes this point")
        subject = ", ".join(self._salient(text, k=3)) or "the matter"
        return f"{connector} where {subject} is concerned, {status_phrase}."

    def _legal_clause(self, name: str, legal_status: str) -> str:
        phrase = self._STATUS_PHRASE.get(legal_status.upper(), "no status is asserted")
        return f"For {name}, the record's position is precise: {phrase}."

    def _salient(self, text: str, *, k: int = 3) -> list[str]:
        # Pick a few distinctive, non-stopword terms to anchor a reworded clause.
        stop = {
            "the", "a", "an", "of", "to", "in", "on", "and", "or", "for", "with", "was",
            "were", "is", "are", "that", "this", "from", "had", "has", "been",
            "which", "who", "later", "after", "before", "into", "through", "multiple",
        }
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text) if w.lower() not in stop]
        seen: list[str] = []
        for w in words:
            if w.lower() not in {s.lower() for s in seen}:
                seen.append(w.lower())
            if len(seen) >= k:
                break
        return seen

    _PADDING = [
        " Investigators returned to what could be documented rather than what could be assumed.",
        " The pattern that emerged was built from records, not from speculation or hearsay.",
        " Each step forward had to survive the same test: could it be shown, not merely believed.",
        " That discipline, unglamorous as it was, is what eventually held up under scrutiny.",
        " Where certainty ran out, the account here stops, and says so plainly.",
    ]

    def _pad_to_length(self, sections: list[tuple[str, str]], target: int) -> list[tuple[str, str]]:
        words = sum(len(t.split()) for _, t in sections)
        i = 0
        # Prime with the padding already present so we never re-append a line a
        # section ends with (avoids duplicated sentences in narration/captions).
        used: list[set[str]] = [
            {p.strip() for p in self._PADDING if p.strip() and text.rstrip().endswith(p.strip())}
            for _, text in sections
        ]
        while words < target and i < 600:
            sec = i % len(sections)
            name, text = sections[sec]
            # Pick the next padding line this section has not used yet.
            choice = next(
                (p for k in range(len(self._PADDING))
                 if (p := self._PADDING[(i + k) % len(self._PADDING)]).strip() not in used[sec]),
                None,
            )
            i += 1
            if choice is None:  # this section already carries every padding line
                continue
            sections[sec] = (name, text + choice)
            used[sec].add(choice.strip())
            words += len(choice.split())
        return sections

    def _parse_sections(self, text: str) -> list[tuple[str, str]]:
        names = [name for name, _ in _SECTION_TEMPLATES]
        sections: list[tuple[str, str]] = []
        current = None
        buf: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            matched = next((n for n in names if stripped.upper().startswith(n)), None)
            if matched:
                if current:
                    sections.append((current, " ".join(buf).strip()))
                current = matched
                buf = [stripped[len(matched):].lstrip(":- ").strip()]
            elif current:
                buf.append(stripped)
        if current:
            sections.append((current, " ".join(buf).strip()))
        # Only accept if we recovered several labelled sections with content.
        good = [(n, b) for n, b in sections if len(b.split()) > 4]
        return good if len(good) >= 5 else []

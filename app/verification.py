"""Source verification and claim construction (spec §8).

Rules enforced here:
* A production needs at least ``MIN_SOURCES`` independently useful sources.
* At least one should be a court/official/government source.
* Every fact becomes a claim with a legal status from a fixed vocabulary.
* Legal status is never escalated (arrested !-> guilty, charged !-> convicted).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import Settings, get_settings
from app.models import Claim, ClaimStatus, Source, SourceType

# Ordered from weakest to strongest assertion. We never move a claim to a
# stronger status than its source language supports.
_STATUS_RANK = {
    ClaimStatus.UNCONFIRMED: 0,
    ClaimStatus.DISPUTED: 1,
    ClaimStatus.SUSPECT: 2,
    ClaimStatus.ACCUSED: 3,
    ClaimStatus.CHARGED: 4,
    ClaimStatus.PLEADED_GUILTY: 5,
    ClaimStatus.CONVICTED: 6,
    ClaimStatus.CONFIRMED: 6,
}

_STATUS_CUES = [
    (ClaimStatus.CONVICTED, re.compile(r"\b(convicted|found guilty|verdict of guilty|sentenced to)\b", re.I)),
    (ClaimStatus.PLEADED_GUILTY, re.compile(r"\b(pleaded guilty|pled guilty|guilty plea)\b", re.I)),
    (ClaimStatus.CHARGED, re.compile(r"\b(charged with|indicted|arraigned)\b", re.I)),
    (ClaimStatus.ACCUSED, re.compile(r"\b(accused|alleged|allegedly)\b", re.I)),
    (ClaimStatus.SUSPECT, re.compile(r"\b(suspect|person of interest|suspected)\b", re.I)),
    # "arrested" maps to CHARGED-level at most — never to guilt.
    (ClaimStatus.CHARGED, re.compile(r"\barrested\b", re.I)),
]


@dataclass
class VerificationResult:
    ok: bool
    reason: str
    sources: list[Source]
    has_official: bool
    unique_source_count: int


class Verifier:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def verify_sources(self, sources: list[Source]) -> VerificationResult:
        # Dedupe by URL/publisher — "independently useful" means distinct origins.
        seen = set()
        unique: list[Source] = []
        for s in sources:
            key = (s.url or s.title).strip().lower()
            origin = s.publisher.strip().lower()
            dedupe_key = key or origin
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            unique.append(s)

        has_official = any(
            s.source_type in {SourceType.OFFICIAL.value, SourceType.COURT.value} for s in unique
        )
        min_needed = self.settings.scoring.min_sources
        if len(unique) < min_needed:
            return VerificationResult(
                ok=False,
                reason=f"insufficient sources: {len(unique)} < MIN_SOURCES={min_needed}",
                sources=unique,
                has_official=has_official,
                unique_source_count=len(unique),
            )
        if not has_official:
            return VerificationResult(
                ok=False,
                reason="no official/court source among sources (at least one required)",
                sources=unique,
                has_official=False,
                unique_source_count=len(unique),
            )
        return VerificationResult(
            ok=True,
            reason="verified",
            sources=unique,
            has_official=True,
            unique_source_count=len(unique),
        )

    def classify_status(self, text: str) -> ClaimStatus:
        """Infer the strongest *supported* legal status from source language."""
        best = ClaimStatus.UNCONFIRMED
        for status, pattern in _STATUS_CUES:
            if pattern.search(text) and _STATUS_RANK[status] > _STATUS_RANK[best]:
                best = status
        return best

    def cap_status(self, proposed: ClaimStatus, supported: ClaimStatus) -> ClaimStatus:
        """Never allow a claim stronger than the source supports."""
        if _STATUS_RANK[proposed] > _STATUS_RANK[supported]:
            return supported
        return proposed

    def build_claims(self, facts: list[tuple[str, str, list[str]]]) -> list[Claim]:
        """facts: list of (fact_text, source_text, source_ids)."""
        claims: list[Claim] = []
        for i, (fact_text, source_text, source_ids) in enumerate(facts, start=1):
            supported = self.classify_status(source_text or fact_text)
            confidence = 0.6 + 0.1 * min(3, len(source_ids))
            claims.append(
                Claim(
                    claim_id=f"C{i:03d}",
                    claim=fact_text,
                    status=supported.value,
                    sources=source_ids,
                    confidence=round(min(0.98, confidence), 2),
                )
            )
        return claims

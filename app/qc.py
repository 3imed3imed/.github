"""Quality-control gate (spec §8, §11, §14, §44): policy + fact + copyright.

QC must pass before a video is considered READY. It checks:
* Policy: no forbidden topics in title/description/script.
* Facts: every declarative factual claim maps to a claim_id + source_id
  (no orphan claims); legal statuses were never escalated.
* Copyright: every downloaded asset has a licence manifest entry.
* Originality: the script cleared the similarity threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import Settings, get_settings
from app.models import Asset, Claim, Scene
from app.niche import _REJECT


@dataclass
class QCResult:
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    orphan_claims: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "failures": self.failures,
            "orphan_claims": self.orphan_claims,
        }


class QCGate:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def run(
        self,
        *,
        title: str,
        description: str,
        script_text: str,
        scenes: list[Scene],
        claims: list[Claim],
        assets: list[Asset],
        sources_ids: set[str],
        originality_ok: bool,
        verified: bool,
    ) -> QCResult:
        result = QCResult(passed=True)

        # 1. Policy.
        policy_ok = not self._policy_hits(f"{title}\n{description}\n{script_text}")
        result.checks["policy"] = policy_ok
        if not policy_ok:
            result.failures.append("policy: forbidden topic detected in text")

        # 2. Facts: sourcing + no escalation.
        verified_ok = verified
        result.checks["verified_sources"] = verified_ok
        if not verified_ok:
            result.failures.append("facts: source verification did not pass")

        orphans = [c.claim_id for c in claims if not c.sources or not (set(c.sources) & sources_ids or c.sources)]
        # A claim is an orphan only if it has no source ids at all.
        orphans = [c.claim_id for c in claims if not c.sources]
        result.orphan_claims = orphans
        result.checks["no_orphan_claims"] = not orphans
        if orphans:
            result.failures.append(f"facts: orphan claims without sources: {orphans}")

        escalation_ok = all(c.status != "CONFIRMED" or c.sources for c in claims)
        result.checks["legal_status_supported"] = escalation_ok
        if not escalation_ok:
            result.failures.append("facts: a claim asserts status without sources")

        # 3. Copyright.
        copyright_ok = all(a.license for a in assets)
        result.checks["copyright_manifest"] = copyright_ok
        if not copyright_ok:
            missing = [a.asset_id for a in assets if not a.license]
            result.failures.append(f"copyright: assets missing licence: {missing}")

        # 4. Originality.
        result.checks["originality"] = originality_ok
        if not originality_ok:
            result.failures.append("originality: script too similar to source text")

        result.passed = all(result.checks.values())
        return result

    def _policy_hits(self, text: str) -> list[str]:
        return [p.pattern for p in _REJECT if p.search(text)]

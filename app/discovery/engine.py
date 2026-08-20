"""Discovery orchestration: run every source, normalise, deduplicate."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.dedupe import Fingerprinter
from app.discovery.base import DiscoverySource
from app.discovery.sources import ALL_SOURCES
from app.models import Candidate
from app.observability import get_logger

log = get_logger("discovery")


class DiscoveryEngine:
    def __init__(self, settings: Settings | None = None, sources: list[DiscoverySource] | None = None):
        self.settings = settings or get_settings()
        self.sources = sources if sources is not None else [cls(self.settings) for cls in ALL_SOURCES]

    def discover(self, per_source: int = 25) -> list[Candidate]:
        seen: dict[str, Candidate] = {}
        fp = Fingerprinter()
        for source in self.sources:
            if not source.available():
                continue
            candidates = source.discover(limit=per_source)
            log.info("source=%s returned=%d", source.name, len(candidates))
            for c in candidates:
                if not c.headline:
                    continue
                key = fp.candidate_fingerprint(c)
                if key in seen:
                    continue
                seen[key] = c
        result = list(seen.values())
        log.info("discovery total unique candidates=%d", len(result))
        return result

"""Base class for discovery sources."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.models import Candidate, SourceType
from app.observability import get_logger

log = get_logger("discovery")


class DiscoverySource:
    name: str = "source"
    source_type: str = SourceType.NEWS.value
    default_jurisdiction: str = ""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def available(self) -> bool:
        return True

    def discover(self, limit: int = 25) -> list[Candidate]:
        """Fetch and normalise candidates. Must never raise — fail soft."""
        try:
            candidates = self._discover(limit=limit)
        except Exception as exc:  # noqa: BLE001
            log.warning("source %s failed: %s", self.name, exc)
            return []
        for c in candidates:
            c.source = c.source or self.name
            c.source_type = c.source_type or self.source_type
            c.jurisdiction = c.jurisdiction or self.default_jurisdiction
            c.ensure_id()
        return candidates

    def _discover(self, limit: int) -> list[Candidate]:  # pragma: no cover - abstract
        raise NotImplementedError

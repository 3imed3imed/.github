"""Job reporting, secret-safe logging and cost accounting."""

from __future__ import annotations

import logging
import re
import time
import uuid
from pathlib import Path

from app.config import Settings, get_settings
from app.models import JobReport

# Patterns we scrub from any log line to guarantee we never emit a secret.
_SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"(Token\s+)[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"([?&](?:key|api_key|token|access_token)=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(sk-[A-Za-z0-9]{6})[A-Za-z0-9]+"),
]


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        msg = record.getMessage()
        for pat in _SECRET_PATTERNS:
            msg = pat.sub(r"\1[REDACTED]", msg)
        record.msg = msg
        record.args = ()
        return True


def get_logger(name: str = "factory") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s"))
        handler.addFilter(RedactingFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


class JobTracker:
    """Accumulates a :class:`JobReport` across stages and persists it."""

    def __init__(self, story_id: str = "", settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.report = JobReport(job_id="job_" + uuid.uuid4().hex[:12], story_id=story_id)
        self._t0 = time.time()
        self.log = get_logger()

    def stage(self, stage: str) -> None:
        self.report.stage = stage
        self.log.info("stage=%s story=%s", stage, self.report.story_id)

    def record(self, *, provider: str = "", requests: int = 0, errors: int = 0, retries: int = 0, cost: float = 0.0) -> None:
        if provider:
            self.report.provider = provider
        self.report.requests += requests
        self.report.errors += errors
        self.report.retries += retries
        self.report.actual_cost += cost

    def note(self, text: str) -> None:
        self.report.notes.append(text)
        self.log.info("%s", text)

    def enforce_cost_invariant(self) -> None:
        """Hard rule: actual_cost must be 0 when paid services are disallowed."""
        if not self.settings.safety.allow_paid_services and self.report.actual_cost != 0:
            raise AssertionError(
                f"COST INVARIANT VIOLATED: actual_cost={self.report.actual_cost} "
                "while ALLOW_PAID_SERVICES=false"
            )

    def finish(self, status: str = "success") -> JobReport:
        self.report.status = status
        self.report.elapsed_time = round(time.time() - self._t0, 2)
        from datetime import datetime, timezone

        self.report.finished_at = datetime.now(timezone.utc).isoformat()
        self.enforce_cost_invariant()
        return self.report

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.report.model_dump_json(indent=2))

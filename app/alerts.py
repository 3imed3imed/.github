"""Alerting: create a GitHub Issue on serious failures.

Failures are never silently skipped. When a serious condition occurs (token
expired, all providers failed, verification failed, render failed, quota
exhausted, upload rejected) we raise an alert. In CI/production this opens a
GitHub Issue via the REST API using ``GITHUB_TOKEN``; locally it logs and writes
an alert file so nothing is lost.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from app.config import Settings, get_settings
from app.observability import get_logger
from app.providers.http import client

log = get_logger("alerts")


class Alerter:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def alert(self, title: str, body: str, *, labels: list[str] | None = None) -> dict:
        labels = labels or ["automated", "production-failure"]
        record = {
            "title": title,
            "body": body,
            "labels": labels,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        # Always persist locally so an alert is never lost.
        self._persist(record)
        log.error("ALERT: %s", title)
        if self.settings.github_token and self.settings.github_repository:
            try:
                return self._create_issue(record)
            except Exception as exc:  # noqa: BLE001
                log.error("failed to create GitHub issue: %s", exc)
        return {"status": "logged", **record}

    def _persist(self, record: dict) -> None:
        self.settings.ensure_dirs()
        alerts_dir = self.settings.data_dir / "alerts"
        alerts_dir.mkdir(parents=True, exist_ok=True)
        fname = alerts_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".json")
        fname.write_text(json.dumps(record, indent=2))

    def _create_issue(self, record: dict) -> dict:
        repo = self.settings.github_repository
        url = f"https://api.github.com/repos/{repo}/issues"
        headers = {
            "Authorization": f"Bearer {self.settings.github_token}",
            "Accept": "application/vnd.github+json",
        }
        with client(headers=headers) as c:
            resp = c.post(
                url,
                json={"title": record["title"], "body": record["body"], "labels": record["labels"]},
            )
            resp.raise_for_status()
            data = resp.json()
        return {"status": "issue_created", "number": data.get("number"), "url": data.get("html_url")}


def make_alerter(settings: Settings | None = None):
    alerter = Alerter(settings)
    return lambda msg: alerter.alert("Provider chain exhausted", msg, labels=["automated", "provider-failure"])

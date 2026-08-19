"""Validation-stage orchestration (spec §27).

Implements the staged rollout as runnable code rather than a manual checklist:

* **Stage A** — research + verification + selection only (no video). Confirms
  facts, sourcing and scoring before any rendering.
* **Stage B** — full episodes, **no upload** (render-only). Confirms render,
  audio, visuals, captions and copyright manifests.
* **Stage C** — private uploads. Confirms OAuth, processing, thumbnail,
  captions, metadata and AI disclosure. Requires ``UPLOAD_ENABLED=true`` and
  never publishes publicly (that stays gated behind ``PUBLIC_AUTO_PUBLISH``).

Each stage returns a structured, JSON-serialisable report and never weakens a
safety gate — Stage C simply refuses to run unless the owner enabled uploads.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from app.config import Settings, get_settings
from app.fixtures import DEFAULT_FIXTURE, FIXTURES, get_fixture
from app.observability import get_logger
from app.research import Researcher

log = get_logger("validate")


@dataclass
class StageItem:
    story_id: str
    ok: bool
    detail: str
    extra: dict = field(default_factory=dict)


@dataclass
class StageReport:
    stage: str
    generated_at: str
    passed: bool
    items: list[StageItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "generated_at": self.generated_at,
            "passed": self.passed,
            "items": [asdict(i) for i in self.items],
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_story_ids(n: int = 3) -> list[str]:
    ids = list(FIXTURES.keys())
    while len(ids) < n:
        ids.append(DEFAULT_FIXTURE)
    return ids[:n]


# --------------------------------------------------------------------------- #
# Stage A — research + verification + selection only
# --------------------------------------------------------------------------- #
def run_stage_a(story_ids: list[str] | None = None, settings: Settings | None = None) -> StageReport:
    settings = settings or get_settings()
    story_ids = story_ids or _default_story_ids()
    report = StageReport(stage="A", generated_at=_now(), passed=True)
    researcher = Researcher(settings)
    for sid in story_ids:
        fixture = get_fixture(sid)
        seed = fixture[1] if fixture else None
        candidate = fixture[0] if fixture else None
        if candidate is None:
            report.items.append(StageItem(sid, False, "unknown story (not a fixture)"))
            report.passed = False
            continue
        output, _ = researcher.build_fact_database(candidate, seed_sources=seed)
        ok = output.verified
        report.items.append(
            StageItem(
                story_id=candidate.id,
                ok=ok,
                detail=output.reason,
                extra={
                    "sources": len(output.sources),
                    "facts": len(output.facts),
                    "has_official": any(s.source_type in {"official", "court"} for s in output.sources),
                },
            )
        )
        report.passed = report.passed and ok
    return report


# --------------------------------------------------------------------------- #
# Stage B — full episodes, no upload (render only)
# --------------------------------------------------------------------------- #
def run_stage_b(story_ids: list[str] | None = None, settings: Settings | None = None) -> StageReport:
    settings = settings or get_settings()
    story_ids = story_ids or _default_story_ids()
    report = StageReport(stage="B", generated_at=_now(), passed=True)
    if settings.safety.upload_enabled:
        log.warning("Stage B is render-only but UPLOAD_ENABLED=true; uploads may occur downstream")
    from app.run import ProductionError, produce

    for sid in story_ids:
        try:
            outcome = produce(sid, settings)
            proj = outcome.project
            required = ["final.mp4", "thumbnail.jpg", "captions.srt", "metadata.json", "sources.json", "run_report.json"]
            missing = [f for f in required if not proj.exists(f)]
            ok = outcome.qc_passed and not missing
            report.items.append(
                StageItem(
                    story_id=outcome.story_id,
                    ok=ok,
                    detail="ok" if ok else f"qc_passed={outcome.qc_passed} missing={missing}",
                    extra={"upload_status": outcome.upload_status, "synthetic": outcome.synthetic_media_used},
                )
            )
            report.passed = report.passed and ok
        except ProductionError as exc:
            report.items.append(StageItem(sid, False, f"production failed: {exc}"))
            report.passed = False
    return report


# --------------------------------------------------------------------------- #
# Stage C — private uploads (gated)
# --------------------------------------------------------------------------- #
def run_stage_c(story_ids: list[str] | None = None, settings: Settings | None = None) -> StageReport:
    settings = settings or get_settings()
    story_ids = story_ids or _default_story_ids()
    report = StageReport(stage="C", generated_at=_now(), passed=True)
    if not settings.safety.upload_enabled:
        report.passed = False
        report.items.append(
            StageItem("*", False, "UPLOAD_ENABLED=false — Stage C requires the owner to enable uploads first")
        )
        return report
    from app.run import ProductionError, produce

    for sid in story_ids:
        try:
            outcome = produce(sid, settings)
            upload = outcome.project.read_json("upload.json") or {}
            status = upload.get("status")
            privacy = upload.get("privacy_status")
            # Uploaded (or scheduled) and never public directly.
            ok = status in {"uploaded", "scheduled"} and privacy != "public"
            report.items.append(
                StageItem(
                    story_id=outcome.story_id,
                    ok=ok,
                    detail=upload.get("detail", ""),
                    extra={"status": status, "privacy": privacy, "video_id": upload.get("video_id")},
                )
            )
            report.passed = report.passed and ok
        except ProductionError as exc:
            report.items.append(StageItem(sid, False, f"production failed: {exc}"))
            report.passed = False
    return report


_STAGES = {"a": run_stage_a, "b": run_stage_b, "c": run_stage_c}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a validation stage (spec §27).")
    parser.add_argument("--stage", required=True, choices=["a", "b", "c"], help="Validation stage to run")
    parser.add_argument("--stories", default="", help="Comma-separated story ids (default: fixtures)")
    args = parser.parse_args(argv)
    story_ids = [s.strip() for s in args.stories.split(",") if s.strip()] or None
    report = _STAGES[args.stage](story_ids)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.passed else 2


if __name__ == "__main__":
    sys.exit(main())

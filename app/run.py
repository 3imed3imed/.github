"""End-to-end single-story production (spec §45, §46).

    python -m app.run --story <story_id>

produces, under ``projects/<story_id>/``, without manual editing:
    final.mp4, thumbnail.jpg, captions.srt, metadata.json, facts.json,
    sources.json, run_report.json (+ people/timeline/claims/media/qc reports).

Every stage is idempotent and resumable; re-running continues from cached work.
Uploading is gated (render-only unless UPLOAD_ENABLED=true) and never public
without owner-set PUBLIC_AUTO_PUBLISH=true.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.alerts import Alerter, make_alerter
from app.audio import AudioStage
from app.captions import to_ass, to_srt, to_vtt
from app.config import Settings, get_settings
from app.dedupe import PublishedLedger
from app.fixtures import get_fixture
from app.models import Candidate, Claim, Fact, Person, Scene, Source
from app.observability import JobTracker, get_logger
from app.publishing.description import build_description
from app.publishing.titles import TitleEngine
from app.publishing.youtube import YouTubeUploader
from app.qc import QCGate
from app.rendering.pipeline import Renderer
from app.research import Researcher
from app.scripting import ScriptEngine
from app.state import ProductionState, StateStore
from app.storage import ProjectStore
from app.storyboard import StoryboardEngine
from app.thumbnails import ThumbnailEngine
from app.visuals import VisualsCollector

log = get_logger("run")


class ProductionError(RuntimeError):
    pass


@dataclass
class ProductionOutcome:
    story_id: str
    project: ProjectStore
    qc_passed: bool
    upload_status: str
    synthetic_media_used: bool


def _load_candidate(settings: Settings, story_id: str) -> tuple[Candidate, list[Source]]:
    fixture = get_fixture(story_id)
    if fixture:
        return fixture
    # Otherwise load from the state store meta (a real discovered candidate).
    store = StateStore(settings)
    rec = store.get(story_id)
    if rec and rec.get("meta", {}).get("candidate"):
        return Candidate(**rec["meta"]["candidate"]), []
    # Or from an existing project's sources.json.
    proj = ProjectStore(story_id, settings)
    existing = proj.read_json("sources.json")
    if existing:
        cand = Candidate(id=story_id, headline=proj.read_json("metadata.json").get("title", story_id) if proj.exists("metadata.json") else story_id)
        return cand, [Source(**s) for s in existing]
    raise ProductionError(
        f"Unknown story '{story_id}'. Provide a fixture id, a discovered candidate, "
        "or a project with sources.json."
    )


def produce(story_id: str, settings: Settings | None = None) -> ProductionOutcome:
    settings = settings or get_settings()
    settings.ensure_dirs()
    alerter = Alerter(settings)
    on_alert = make_alerter(settings)
    tracker = JobTracker(story_id=story_id, settings=settings)
    state = StateStore(settings)

    candidate, seed_sources = _load_candidate(settings, story_id)
    story_id = candidate.id
    state.create(story_id, meta={"candidate": candidate.model_dump()})

    # -- Research + verification (facts, sources, people, timeline, claims) -- #
    tracker.stage("research")
    state.transition(story_id, ProductionState.RESEARCHING, note="building fact database")
    researcher = Researcher(settings)
    research, project = researcher.build_fact_database(candidate, seed_sources=seed_sources or None)
    tracker.record(requests=1)
    if not research.verified:
        state.transition(story_id, ProductionState.REJECTED, note=research.reason)
        alerter.alert(
            "Fact verification failed",
            f"Story {story_id} could not be verified: {research.reason}",
            labels=["automated", "verification-failed"],
        )
        tracker.finish("rejected")
        tracker.write(project.path("run_report.json"))
        raise ProductionError(f"verification failed: {research.reason}")
    state.transition(story_id, ProductionState.VERIFIED, note=f"{research.reason}; sources={len(research.sources)}")

    facts: list[Fact] = research.facts
    people: list[Person] = research.people
    sources: list[Source] = research.sources
    claims = [Claim(**c) for c in (project.read_json("claims.json") or [])]

    # -- Select ------------------------------------------------------------ #
    state.transition(story_id, ProductionState.SELECTED, note="selected for production")

    # -- Title (needed for script + thumbnail) ----------------------------- #
    title_engine = TitleEngine(settings)
    title_candidates = title_engine.generate(candidate, facts)
    best_title = title_candidates[0]
    project.write_json("titles.json", [{"text": t.text, "scores": t.scores, "total": t.total} for t in title_candidates])

    # -- Script + originality ---------------------------------------------- #
    tracker.stage("script")
    script_engine = ScriptEngine(settings)
    script, originality = script_engine.write(
        title=best_title.text, facts=facts, people=people, sources=sources, on_alert=on_alert
    )
    project.write_text("script.txt", script.full_text())
    project.write_json(
        "script.json",
        {
            "title_working": script.title_working,
            "word_count": script.word_count,
            "sections": [{"name": n, "text": t} for n, t in script.sections],
            "used_fact_ids": script.used_fact_ids,
            "originality": {"max_similarity": originality.max_similarity, "ok": originality.ok},
        },
    )
    state.transition(story_id, ProductionState.SCRIPTED, note=f"{script.word_count} words; sim={originality.max_similarity}")

    # -- Storyboard -------------------------------------------------------- #
    tracker.stage("storyboard")
    storyboard = StoryboardEngine(settings)
    scenes: list[Scene] = storyboard.build(script.narration_only(), people=people)
    project.write_json("storyboard.json", [s.model_dump() for s in scenes])

    # -- Visuals ----------------------------------------------------------- #
    tracker.stage("visuals")
    state.transition(story_id, ProductionState.ASSETS, note="collecting visuals + audio")
    visuals = VisualsCollector(settings, on_alert=on_alert)
    assets = visuals.collect(project, scenes)

    # -- Audio (updates scene durations) ----------------------------------- #
    tracker.stage("audio")
    audio = AudioStage(settings, on_alert=on_alert)
    audio_result = audio.synthesize(project, scenes)
    tracker.record(provider=audio_result.provider)
    # Recompute scene start times after TTS-driven durations.
    t = 0.0
    for sc in scenes:
        sc.start = round(t, 2)
        t += sc.duration
    project.write_json("storyboard.json", [s.model_dump() for s in scenes])

    # -- Captions ---------------------------------------------------------- #
    tracker.stage("captions")
    project.write_text("captions.srt", to_srt(scenes))
    project.write_text("captions.ass", to_ass(scenes))
    project.write_text("captions.vtt", to_vtt(scenes))

    # -- Render ------------------------------------------------------------ #
    tracker.stage("render")
    state.transition(story_id, ProductionState.RENDERING, note="ffmpeg render")
    renderer = Renderer(settings, on_alert=on_alert)
    try:
        render_result = renderer.render(project, scenes, assets, audio_result.master)
    except Exception as exc:
        state.transition(story_id, ProductionState.QC_FAILED, note=f"render failed: {exc}")
        alerter.alert("Render failed", f"Story {story_id}: {exc}", labels=["automated", "render-failed"])
        tracker.record(errors=1)
        tracker.finish("failed")
        tracker.write(project.path("run_report.json"))
        raise
    synthetic_used = render_result.synthetic_used
    tracker.report.synthetic_media_used = synthetic_used

    # -- Thumbnail --------------------------------------------------------- #
    tracker.stage("thumbnail")
    thumb = ThumbnailEngine(settings)
    thumb.generate(project, title=best_title.text)

    # -- Description ------------------------------------------------------- #
    description = build_description(
        title=best_title.text,
        summary=candidate.summary,
        scenes=scenes,
        sources=sources,
        assets=assets,
        facts=facts,
        synthetic_media_used=synthetic_used,
    )
    project.write_text("description.txt", description)

    # -- QC ---------------------------------------------------------------- #
    tracker.stage("qc")
    qc = QCGate(settings)
    qc_result = qc.run(
        title=best_title.text,
        description=description,
        script_text=script.full_text(),
        scenes=scenes,
        claims=claims,
        assets=assets,
        sources_ids={s.id for s in sources},
        originality_ok=originality.ok,
        verified=research.verified,
    )
    project.write_json("qc_report.json", qc_result.as_dict())
    if not qc_result.passed:
        state.transition(story_id, ProductionState.QC_FAILED, note="; ".join(qc_result.failures))
        alerter.alert(
            "QC failed",
            f"Story {story_id} failed QC: {qc_result.failures}",
            labels=["automated", "qc-failed"],
        )
        tracker.finish("qc_failed")
        tracker.write(project.path("run_report.json"))
        _write_metadata(project, best_title.text, description, synthetic_used, qc_result.passed, sources)
        raise ProductionError(f"QC failed: {qc_result.failures}")

    state.transition(story_id, ProductionState.READY, note="passed QC")

    # -- Metadata + upload plan ------------------------------------------- #
    _write_metadata(project, best_title.text, description, synthetic_used, qc_result.passed, sources)

    tracker.stage("upload")
    uploader = YouTubeUploader(settings)
    publish_at = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
    plan = uploader.build_plan(
        video_path=render_result.final_path,
        title=best_title.text,
        description=description,
        thumbnail_path=project.path("thumbnail.jpg"),
        captions_path=project.path("captions.srt"),
        synthetic_media=synthetic_used,
        publish_at=publish_at,
    )
    upload_result = uploader.upload(plan)
    project.write_json(
        "upload.json",
        {
            "status": upload_result.status,
            "video_id": upload_result.video_id,
            "processing_status": upload_result.processing_status,
            "detail": upload_result.detail,
            "privacy_status": plan.privacy_status,
            "publish_at": plan.publish_at,
            "synthetic_media": plan.synthetic_media,
        },
    )
    if upload_result.status == "uploaded":
        state.transition(story_id, ProductionState.UPLOADED, note=upload_result.detail)
    elif upload_result.status == "scheduled":
        state.transition(story_id, ProductionState.UPLOADED, note=upload_result.detail)
        state.transition(story_id, ProductionState.SCHEDULED, note=f"publishAt={plan.publish_at}")
    if upload_result.video_id:
        PublishedLedger(settings).add(candidate, video_id=upload_result.video_id)

    tracker.finish("success")
    tracker.write(project.path("run_report.json"))
    log.info("production complete story=%s upload=%s", story_id, upload_result.status)
    return ProductionOutcome(
        story_id=story_id,
        project=project,
        qc_passed=qc_result.passed,
        upload_status=upload_result.status,
        synthetic_media_used=synthetic_used,
    )


def _write_metadata(project, title, description, synthetic, qc_passed, sources) -> None:
    project.write_json(
        "metadata.json",
        {
            "title": title,
            "description": description,
            "synthetic_media_used": synthetic,
            "qc_passed": qc_passed,
            "source_count": len(sources),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Produce one documentary episode end-to-end.")
    parser.add_argument("--story", required=True, help="Story id (fixture id or discovered candidate id)")
    args = parser.parse_args(argv)
    try:
        outcome = produce(args.story)
    except ProductionError as exc:
        log.error("production failed: %s", exc)
        return 2
    print(f"OK story={outcome.story_id} qc_passed={outcome.qc_passed} upload={outcome.upload_status}")
    print(f"Artifacts in: {outcome.project.root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

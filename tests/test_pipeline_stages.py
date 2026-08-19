"""Script/originality, storyboard/visual-safety, captions, titles, QC, uploader."""

from __future__ import annotations

from app.captions import to_srt, to_vtt
from app.models import Claim, Person, Source, VisualType
from app.publishing.titles import TitleEngine
from app.publishing.youtube import YouTubeUploader
from app.qc import QCGate
from app.research import Researcher
from app.scripting import OriginalityChecker, ScriptEngine
from app.storyboard import StoryboardEngine
from tests import fixtures_data as fx


def _research(settings):
    return Researcher(settings).build_fact_database(fx.SOLVED_COLD_CASE, seed_sources=fx.CONFLICTING_SOURCES)


def test_script_length_and_originality(settings):
    output, _ = _research(settings)
    script, report = ScriptEngine(settings).write(
        title="A Case Finally Solved", facts=output.facts, people=output.people, sources=output.sources
    )
    # Word count tracks the configured target duration (default ~5 min).
    target = settings.target_script_words()
    assert 0.8 * target <= script.word_count <= 1.25 * target
    assert report.ok  # deterministic writer must clear the similarity threshold


def test_originality_rejects_copied_text(settings):
    src = [Source(id="S01", text_excerpt="The defendant pleaded guilty to multiple counts of murder in June.")]
    checker = OriginalityChecker(settings)
    copied = "The defendant pleaded guilty to multiple counts of murder in June."
    report = checker.check(copied, src)
    assert not report.ok


def test_storyboard_beats_in_range_and_safe(settings):
    people = [Person(name="A. Person", legal_status="SUSPECT", convicted=False)]
    narration = ("A. Person was seen nearby. " * 5) + "A. Person did not commit murder in this sentence. " + ("More context follows. " * 40)
    scenes = StoryboardEngine(settings).build(narration, people=people)
    assert 20 <= len(scenes) <= 45
    # Any scene depicting an unconvicted person + a crime verb must be made safe.
    for sc in scenes:
        if "a. person" in sc.narration.lower() and "murder" in sc.narration.lower():
            assert sc.visual_type == VisualType.LOCATION.value
            assert "VISUAL SAFETY" in sc.source_requirement or sc.visual_type == VisualType.LOCATION.value


def test_captions_have_timestamps(settings):
    people = [Person(name="X")]
    scenes = StoryboardEngine(settings).build("Sentence one is here. " * 60, people=people)
    srt = to_srt(scenes)
    assert "-->" in srt
    assert "WEBVTT" in to_vtt(scenes)


def test_titles_at_least_ten_and_scored(settings):
    output, _ = _research(settings)
    titles = TitleEngine(settings).generate(fx.SOLVED_COLD_CASE, output.facts)
    assert len(titles) >= 10
    assert all(t.total > 0 for t in titles)
    # No banned sensational language in the top pick.
    assert "shocking" not in titles[0].text.lower()


def test_qc_blocks_orphan_claim(settings):
    gate = QCGate(settings)
    claims_ok = [Claim(claim_id="C001", claim="x", status="CHARGED", sources=["S01"])]
    claims_orphan = [Claim(claim_id="C001", claim="x", status="CHARGED", sources=[])]
    from app.models import Asset

    asset = Asset(asset_id="a1", provider="generated", license="own", scene_id=1)
    base = dict(
        title="A Case", description="d", script_text="clean text", scenes=[], assets=[asset],
        sources_ids={"S01"}, originality_ok=True, verified=True,
    )
    assert gate.run(claims=claims_ok, **base).passed
    assert not gate.run(claims=claims_orphan, **base).passed


def test_uploader_dry_run_when_disabled(settings):
    from pathlib import Path

    up = YouTubeUploader(settings)
    plan = up.build_plan(
        video_path=Path("nope.mp4"), title="t", description="d", thumbnail_path=None,
        captions_path=None, synthetic_media=True, publish_at="2030-01-01T00:00:00Z",
    )
    # Privacy never public; publishAt suppressed unless auto-publish enabled.
    assert plan.privacy_status in {"none", "private"}
    assert plan.publish_at is None  # PUBLIC_AUTO_PUBLISH=false
    result = up.upload(plan)
    assert result.status == "dry-run"
    assert result.video_id is None


def test_script_length_tracks_target_minutes(monkeypatch):
    # Owner-configurable target duration drives the word count (spec §10 override).
    monkeypatch.setenv("TARGET_VIDEO_MINUTES", "5")
    from app.config import reload_settings
    s = reload_settings()
    output, _ = Researcher(s).build_fact_database(fx.SOLVED_COLD_CASE, seed_sources=fx.CONFLICTING_SOURCES)
    script, report = ScriptEngine(s).write(
        title="A Case", facts=output.facts, people=output.people, sources=output.sources
    )
    target = s.target_script_words()  # 775
    # Within ~20% of the target so rendered duration lands near 5 minutes.
    assert 0.8 * target <= script.word_count <= 1.25 * target
    assert report.ok
    reload_settings()

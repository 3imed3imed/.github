"""Validation-stage orchestration (spec §27)."""

from __future__ import annotations

from app.validate import run_stage_a, run_stage_c


def test_stage_a_verifies_fixture_stories(settings):
    report = run_stage_a(settings=settings)
    assert report.stage == "A"
    assert report.passed  # fixtures ship with >=3 sources incl. official/court
    assert len(report.items) >= 2
    for item in report.items:
        assert item.ok
        assert item.extra["sources"] >= settings.scoring.min_sources
        assert item.extra["has_official"] is True


def test_stage_a_flags_unknown_story(settings):
    report = run_stage_a(["not-a-real-story"], settings=settings)
    assert not report.passed
    assert report.items[0].ok is False


def test_stage_c_refuses_without_upload_enabled(settings):
    # Default safety: uploads disabled -> Stage C must refuse (never silently pass).
    report = run_stage_c(settings=settings)
    assert not report.passed
    assert "UPLOAD_ENABLED=false" in report.items[0].detail


def test_stage_report_is_json_serializable(settings):
    import json

    report = run_stage_a(settings=settings)
    json.dumps(report.to_dict())  # must not raise

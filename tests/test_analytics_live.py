"""Live YouTube Analytics collector: normalizer + graceful degradation (spec §29)."""

from __future__ import annotations


def test_collect_live_returns_empty_without_oauth(settings):
    # No YouTube OAuth configured -> collector degrades to [] (never raises).
    from app.analytics import AnalyticsEngine

    assert AnalyticsEngine(settings)._collect_live() == []


def test_normalize_performance_maps_category_via_ledger(settings):
    from app.analytics import AnalyticsEngine
    from app.dedupe import PublishedLedger
    from app.models import Candidate

    # Publish a fraud story under a known video id.
    ledger = PublishedLedger(settings)
    cand = Candidate(id="s1", headline="A major investment fraud scheme unravels", url="https://x").ensure_id()
    ledger.add(cand, video_id="VID123")

    eng = AnalyticsEngine(settings)
    videos = [{"video_id": "VID123", "title": "Fraud doc"}, {"video_id": "VID999", "title": "A daring museum heist"}]
    metrics = {
        "VID123": {"views": 1000, "averageViewPercentage": 55, "likes": 40, "comments": 5},
        "VID999": {"views": 500, "averageViewPercentage": 33},
    }
    records = eng._normalize_performance(videos, metrics)
    by_id = {r["video_id"]: r for r in records}
    # Category recovered from the ledger headline (fraud) for the known video.
    assert by_id["VID123"]["category"] == "fraud"
    assert by_id["VID123"]["avg_percentage_viewed"] == 55.0
    assert by_id["VID123"]["views"] == 1000.0
    # Unknown video falls back to classifying its own title (heist).
    assert by_id["VID999"]["category"] == "heist"


def test_normalize_feeds_analyze_and_biases_selection(settings):
    # End-to-end within analytics: normalized records -> analyze -> weights.
    from app.analytics import AnalyticsEngine

    eng = AnalyticsEngine(settings)
    videos = [{"video_id": "v1", "title": "t1"}, {"video_id": "v2", "title": "t2"}]
    metrics = {
        "v1": {"averageViewPercentage": 70},
        "v2": {"averageViewPercentage": 30},
    }
    # No ledger entries -> category from titles ("other"); still valid records.
    records = eng._normalize_performance(videos, metrics)
    report = eng.analyze(records)
    assert report.videos_considered == 2
    assert report.to_dict()["safety_rules_unchanged"] is True


def test_shared_oauth_helper_reports_not_ready(settings):
    from app.publishing.google_auth import oauth_ready

    assert oauth_ready(settings) is False

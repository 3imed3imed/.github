"""Visual-mix budget (spec §15), analytics, cleanup and ASS captions."""

from __future__ import annotations

from collections import Counter

from app.captions import to_ass
from app.config import reload_settings
from app.models import Person, VisualType
from app.storyboard import _MIX_CATEGORY_TYPES, StoryboardEngine

_CATEGORY_OF = {vt: cat for cat, types in _MIX_CATEGORY_TYPES.items() for vt in types}


def _category_counts(scenes):
    c = Counter()
    for sc in scenes:
        vt = VisualType(sc.visual_type)
        # LOCATION appears both as a stock type and as the visual-safety override;
        # classify by our category map, defaulting stock.
        c[_CATEGORY_OF.get(vt, "stock")] += 1
    return c


def test_visual_mix_allocation_matches_config(settings):
    narration = "This is a documentary sentence about the case. " * 80
    scenes = StoryboardEngine(settings).build(narration, people=[])
    n = len(scenes)
    counts = _category_counts(scenes)
    mix = settings.visual_mix
    # AI reconstruction should be near its configured share (0.15), within tolerance.
    ai_share = counts.get("ai_reconstruction", 0) / n
    assert 0.08 <= ai_share <= 0.24, f"ai share {ai_share} out of expected band"
    # Stock should be the largest category (0.40 configured).
    assert counts["stock"] >= counts.get("records", 0)
    assert mix.stock > mix.records  # config sanity


def test_visual_mix_configurable_no_ai(monkeypatch):
    monkeypatch.setenv("MIX_AI_RECONSTRUCTION", "0.0")
    monkeypatch.setenv("MIX_STOCK", "0.6")
    monkeypatch.setenv("MIX_RECORDS", "0.4")
    monkeypatch.setenv("MIX_STILLS_MOTION", "0.0")
    s = reload_settings()
    scenes = StoryboardEngine(s).build("A sentence about the case here. " * 80, people=[])
    counts = _category_counts(scenes)
    assert counts.get("ai_reconstruction", 0) == 0  # no AI when configured to 0
    reload_settings()


def test_ai_scene_gets_disclosure_prompt_and_safety(settings):
    # An AI scene mentioning an unconvicted person + crime must be made safe.
    people = [Person(name="Jane Doe", legal_status="SUSPECT", convicted=False)]
    narration = "Jane Doe allegedly did murder someone in this beat. " + ("Filler sentence. " * 120)
    scenes = StoryboardEngine(settings).build(narration, people=people)
    for sc in scenes:
        if "jane doe" in sc.narration.lower() and "murder" in sc.narration.lower():
            assert sc.visual_type == VisualType.LOCATION.value
        if sc.visual_type == VisualType.AI_RECONSTRUCTION.value:
            assert "NOT look like authentic" in sc.ai_prompt


def test_ass_captions_wellformed(settings):
    people = [Person(name="X")]
    scenes = StoryboardEngine(settings).build("A sentence here for captions. " * 60, people=people)
    ass = to_ass(scenes)
    assert "[Script Info]" in ass
    assert "Dialogue:" in ass
    assert ass.count("Dialogue:") == len(scenes)


def test_analytics_no_data_leaves_weights_unchanged(settings):
    from app.analytics import AnalyticsEngine

    report = AnalyticsEngine(settings).run_weekly()
    d = report.to_dict()
    assert d["safety_rules_unchanged"] is True
    assert d["videos_considered"] == 0


def test_analytics_recommendations_from_data(settings):
    import json

    settings.ensure_dirs()
    perf = [
        {"title": "How it was solved", "category": "cold_case", "avg_percentage_viewed": 60},
        {"title": "What happened?", "category": "fraud", "avg_percentage_viewed": 40},
    ]
    (settings.data_dir / "performance.json").write_text(json.dumps(perf))
    from app.analytics import AnalyticsEngine

    report = AnalyticsEngine(settings).run_weekly()
    assert report.videos_considered == 2
    assert report.recommendations  # produced advisory weights
    assert (settings.data_dir / "selection_weights.json").exists()


def test_cleanup_keeps_deliverables(settings):
    from app.cleanup import cleanup
    from app.storage import ProjectStore

    store = ProjectStore("t_clean", settings)
    (store.path("final.mp4")).write_bytes(b"video")
    (store.path("thumbnail.jpg")).write_bytes(b"jpg")
    scenes_dir = store.path("scenes")
    (scenes_dir / "scene_001.mp4").write_bytes(b"x" * 1000)
    cleanup(settings)
    assert store.path("final.mp4").exists()
    assert store.path("thumbnail.jpg").exists()
    assert not (scenes_dir / "scene_001.mp4").exists()  # intermediate pruned

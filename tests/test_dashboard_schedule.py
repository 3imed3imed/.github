"""Schedule screen + WebVTT captions endpoints (control-room upgrade)."""

from __future__ import annotations


def _client():
    from fastapi.testclient import TestClient

    from dashboard.app import app

    return TestClient(app)


def _make_episode(settings, sid="t_sched"):
    from app.storage import ProjectStore

    store = ProjectStore(sid, settings)
    store.path("final.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42stub")
    store.write_json("metadata.json", {"title": "Scheduled Ep", "synthetic_media_used": False})
    store.write_json("qc_report.json", {"passed": True, "checks": {"policy": True}})
    store.write_text("captions.srt", "1\n00:00:00,000 --> 00:00:03,000\nHello world\n")
    return store


def test_schedule_lists_daily_stages(settings):
    d = _client().get("/api/schedule").json()
    assert d["timezone"]
    keys = {s["key"] for s in d["stages"]}
    # The full daily pipeline is represented, in configured-time order.
    assert {"discover", "render", "qc", "upload", "publish"} <= keys
    times = [s["time"] for s in d["stages"]]
    assert times == sorted(times)
    # Each stage carries a concrete next-run wall clock.
    assert all(s["next_run"] for s in d["stages"])


def test_schedule_reports_guardrails_and_weekly(settings):
    d = _client().get("/api/schedule").json()
    assert d["guardrails"]["one_job_at_a_time"] is True
    assert d["guardrails"]["max_runtime_minutes"] == 180
    assert d["weekly"]["analytics_day"] == "sunday"


def test_schedule_publication_queue(settings):
    _make_episode(settings)
    d = _client().get("/api/schedule").json()
    ours = [p for p in d["publications"] if p["story_id"] == "t_sched"]
    assert ours and ours[0]["stage"] == "ready"
    # Render-only: privacy is none and nothing is scheduled public.
    assert ours[0]["privacy"] == "none"
    assert ours[0]["publish_at"] is None


def test_captions_vtt_conversion(settings):
    _make_episode(settings)
    r = _client().get("/api/captions/t_sched/vtt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/vtt")
    body = r.text
    assert body.startswith("WEBVTT")
    # SRT comma millisecond separators become dots for WebVTT.
    assert "00:00:00.000 --> 00:00:03.000" in body
    assert "Hello world" in body


def test_captions_vtt_missing_is_404(settings):
    from app.storage import ProjectStore

    ProjectStore("t_nocap", settings).path("final.mp4").write_bytes(b"stub")
    assert _client().get("/api/captions/t_nocap/vtt").status_code == 404

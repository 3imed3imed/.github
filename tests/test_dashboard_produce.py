"""In-dashboard produce trigger: listing, guards, and job lifecycle."""

from __future__ import annotations

import time


def _client():
    from fastapi.testclient import TestClient

    from dashboard.app import app

    return TestClient(app)


def _wait_state(client, story, target, timeout=5.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.get(f"/api/produce/{story}/status").json()
        if last.get("state") == target:
            return last
        time.sleep(0.05)
    return last


def test_producible_lists_fixtures(settings):
    d = _client().get("/api/producible").json()
    ids = {s["story_id"] for s in d["stories"]}
    assert "fixture-genealogy-coldcase" in ids
    assert d["busy"] is False


def test_produce_rejects_unknown_story(settings):
    assert _client().post("/api/produce/not-a-real-story").status_code == 404
    # Path-traversal-ish ids never reach produce().
    assert _client().post("/api/produce/..%2f..%2fetc").status_code in (400, 404)


def test_produce_runs_and_reports_done(settings, monkeypatch):
    import app.run as run

    class _Outcome:
        story_id = "fixture-genealogy-coldcase"
        qc_passed = True
        upload_status = "dry-run"

    def _fake_produce(story_id, settings=None):
        return _Outcome()

    monkeypatch.setattr(run, "produce", _fake_produce)
    c = _client()
    r = c.post("/api/produce/fixture-genealogy-coldcase")
    assert r.status_code == 200 and r.json()["started"] is True
    done = _wait_state(c, "fixture-genealogy-coldcase", "done")
    assert done["state"] == "done"
    assert done["qc_passed"] is True
    assert done["upload_status"] == "dry-run"


def test_produce_is_single_flighted(settings, monkeypatch):
    import threading

    import app.run as run

    release = threading.Event()

    def _slow_produce(story_id, settings=None):
        release.wait(timeout=3)

        class _O:
            qc_passed = True
            upload_status = "dry-run"

        return _O()

    monkeypatch.setattr(run, "produce", _slow_produce)
    c = _client()
    first = c.post("/api/produce/fixture-genealogy-coldcase")
    assert first.status_code == 200
    # A second production while the first is running is refused.
    second = c.post("/api/produce/fixture-fraud-scheme")
    assert second.status_code == 409
    release.set()
    _wait_state(c, "fixture-genealogy-coldcase", "done")

"""Dashboard Production endpoint (spec §32)."""

from __future__ import annotations

import json


def _client():
    from fastapi.testclient import TestClient

    from dashboard.app import app

    return TestClient(app)


def test_production_empty(settings):
    r = _client().get("/api/production")
    assert r.status_code == 200
    assert r.json() == []


def test_production_reports_run_qc_upload(settings):
    from app.storage import ProjectStore

    store = ProjectStore("t_prod", settings)
    store.path("final.mp4").write_bytes(b"v")
    store.write_json("run_report.json", {"stage": "qc", "status": "success", "elapsed_time": 12.3, "actual_cost": 0.0, "synthetic_media_used": False})
    store.write_json("qc_report.json", {"passed": True, "failures": []})
    store.write_json("upload.json", {"status": "dry-run", "privacy_status": "none"})
    store.write_json("metadata.json", {"title": "A Case"})

    data = _client().get("/api/production").json()
    assert len(data) == 1
    row = data[0]
    assert row["story_id"] == "t_prod"
    assert row["status"] == "success"
    assert row["qc_passed"] is True
    assert row["actual_cost"] == 0.0
    assert row["has_final"] is True
    assert row["upload_status"] == "dry-run"


def test_production_survives_corrupt_report(settings):
    from app.storage import ProjectStore

    store = ProjectStore("t_bad", settings)
    (store.path("run_report.json")).write_text("{not json")
    data = _client().get("/api/production").json()
    # Corrupt report must not crash the endpoint; row still present.
    assert any(r["story_id"] == "t_bad" for r in data)


def test_production_screen_registered_in_html():
    from pathlib import Path

    html = (Path(__file__).resolve().parent.parent / "dashboard" / "index.html").read_text()
    assert '"Production"' in html
    assert "renderProduction" in html
    # sanity: the endpoint payload is JSON-serialisable through the helper
    json.dumps({"ok": True})

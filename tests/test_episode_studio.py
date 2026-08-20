"""Episode Studio endpoints: watch + edit (spec §32)."""

from __future__ import annotations

import json


def _client():
    from fastapi.testclient import TestClient

    from dashboard.app import app

    return TestClient(app)


def _make_episode(settings, sid="t_studio"):
    from app.storage import ProjectStore

    store = ProjectStore(sid, settings)
    # a tiny valid mp4 stand-in is unnecessary; existence is what endpoints check
    store.path("final.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42stub")
    store.write_json("metadata.json", {"title": "Original Title", "synthetic_media_used": False})
    store.write_text("description.txt", "Original description.")
    store.write_json("qc_report.json", {"passed": True, "checks": {"policy": True}})
    store.write_json("sources.json", [{"id": "S01", "title": "A", "source_type": "official"}])
    store.write_json("script.json", {"word_count": 1111, "sections": []})
    store.write_json("storyboard.json", [{"scene_id": 1}, {"scene_id": 2}])
    store.write_text("captions.srt", "1\n00:00:00,000 --> 00:00:03,000\nHello\n")
    return store


def test_episode_detail(settings):
    _make_episode(settings)
    r = _client().get("/api/episode/t_studio")
    assert r.status_code == 200
    d = r.json()
    assert d["title"] == "Original Title"
    assert d["has_video"] and d["has_captions"]
    assert d["script_words"] == 1111
    assert d["storyboard_scenes"] == 2


def test_video_streams(settings):
    _make_episode(settings)
    r = _client().get("/api/video/t_studio")
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    assert b"ftyp" in r.content


def test_captions_served(settings):
    _make_episode(settings)
    r = _client().get("/api/captions/t_studio")
    assert r.status_code == 200
    assert "Hello" in r.text


def test_edit_metadata_writes_back(settings):
    store = _make_episode(settings)
    c = _client()
    r = c.post("/api/episode/t_studio/metadata", json={"title": "Edited Title", "description": "New body copy."})
    assert r.status_code == 200
    assert r.json()["title"] == "Edited Title"
    # Persisted to disk.
    md = json.loads((store.path("metadata.json")).read_text())
    assert md["title"] == "Edited Title"
    assert (store.path("description.txt")).read_text() == "New body copy."
    # Reflected on subsequent GET.
    assert c.get("/api/episode/t_studio").json()["title"] == "Edited Title"


def test_edit_rejects_empty(settings):
    _make_episode(settings)
    r = _client().post("/api/episode/t_studio/metadata", json={})
    assert r.status_code == 400


def test_path_traversal_rejected(settings):
    _make_episode(settings)
    c = _client()
    assert c.get("/api/episode/..%2f..%2fetc").status_code in (400, 404)
    assert c.get("/api/video/nonexistent").status_code == 404


def test_episode_chapters_and_checks(settings):
    store = _make_episode(settings, sid="t_chap")
    store.write_text(
        "description.txt",
        "Intro line.\n\nChapters:\n00:00 Introduction\n01:30 The turn\n1:02:03 Late\n\nSources:\n- x",
    )
    store.write_json("qc_report.json", {"passed": True, "checks": {"policy": True, "originality": False}})
    d = _client().get("/api/episode/t_chap").json()
    chapters = d["chapters"]
    assert [c["time"] for c in chapters] == ["00:00", "01:30", "1:02:03"]
    assert chapters[1]["seconds"] == 90 and chapters[2]["seconds"] == 3723
    assert chapters[0]["label"] == "Introduction"
    # QC checks are surfaced individually for the studio checklist.
    assert d["qc_checks"] == {"policy": True, "originality": False}


def test_thumbnail_served(settings):
    store = _make_episode(settings, sid="t_thumb")
    store.path("thumbnail.jpg").write_bytes(b"\xff\xd8\xff\xe0stubjpeg")
    r = _client().get("/api/thumbnail/t_thumb")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert _client().get("/api/episode/t_thumb").json()["has_thumbnail"] is True


def test_thumbnail_missing_is_404(settings):
    _make_episode(settings, sid="t_nothumb")
    assert _client().get("/api/thumbnail/t_nothumb").status_code == 404


def test_chapters_survive_premature_header_and_long_marks(settings):
    from dashboard.app import _parse_chapters

    # A stray "Chapters:" in the summary must not swallow the real block, and a
    # 100-minute-plus mark must still parse.
    desc = (
        "Chapters: coming up in this episode we cover a lot.\n"
        "This is just prose, not a timestamp.\n\n"
        "Chapters:\n00:00 Intro\n100:00 Very late mark\n\nSources:\n- x"
    )
    ch = _parse_chapters(desc)
    assert [c["time"] for c in ch] == ["00:00", "100:00"]
    assert ch[1]["seconds"] == 6000


def test_source_url_scheme_is_validated_client_side():
    # The dashboard must not turn a javascript: source URL into an href.
    import re
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "function safeUrl" in html
    # Source links go through safeUrl, never the raw url.
    assert "safeUrl(s.url)" in html
    assert not re.search(r'href="\$\{esc\(s\.url\)\}"', html)

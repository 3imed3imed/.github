"""FastAPI dashboard (spec §32, §33).

Read-only operational view over local state/artifacts, plus a provider matrix and
a connectors screen that never reveals secrets. Runs entirely on local files, so
it works with zero external services.

    uvicorn dashboard.app:app --port 8080
"""

from __future__ import annotations

import json
from pathlib import Path

from app.analytics import AnalyticsEngine
from app.config import get_settings
from app.health import run_all
from app.providers.legal import CourtListenerProvider
from app.providers.llm import build_llm_chain
from app.providers.stock import build_stock_chain
from app.providers.tts import build_tts_chain
from app.providers.video import build_video_chain
from app.setup_wizard import status_table
from app.state import ProductionState, StateStore

try:
    from fastapi import Body, FastAPI, HTTPException
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Install dashboard extras: pip install '.[dashboard]'") from exc

app = FastAPI(title="Crime YouTube Factory")


def _provider_matrix() -> list[dict]:
    s = get_settings()
    rows: list[dict] = []
    for chain in (build_llm_chain(s), build_tts_chain(s), build_video_chain(s), build_stock_chain(s)):
        rows.extend(chain.describe())
    rows.extend([CourtListenerProvider(s).describe()])
    return rows


def _overview() -> dict:
    s = get_settings()
    store = StateStore(s)
    stories = store.all()
    counts: dict[str, int] = {}
    for rec in stories.values():
        counts[rec["state"]] = counts.get(rec["state"], 0) + 1
    published = counts.get(ProductionState.PUBLISHED.value, 0)
    ready = counts.get(ProductionState.READY.value, 0)
    videos = sum(1 for p in s.projects_dir.glob("*/final.mp4")) if s.projects_dir.exists() else 0
    return {
        "counts": counts,
        "total_stories": len(stories),
        "videos_generated": videos,
        "ready": ready,
        "published": published,
        "upload_enabled": s.safety.upload_enabled,
        "public_auto_publish": s.safety.public_auto_publish,
        "allow_paid": s.safety.allow_paid_services,
        "timezone": s.timezone,
    }


def _production() -> list[dict]:
    """Per-project production reports (run_report + qc + upload status)."""
    s = get_settings()
    out: list[dict] = []
    if not s.projects_dir.exists():
        return out

    def _read(proj, name: str):
        p = proj / name
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except Exception:
            return None

    for proj in sorted(s.projects_dir.iterdir()):
        if not proj.is_dir():
            continue
        run = _read(proj, "run_report.json") or {}
        qc = _read(proj, "qc_report.json") or {}
        upload = _read(proj, "upload.json") or {}
        meta = _read(proj, "metadata.json") or {}
        out.append(
            {
                "story_id": proj.name,
                "stage": run.get("stage", ""),
                "status": run.get("status", ""),
                "finished_at": run.get("finished_at", ""),
                "elapsed_time": run.get("elapsed_time", 0),
                "actual_cost": run.get("actual_cost", 0),
                "synthetic_media": run.get("synthetic_media_used", False),
                "qc_passed": qc.get("passed"),
                "qc_failures": qc.get("failures", []),
                "upload_status": upload.get("status", ""),
                "privacy": upload.get("privacy_status", ""),
                "title": meta.get("title", ""),
                "has_final": (proj / "final.mp4").exists(),
            }
        )
    # Most recently finished first (unfinished runs, with empty finished_at,
    # sort to the bottom).
    out.sort(key=lambda r: r.get("finished_at") or "", reverse=True)
    return out


def _alerts() -> list[dict]:
    s = get_settings()
    adir = s.data_dir / "alerts"
    out = []
    if adir.exists():
        for f in sorted(adir.glob("*.json"), reverse=True)[:10]:
            try:
                out.append(json.loads(f.read_text()))
            except Exception:
                pass
    return out


@app.get("/api/overview")
def api_overview() -> JSONResponse:
    return JSONResponse(_overview())


@app.get("/api/stories")
def api_stories() -> JSONResponse:
    store = StateStore(get_settings())
    return JSONResponse(store.all())


@app.get("/api/providers")
def api_providers() -> JSONResponse:
    return JSONResponse(_provider_matrix())


@app.get("/api/connectors")
def api_connectors() -> JSONResponse:
    return JSONResponse([{"name": n, "state": st, "purpose": p} for n, st, p in status_table()])


@app.get("/api/health")
def api_health() -> JSONResponse:
    return JSONResponse([c.__dict__ for c in run_all()])


@app.get("/api/analytics")
def api_analytics() -> JSONResponse:
    return JSONResponse(AnalyticsEngine().run_weekly().to_dict())


@app.get("/api/production")
def api_production() -> JSONResponse:
    return JSONResponse(_production())


# --------------------------------------------------------------------------- #
# Episode Studio — watch the full video and edit its metadata (spec §32)
# --------------------------------------------------------------------------- #
def _project_dir(story: str) -> Path:
    """Resolve a project directory, refusing any path traversal."""
    s = get_settings()
    if not story or "/" in story or "\\" in story or story.startswith("."):
        raise HTTPException(status_code=400, detail="invalid story id")
    base = s.projects_dir.resolve()
    proj = (s.projects_dir / story).resolve()
    if proj.parent != base or not proj.is_dir():
        raise HTTPException(status_code=404, detail="unknown story")
    return proj


@app.get("/api/episode/{story}")
def api_episode(story: str) -> JSONResponse:
    proj = _project_dir(story)

    def _read(name: str):
        p = proj / name
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except Exception:
            return None

    md = _read("metadata.json") or {}
    script = _read("script.json") or {}
    return JSONResponse(
        {
            "story_id": story,
            "title": md.get("title", ""),
            "description": (proj / "description.txt").read_text() if (proj / "description.txt").exists() else md.get("description", ""),
            "synthetic_media": md.get("synthetic_media_used", False),
            "qc": _read("qc_report.json") or {},
            "sources": _read("sources.json") or [],
            "storyboard_scenes": len(_read("storyboard.json") or []),
            "script_words": script.get("word_count", 0),
            "script_sections": script.get("sections", []),
            "has_video": (proj / "final.mp4").exists(),
            "has_captions": (proj / "captions.srt").exists(),
        }
    )


@app.get("/api/video/{story}")
def api_video(story: str):
    proj = _project_dir(story)
    video = proj / "final.mp4"
    if not video.exists():
        raise HTTPException(status_code=404, detail="no video")
    # FileResponse serves HTTP Range requests, so the browser can seek/stream.
    return FileResponse(str(video), media_type="video/mp4", filename=f"{story}.mp4")


@app.get("/api/captions/{story}")
def api_captions(story: str) -> PlainTextResponse:
    proj = _project_dir(story)
    srt = proj / "captions.srt"
    if not srt.exists():
        raise HTTPException(status_code=404, detail="no captions")
    return PlainTextResponse(srt.read_text())


@app.post("/api/episode/{story}/metadata")
def api_edit_metadata(story: str, payload: dict = Body(...)) -> JSONResponse:
    """Edit the episode's title and/or description. Writes back to disk.

    Only title and description are editable here — the safe, non-destructive
    fields. The video master is not touched (these are upload-time metadata).
    """
    proj = _project_dir(story)
    md_path = proj / "metadata.json"
    md = {}
    if md_path.exists():
        try:
            md = json.loads(md_path.read_text())
        except Exception:
            md = {}
    changed = []
    title = payload.get("title")
    if isinstance(title, str) and title.strip():
        md["title"] = title.strip()[:100]
        changed.append("title")
    description = payload.get("description")
    if isinstance(description, str) and description.strip():
        md["description"] = description.strip()[:4900]
        (proj / "description.txt").write_text(md["description"])
        changed.append("description")
    if not changed:
        raise HTTPException(status_code=400, detail="nothing to update (title/description)")
    md["edited_at"] = _now_iso()
    tmp = md_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(md, indent=2))
    tmp.replace(md_path)
    return JSONResponse({"ok": True, "changed": changed, "title": md.get("title", "")})


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@app.get("/api/alerts")
def api_alerts() -> JSONResponse:
    return JSONResponse(_alerts())


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    html = (Path(__file__).parent / "index.html").read_text()
    return html

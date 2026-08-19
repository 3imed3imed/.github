"""FastAPI dashboard (spec §32, §33).

Read-only operational view over local state/artifacts, plus a provider matrix and
a connectors screen that never reveals secrets. Runs entirely on local files, so
it works with zero external services.

    uvicorn dashboard.app:app --port 8080
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

from app.analytics import AnalyticsEngine
from app.config import REPO_ROOT, get_settings
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


def _read_project_json(proj: Path, name: str):
    """Load a project JSON file, returning None if absent or unparseable."""
    p = proj / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _production() -> list[dict]:
    """Per-project production reports (run_report + qc + upload status)."""
    s = get_settings()
    out: list[dict] = []
    if not s.projects_dir.exists():
        return out

    def _read(proj, name: str):
        return _read_project_json(proj, name)

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


_STAGE_LABELS = {
    "discover": "Discover stories",
    "verify_score": "Verify + score",
    "select_winner": "Select winner",
    "script_board": "Script + storyboard",
    "assets": "Assets",
    "render": "Render",
    "qc": "Quality control",
    "upload": "Upload (gated)",
    "publish": "Scheduled publish",
}


def _load_schedule_file() -> dict:
    path = REPO_ROOT / "config" / "schedule.yml"
    if not path.exists():
        return {}
    try:
        import yaml

        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def _tz(name: str):
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:  # pragma: no cover - tzdata missing
        return None


def _next_occurrence(hhmm: str, tz) -> datetime | None:
    """Next wall-clock datetime for an ``HH:MM`` time in the given timezone."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(hhmm).strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    now = datetime.now(tz) if tz else datetime.now()
    nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return nxt


def _schedule() -> dict:
    s = get_settings()
    cfg = _load_schedule_file()
    tzname = cfg.get("timezone") or s.timezone
    tz = _tz(tzname)
    now = datetime.now(tz) if tz else datetime.now()

    daily = cfg.get("daily", {}) or {}
    stages = []
    for key, label in _STAGE_LABELS.items():
        t = daily.get(key)
        if not t:
            continue
        nxt = _next_occurrence(t, tz)
        stages.append(
            {
                "key": key,
                "label": label,
                "time": t,
                "next_run": nxt.isoformat() if nxt else None,
                "in_minutes": int((nxt - now).total_seconds() // 60) if nxt else None,
            }
        )

    def _time_key(st: dict) -> tuple[int, int]:
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(st["time"]).strip())
        return (int(m.group(1)), int(m.group(2))) if m else (99, 99)

    stages.sort(key=_time_key)

    weekly = cfg.get("weekly", {}) or {}
    return {
        "timezone": tzname,
        "now": now.isoformat(),
        "stages": stages,
        "weekly": {
            "analytics_day": weekly.get("analytics_day"),
            "analytics_time": weekly.get("analytics_time"),
        },
        "guardrails": {
            "one_job_at_a_time": cfg.get("one_job_at_a_time"),
            "max_runtime_minutes": cfg.get("max_runtime_minutes"),
        },
        "upload_enabled": s.safety.upload_enabled,
        "public_auto_publish": s.safety.public_auto_publish,
        "publications": _publication_queue(),
    }


def _publication_queue() -> list[dict]:
    """Rendered episodes and where they sit in the publish pipeline."""
    s = get_settings()
    out: list[dict] = []
    if not s.projects_dir.exists():
        return out

    for proj in sorted(s.projects_dir.iterdir()):
        if not proj.is_dir() or not (proj / "final.mp4").exists():
            continue
        meta = _read_project_json(proj, "metadata.json") or {}
        upload = _read_project_json(proj, "upload.json") or {}
        qc = _read_project_json(proj, "qc_report.json") or {}
        privacy = upload.get("privacy_status") or "none"
        publish_at = upload.get("publish_at")
        if publish_at:
            stage = "scheduled"
        elif upload.get("status") in {"uploaded", "success"}:
            stage = "uploaded"
        elif qc.get("passed"):
            stage = "ready"
        else:
            stage = "rendered"
        out.append(
            {
                "story_id": proj.name,
                "title": meta.get("title", proj.name),
                "stage": stage,
                "privacy": privacy,
                "publish_at": publish_at,
                "qc_passed": qc.get("passed"),
            }
        )
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


@app.get("/api/schedule")
def api_schedule() -> JSONResponse:
    return JSONResponse(_schedule())


# --------------------------------------------------------------------------- #
# In-dashboard "produce episode" trigger (one job at a time, spec §33)
# --------------------------------------------------------------------------- #
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,80}$")
_produce_lock = threading.Lock()
_produce_jobs: dict[str, dict] = {}


def _producible_ids() -> dict[str, str]:
    """Map of story ids that can be produced now -> a human label.

    Shipped fixtures plus any existing project that already has a sources.json
    (a selected/discovered story). Never accepts an arbitrary path.
    """
    out: dict[str, str] = {}
    try:
        from app.fixtures import FIXTURES

        for sid, (cand, _srcs) in FIXTURES.items():
            out[sid] = getattr(cand, "headline", "") or sid
    except Exception:
        pass
    s = get_settings()
    if s.projects_dir.exists():
        for proj in sorted(s.projects_dir.iterdir()):
            if proj.is_dir() and (proj / "sources.json").exists():
                out.setdefault(proj.name, proj.name)
    return out


def _run_production(story: str) -> None:
    from app.run import produce

    job = _produce_jobs[story]
    try:
        outcome = produce(story)
        job.update(
            state="done",
            finished_at=_now_iso(),
            qc_passed=getattr(outcome, "qc_passed", None),
            upload_status=getattr(outcome, "upload_status", None),
        )
    except Exception as exc:  # noqa: BLE001
        job.update(state="error", finished_at=_now_iso(), error=str(exc)[:400])
    finally:
        _produce_lock.release()


@app.get("/api/producible")
def api_producible() -> JSONResponse:
    running = [sid for sid, j in _produce_jobs.items() if j.get("state") == "running"]
    return JSONResponse(
        {
            "stories": [{"story_id": k, "label": v} for k, v in _producible_ids().items()],
            "busy": bool(running),
            "running": running,
        }
    )


@app.post("/api/produce/{story}")
def api_produce(story: str) -> JSONResponse:
    if not _ID_RE.match(story or "") or story not in _producible_ids():
        raise HTTPException(status_code=404, detail="unknown or non-producible story")
    # One production at a time (mirrors the pipeline's concurrency guard).
    if not _produce_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="a production is already running")
    # Bound the job history so a long-lived dashboard doesn't grow it forever.
    if len(_produce_jobs) > 50:
        for sid in [s for s, j in _produce_jobs.items() if j.get("state") != "running"][:25]:
            _produce_jobs.pop(sid, None)
    _produce_jobs[story] = {"state": "running", "started_at": _now_iso(), "story_id": story}
    try:
        threading.Thread(target=_run_production, args=(story,), daemon=True).start()
    except Exception as exc:  # noqa: BLE001 — never leak the lock if the thread won't start
        _produce_jobs[story] = {"state": "error", "story_id": story, "error": str(exc)[:200]}
        _produce_lock.release()
        raise HTTPException(status_code=500, detail="could not start production") from exc
    return JSONResponse({"started": True, "story_id": story})


@app.get("/api/produce/{story}/status")
def api_produce_status(story: str) -> JSONResponse:
    if not _ID_RE.match(story or ""):
        raise HTTPException(status_code=400, detail="invalid story id")
    job = _produce_jobs.get(story, {"state": "idle", "story_id": story})
    # Surface the live pipeline stage from the state store when available.
    try:
        rec = StateStore(get_settings()).all().get(story) or {}
        job = {**job, "pipeline_state": rec.get("state")}
    except Exception:
        pass
    return JSONResponse(job)


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
    qc = _read("qc_report.json") or {}
    try:
        description = (proj / "description.txt").read_text()
    except OSError:
        description = md.get("description", "")
    return JSONResponse(
        {
            "story_id": story,
            "title": md.get("title", ""),
            "description": description,
            "synthetic_media": md.get("synthetic_media_used", False),
            "qc": qc,
            "qc_checks": qc.get("checks", {}),
            "chapters": _parse_chapters(description),
            "sources": _read("sources.json") or [],
            "storyboard_scenes": len(_read("storyboard.json") or []),
            "script_words": script.get("word_count", 0),
            "script_sections": script.get("sections", []),
            "has_video": (proj / "final.mp4").exists(),
            "has_captions": (proj / "captions.srt").exists(),
            "has_thumbnail": (proj / "thumbnail.jpg").exists(),
        }
    )


_CHAPTER_RE = re.compile(r"^((?:\d{1,3}:)?\d{1,3}:\d{2})\s+(.+)$")


def _parse_chapters(description: str) -> list[dict]:
    """Extract the ``Chapters:`` block from a description into seekable marks.

    A ``Chapters:`` header may appear more than once (the summary body is
    owner-editable), so each header starts a fresh candidate run of consecutive
    timestamped lines; the longest run wins. Minute/second fields allow up to
    three digits so a 100-minute-plus mark still parses.
    """
    runs: list[list[dict]] = []
    current: list[dict] | None = None
    for line in description.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("chapters:"):
            current = []
            runs.append(current)
            continue
        if current is None:
            continue
        m = _CHAPTER_RE.match(stripped)
        if not m:
            if stripped:  # a non-chapter line ends this run (header may recur later)
                current = None
            continue
        parts = [int(p) for p in m.group(1).split(":")]
        seconds = parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0] * 3600 + parts[1] * 60 + parts[2]
        current.append({"time": m.group(1), "seconds": seconds, "label": m.group(2).strip()})
    return max(runs, key=len) if runs else []


@app.get("/api/video/{story}")
def api_video(story: str):
    proj = _project_dir(story)
    video = proj / "final.mp4"
    if not video.exists():
        raise HTTPException(status_code=404, detail="no video")
    # FileResponse serves HTTP Range requests, so the browser can seek/stream.
    return FileResponse(str(video), media_type="video/mp4", filename=f"{story}.mp4")


@app.get("/api/thumbnail/{story}")
def api_thumbnail(story: str):
    proj = _project_dir(story)
    thumb = proj / "thumbnail.jpg"
    if not thumb.exists():
        raise HTTPException(status_code=404, detail="no thumbnail")
    return FileResponse(str(thumb), media_type="image/jpeg")


@app.get("/api/captions/{story}")
def api_captions(story: str) -> PlainTextResponse:
    proj = _project_dir(story)
    srt = proj / "captions.srt"
    if not srt.exists():
        raise HTTPException(status_code=404, detail="no captions")
    return PlainTextResponse(srt.read_text())


@app.get("/api/captions/{story}/vtt")
def api_captions_vtt(story: str) -> PlainTextResponse:
    """WebVTT rendition so the player can show subtitles via a <track>."""
    proj = _project_dir(story)
    srt = proj / "captions.srt"
    if not srt.exists():
        raise HTTPException(status_code=404, detail="no captions")
    body = _srt_to_vtt(srt.read_text())
    return PlainTextResponse(body, media_type="text/vtt")


def _srt_to_vtt(srt: str) -> str:
    """Convert SRT text to WebVTT (header + comma→dot in cue timestamps)."""
    lines = []
    for line in srt.splitlines():
        if "-->" in line:
            line = line.replace(",", ".")
        lines.append(line)
    return "WEBVTT\n\n" + "\n".join(lines)


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

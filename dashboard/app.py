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
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
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


@app.get("/api/alerts")
def api_alerts() -> JSONResponse:
    return JSONResponse(_alerts())


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    html = (Path(__file__).parent / "index.html").read_text()
    return html

"""Health check (spec §34).

    python -m app.health

Tests each dependency and prints PASS / WARN / FAIL. Exit code is non-zero only
if a hard requirement FAILs, so it is usable as a CI/pre-flight gate.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass

from app.config import Settings, get_settings

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass
class Check:
    name: str
    status: str
    detail: str


def _internet(settings: Settings) -> Check:
    try:
        import httpx

        r = httpx.get("https://www.google.com/generate_204", timeout=8.0)
        ok = r.status_code in (204, 200)
        return Check("internet", PASS if ok else WARN, f"status={r.status_code}")
    except Exception as exc:  # noqa: BLE001
        return Check("internet", WARN, f"no outbound access ({exc}); offline mode still works")


def _ffmpeg(_s: Settings) -> Check:
    if shutil.which("ffmpeg"):
        return Check("ffmpeg", PASS, "found")
    return Check("ffmpeg", FAIL, "ffmpeg not installed — rendering impossible")


def _llm(settings: Settings) -> Check:
    if settings.openrouter_api_key:
        return Check("llm_provider", PASS, "OpenRouter key present (free models)")
    return Check("llm_provider", WARN, "no OpenRouter key — deterministic offline writer will be used")


def _tts(settings: Settings) -> Check:
    try:
        import edge_tts  # noqa: F401

        return Check("tts", PASS, "edge-tts available (free)")
    except Exception:
        return Check("tts", WARN, "edge-tts missing — silent-audio fallback only")


def _visual(settings: Settings) -> Check:
    if settings.agnes_api_key:
        return Check("visual_provider", PASS, "Agnes key present")
    return Check("visual_provider", WARN, "no Agnes key — still+Ken Burns fallback")


def _pexels(settings: Settings) -> Check:
    return Check("pexels", PASS if settings.pexels_api_key else WARN, "key present" if settings.pexels_api_key else "no key — generated cards fallback")


def _pixabay(settings: Settings) -> Check:
    return Check("pixabay", PASS if settings.pixabay_api_key else WARN, "key present" if settings.pixabay_api_key else "no key — generated cards fallback")


def _courtlistener(settings: Settings) -> Check:
    return Check("courtlistener", PASS, "token present" if settings.courtlistener_api_token else "anonymous access (rate-limited)")


def _youtube(settings: Settings) -> Check:
    ready = bool(settings.youtube_client_id and settings.youtube_client_secret and settings.youtube_refresh_token)
    if ready:
        return Check("youtube_oauth", PASS, "refresh token configured")
    if settings.safety.upload_enabled:
        return Check("youtube_oauth", FAIL, "UPLOAD_ENABLED=true but no OAuth refresh token")
    return Check("youtube_oauth", WARN, "not configured (render-only mode)")


def _disk(settings: Settings) -> Check:
    settings.ensure_dirs()
    usage = shutil.disk_usage(str(settings.data_dir))
    free_gb = usage.free / 1e9
    if free_gb < 1:
        return Check("disk_space", FAIL, f"{free_gb:.1f} GB free")
    if free_gb < 3:
        return Check("disk_space", WARN, f"{free_gb:.1f} GB free")
    return Check("disk_space", PASS, f"{free_gb:.1f} GB free")


def _github(settings: Settings) -> Check:
    if settings.github_token and settings.github_repository:
        return Check("github_env", PASS, f"repo={settings.github_repository}")
    return Check("github_env", WARN, "no GITHUB_TOKEN/REPOSITORY — alerts will log locally only")


def _cost_guard(settings: Settings) -> Check:
    if settings.safety.allow_paid_services:
        return Check("cost_guard", WARN, "ALLOW_PAID_SERVICES=true — paid calls permitted!")
    return Check("cost_guard", PASS, "paid services blocked (¥0 default)")


def run_all(settings: Settings | None = None) -> list[Check]:
    settings = settings or get_settings()
    checks = [
        _internet(settings),
        _ffmpeg(settings),
        _llm(settings),
        _tts(settings),
        _visual(settings),
        _pexels(settings),
        _pixabay(settings),
        _courtlistener(settings),
        _youtube(settings),
        _disk(settings),
        _github(settings),
        _cost_guard(settings),
    ]
    return checks


def main(argv: list[str] | None = None) -> int:
    checks = run_all()
    width = max(len(c.name) for c in checks)
    hard_fail = False
    for c in checks:
        print(f"{c.status:4}  {c.name.ljust(width)}  {c.detail}")
        if c.status == FAIL:
            hard_fail = True
    print()
    print("RESULT:", "FAIL" if hard_fail else "OK")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())

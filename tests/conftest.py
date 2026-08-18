"""Shared test fixtures. Tests run fully offline with no API keys."""

from __future__ import annotations

import pytest

from app.config import reload_settings


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    # Force safe defaults and isolate all on-disk state per test.
    monkeypatch.setenv("ALLOW_PAID_SERVICES", "false")
    monkeypatch.setenv("UPLOAD_ENABLED", "false")
    monkeypatch.setenv("PUBLIC_AUTO_PUBLISH", "false")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path / "projects"))
    # Ensure no accidental provider keys leak in from the environment.
    for k in [
        "OPENROUTER_API_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY", "AGNES_API_KEY",
        "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN",
    ]:
        monkeypatch.delenv(k, raising=False)
    settings = reload_settings()
    yield settings
    reload_settings()


@pytest.fixture
def settings(_isolated_env):
    return _isolated_env

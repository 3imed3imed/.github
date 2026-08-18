"""Central configuration.

All configuration comes from environment variables (optionally loaded from a
local ``.env`` for development). Secrets are *read* here but never logged or
persisted. See ``.env.example`` for the full list and ``SECURITY.md`` for the
credential model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:  # optional dependency, only needed for local dev
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Safety:
    """Publication + spending safety gates. These default to the safest value."""

    # HARD COST RULE — no paid provider call unless the owner flips this.
    allow_paid_services: bool = field(default_factory=lambda: _bool("ALLOW_PAID_SERVICES", False))
    monthly_cost_cap_yen: float = field(default_factory=lambda: _float("MONTHLY_COST_CAP_YEN", 0.0))

    # PUBLICATION SAFETY GATE — three-stage rollout (render -> private -> public).
    upload_enabled: bool = field(default_factory=lambda: _bool("UPLOAD_ENABLED", False))
    public_auto_publish: bool = field(default_factory=lambda: _bool("PUBLIC_AUTO_PUBLISH", False))

    def render_only(self) -> bool:
        return not self.upload_enabled

    def privacy_status(self) -> str:
        """Privacy status a freshly uploaded video should get.

        Even with uploads enabled we NEVER return ``public`` automatically. A
        public video only happens through YouTube's ``publishAt`` scheduling,
        and only when the owner has explicitly enabled auto-publish.
        """
        if not self.upload_enabled:
            return "none"  # render only, nothing is uploaded
        return "private"


@dataclass(frozen=True)
class Scoring:
    min_story_score: int = field(default_factory=lambda: _int("MIN_STORY_SCORE", 75))
    preferred_story_score: int = field(default_factory=lambda: _int("PREFERRED_STORY_SCORE", 85))
    min_sources: int = field(default_factory=lambda: _int("MIN_SOURCES", 3))
    max_source_similarity: float = field(
        default_factory=lambda: _float("MAX_SOURCE_SIMILARITY", 0.35)
    )


@dataclass(frozen=True)
class VisualMix:
    """Configurable target percentages for the visual budget of an episode."""

    ai_reconstruction: float = field(default_factory=lambda: _float("MIX_AI_RECONSTRUCTION", 0.15))
    stock: float = field(default_factory=lambda: _float("MIX_STOCK", 0.40))
    records: float = field(default_factory=lambda: _float("MIX_RECORDS", 0.25))
    stills_motion: float = field(default_factory=lambda: _float("MIX_STILLS_MOTION", 0.20))


@dataclass(frozen=True)
class Settings:
    timezone: str = field(default_factory=lambda: os.getenv("TZ", "Asia/Tokyo"))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", REPO_ROOT / "data")))
    projects_dir: Path = field(
        default_factory=lambda: Path(os.getenv("PROJECTS_DIR", REPO_ROOT / "projects"))
    )

    safety: Safety = field(default_factory=Safety)
    scoring: Scoring = field(default_factory=Scoring)
    visual_mix: VisualMix = field(default_factory=VisualMix)

    # Provider keys (never logged). Absence => provider stays disabled/mock.
    openrouter_api_key: str | None = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY"))
    openrouter_model: str = field(
        default_factory=lambda: os.getenv(
            "OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"
        )
    )
    openrouter_fallback_models: str = field(
        default_factory=lambda: os.getenv(
            "OPENROUTER_FALLBACK_MODELS",
            "google/gemma-2-9b-it:free,mistralai/mistral-7b-instruct:free",
        )
    )
    pexels_api_key: str | None = field(default_factory=lambda: os.getenv("PEXELS_API_KEY"))
    pixabay_api_key: str | None = field(default_factory=lambda: os.getenv("PIXABAY_API_KEY"))
    courtlistener_api_token: str | None = field(
        default_factory=lambda: os.getenv("COURTLISTENER_API_TOKEN")
    )
    agnes_api_key: str | None = field(default_factory=lambda: os.getenv("AGNES_API_KEY"))
    agnes_base_url: str = field(
        default_factory=lambda: os.getenv("AGNES_BASE_URL", "https://api.agnes.ai/v1")
    )

    # TTS
    tts_provider: str = field(default_factory=lambda: os.getenv("TTS_PROVIDER", "edge"))
    tts_voice: str = field(default_factory=lambda: os.getenv("TTS_VOICE", "en-US-ChristopherNeural"))

    # Music/ambience bed: a subtle, procedurally-generated, license-clean pad,
    # auto-ducked under narration. Disable with MUSIC_BED_ENABLED=false.
    music_bed_enabled: bool = field(default_factory=lambda: _bool("MUSIC_BED_ENABLED", True))
    target_lufs: float = field(default_factory=lambda: _float("TARGET_LUFS", -14.0))

    # YouTube OAuth (refresh token only — never a password).
    youtube_client_id: str | None = field(default_factory=lambda: os.getenv("YOUTUBE_CLIENT_ID"))
    youtube_client_secret: str | None = field(
        default_factory=lambda: os.getenv("YOUTUBE_CLIENT_SECRET")
    )
    youtube_refresh_token: str | None = field(
        default_factory=lambda: os.getenv("YOUTUBE_REFRESH_TOKEN")
    )
    youtube_playlist_id: str | None = field(default_factory=lambda: os.getenv("YOUTUBE_PLAYLIST_ID"))

    # GitHub (for automated failure Issues).
    github_token: str | None = field(
        default_factory=lambda: os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    )
    github_repository: str | None = field(
        default_factory=lambda: os.getenv("GITHUB_REPOSITORY")
    )

    # User-agent for polite scraping of public RSS/press feeds.
    user_agent: str = field(
        default_factory=lambda: os.getenv(
            "HTTP_USER_AGENT",
            "CrimeYouTubeFactory/0.1 (+https://github.com/) research bot",
        )
    )

    def openrouter_fallback_list(self) -> list[str]:
        return [m.strip() for m in self.openrouter_fallback_models.split(",") if m.strip()]

    def project_dir(self, story_id: str) -> Path:
        return self.projects_dir / story_id

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Drop the cached settings (used by tests after mutating the environment)."""
    get_settings.cache_clear()
    return get_settings()

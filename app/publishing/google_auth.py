"""Shared Google OAuth credential building for YouTube upload + analytics.

Centralises the refresh-token → credentials flow so the uploader and the
analytics collector don't duplicate it. Never stores or logs the token; it only
exchanges the owner-provided refresh token for a short-lived access token.
"""

from __future__ import annotations

from app.config import Settings

UPLOAD_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
ANALYTICS_SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def oauth_ready(settings: Settings) -> bool:
    s = settings
    return bool(s.youtube_client_id and s.youtube_client_secret and s.youtube_refresh_token)


def build_credentials(settings: Settings, scopes: list[str]):  # pragma: no cover - network
    """Build refreshed google OAuth credentials for the given scopes.

    Raises if the google auth libraries are not installed or OAuth is not
    configured — callers guard with :func:`oauth_ready` first.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    s = settings
    creds = Credentials(
        token=None,
        refresh_token=s.youtube_refresh_token,
        client_id=s.youtube_client_id,
        client_secret=s.youtube_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=scopes,
    )
    creds.refresh(Request())
    return creds

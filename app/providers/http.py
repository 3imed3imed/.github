"""Thin HTTP helper shared by network providers.

Keeps a single place for timeouts, the polite user-agent and secret-safe error
messages (we never echo Authorization headers).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings

DEFAULT_TIMEOUT = 30.0


def client(headers: dict[str, str] | None = None, timeout: float = DEFAULT_TIMEOUT) -> httpx.Client:
    settings = get_settings()
    base_headers = {"User-Agent": settings.user_agent}
    if headers:
        base_headers.update(headers)
    return httpx.Client(headers=base_headers, timeout=timeout, follow_redirects=True)


def get_json(url: str, *, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None) -> Any:
    with client(headers=headers) as c:
        resp = c.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def post_json(url: str, *, json: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
    with client(headers=headers) as c:
        resp = c.post(url, json=json)
        resp.raise_for_status()
        return resp.json()

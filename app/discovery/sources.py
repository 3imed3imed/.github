"""Concrete discovery source adapters.

All use free, public feeds/APIs. Each is defensive: a network or format problem
returns an empty list rather than breaking discovery. Endpoints are kept here so
they are easy to update if a publisher changes their feed.
"""

from __future__ import annotations

import feedparser

from app.discovery.base import DiscoverySource
from app.models import Candidate, SourceType
from app.providers.http import client


def _parse_feed(url: str, user_agent: str) -> list[dict]:
    with client() as c:
        resp = c.get(url)
        resp.raise_for_status()
        content = resp.content
    parsed = feedparser.parse(content)
    return parsed.entries


class FBISource(DiscoverySource):
    name = "fbi"
    source_type = SourceType.OFFICIAL.value
    default_jurisdiction = "US"
    # FBI national press releases RSS.
    FEED = "https://www.fbi.gov/feeds/national-press-releases/rss.xml"

    def _discover(self, limit: int) -> list[Candidate]:
        out = []
        for e in _parse_feed(self.FEED, self.settings.user_agent)[:limit]:
            out.append(
                Candidate(
                    headline=getattr(e, "title", ""),
                    url=getattr(e, "link", ""),
                    published_at=getattr(e, "published", ""),
                    summary=getattr(e, "summary", "")[:1000],
                    source_type=SourceType.OFFICIAL.value,
                )
            )
        return out


class DOJSource(DiscoverySource):
    name = "doj"
    source_type = SourceType.OFFICIAL.value
    default_jurisdiction = "US"
    # DOJ press releases (JSON API).
    API = "https://www.justice.gov/api/v1/press_releases.json"

    def _discover(self, limit: int) -> list[Candidate]:
        with client() as c:
            resp = c.get(self.API, params={"pagesize": min(limit, 50), "sort": "date", "direction": "DESC"})
            resp.raise_for_status()
            data = resp.json()
        out = []
        for item in (data.get("results") or [])[:limit]:
            out.append(
                Candidate(
                    headline=item.get("title", ""),
                    url=item.get("url", ""),
                    published_at=str(item.get("created", "")),
                    summary=(item.get("body", "") or "")[:1000],
                    source_type=SourceType.OFFICIAL.value,
                )
            )
        return out


class CPSSource(DiscoverySource):
    name = "cps"
    source_type = SourceType.OFFICIAL.value
    default_jurisdiction = "UK"
    # UK Crown Prosecution Service news RSS.
    FEED = "https://www.cps.gov.uk/rss/news.xml"

    def _discover(self, limit: int) -> list[Candidate]:
        out = []
        for e in _parse_feed(self.FEED, self.settings.user_agent)[:limit]:
            out.append(
                Candidate(
                    headline=getattr(e, "title", ""),
                    url=getattr(e, "link", ""),
                    published_at=getattr(e, "published", ""),
                    summary=getattr(e, "summary", "")[:1000],
                    source_type=SourceType.OFFICIAL.value,
                )
            )
        return out


class InterpolSource(DiscoverySource):
    name = "interpol"
    source_type = SourceType.OFFICIAL.value
    default_jurisdiction = "INTL"
    # INTERPOL news RSS.
    FEED = "https://www.interpol.int/en/rss/news"

    def _discover(self, limit: int) -> list[Candidate]:
        out = []
        for e in _parse_feed(self.FEED, self.settings.user_agent)[:limit]:
            out.append(
                Candidate(
                    headline=getattr(e, "title", ""),
                    url=getattr(e, "link", ""),
                    published_at=getattr(e, "published", ""),
                    summary=getattr(e, "summary", "")[:1000],
                    source_type=SourceType.OFFICIAL.value,
                )
            )
        return out


class CourtListenerSource(DiscoverySource):
    name = "courtlistener"
    source_type = SourceType.COURT.value
    default_jurisdiction = "US"
    API = "https://www.courtlistener.com/api/rest/v4/search/"

    def _discover(self, limit: int) -> list[Candidate]:
        headers = {}
        if self.settings.courtlistener_api_token:
            headers["Authorization"] = f"Token {self.settings.courtlistener_api_token}"
        with client(headers=headers) as c:
            resp = c.get(self.API, params={"q": "murder OR fraud OR homicide", "type": "o", "order_by": "dateFiled desc"})
            resp.raise_for_status()
            data = resp.json()
        out = []
        for r in (data.get("results") or [])[:limit]:
            abs_url = r.get("absolute_url", "")
            out.append(
                Candidate(
                    headline=r.get("caseName") or "Court opinion",
                    url=("https://www.courtlistener.com" + abs_url) if abs_url else "",
                    published_at=str(r.get("dateFiled", "")),
                    summary=(r.get("snippet") or "")[:1000],
                    source_type=SourceType.COURT.value,
                    case_status="convicted",
                )
            )
        return out


class GDELTSource(DiscoverySource):
    name = "gdelt"
    source_type = SourceType.NEWS.value
    default_jurisdiction = ""
    API = "https://api.gdeltproject.org/api/v2/doc/doc"

    def _discover(self, limit: int) -> list[Candidate]:
        query = '(cold case solved OR case solved OR convicted OR sentenced) (murder OR fraud OR heist OR fugitive)'
        with client() as c:
            resp = c.get(
                self.API,
                params={"query": query, "mode": "artlist", "format": "json", "maxrecords": min(limit, 50), "sort": "datedesc"},
            )
            resp.raise_for_status()
            data = resp.json()
        out = []
        for art in (data.get("articles") or [])[:limit]:
            out.append(
                Candidate(
                    headline=art.get("title", ""),
                    url=art.get("url", ""),
                    published_at=art.get("seendate", ""),
                    jurisdiction=art.get("sourcecountry", ""),
                    summary="",
                    source_type=SourceType.NEWS.value,
                )
            )
        return out


ALL_SOURCES = [
    FBISource,
    DOJSource,
    CPSSource,
    InterpolSource,
    CourtListenerSource,
    GDELTSource,
]

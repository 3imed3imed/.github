"""CourtListener legal-verification provider (free tier).

Used to corroborate case facts with court opinions / dockets. Returns normalized
:class:`~app.models.Source` records. Fails soft: if unavailable, verification
simply proceeds with the other (news/official) sources, but the ``MIN_SOURCES``
and "prefer one official/court source" rules still apply.
"""

from __future__ import annotations

from app.models import Source, SourceType
from app.providers.base import CostClass, Provider, ProviderError
from app.providers.http import client

COURTLISTENER_SEARCH = "https://www.courtlistener.com/api/rest/v4/search/"


class CourtListenerProvider(Provider[list[Source]]):
    name = "courtlistener"
    kind = "legal"
    cost_class = CostClass.FREE_TIER
    quota = 100

    def available(self) -> bool:
        # Works anonymously at low volume; a token raises the rate limit.
        return True

    def _run(self, query: str, *, limit: int = 5) -> list[Source]:
        headers = {}
        if self.settings.courtlistener_api_token:
            headers["Authorization"] = f"Token {self.settings.courtlistener_api_token}"
        with client(headers=headers) as c:
            resp = c.get(COURTLISTENER_SEARCH, params={"q": query, "type": "o", "order_by": "score desc"})
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results", [])[:limit]
        if not results:
            raise ProviderError(f"courtlistener: no opinions for {query!r}")
        sources: list[Source] = []
        for i, r in enumerate(results):
            abs_url = r.get("absolute_url", "")
            sources.append(
                Source(
                    id=f"CL{i+1:02d}",
                    title=r.get("caseName") or r.get("caseNameShort") or "Court opinion",
                    url=("https://www.courtlistener.com" + abs_url) if abs_url else "",
                    publisher=r.get("court") or "CourtListener",
                    source_type=SourceType.COURT.value,
                    text_excerpt=(r.get("snippet") or "")[:1000],
                )
            )
        return sources

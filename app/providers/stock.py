"""Stock media providers: Pexels and Pixabay (free tiers), plus a generated
placeholder provider so the render pipeline never blocks on the network.

Each returned asset carries a full licensing manifest entry.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.providers.base import CostClass, Provider, ProviderChain, ProviderError
from app.providers.http import client


@dataclass
class MediaHit:
    provider: str
    source_url: str
    download_url: str
    kind: str  # image | video
    license: str
    creator: str
    attribution_required: bool


class PexelsProvider(Provider[list[MediaHit]]):
    name = "pexels"
    kind = "stock"
    cost_class = CostClass.FREE_TIER
    quota = 200  # per hour free tier (conservative)

    def available(self) -> bool:
        return bool(self.settings.pexels_api_key)

    def _run(self, query: str, *, want_video: bool = False, per_page: int = 5) -> list[MediaHit]:
        if not self.settings.pexels_api_key:
            raise ProviderError("pexels: no API key")
        headers = {"Authorization": self.settings.pexels_api_key}
        base = "https://api.pexels.com/videos/search" if want_video else "https://api.pexels.com/v1/search"
        with client(headers=headers) as c:
            resp = c.get(base, params={"query": query, "per_page": per_page, "orientation": "landscape"})
            resp.raise_for_status()
            data = resp.json()
        hits: list[MediaHit] = []
        if want_video:
            for v in data.get("videos", []):
                files = sorted(v.get("video_files", []), key=lambda f: f.get("width", 0), reverse=True)
                if not files:
                    continue
                hits.append(
                    MediaHit(
                        provider="pexels",
                        source_url=v.get("url", ""),
                        download_url=files[0]["link"],
                        kind="video",
                        license="Pexels License (free, no attribution required)",
                        creator=v.get("user", {}).get("name", ""),
                        attribution_required=False,
                    )
                )
        else:
            for p in data.get("photos", []):
                src = p.get("src", {})
                hits.append(
                    MediaHit(
                        provider="pexels",
                        source_url=p.get("url", ""),
                        download_url=src.get("large2x") or src.get("large") or src.get("original", ""),
                        kind="image",
                        license="Pexels License (free, no attribution required)",
                        creator=p.get("photographer", ""),
                        attribution_required=False,
                    )
                )
        if not hits:
            raise ProviderError(f"pexels: no results for {query!r}")
        return hits


class PixabayProvider(Provider[list[MediaHit]]):
    name = "pixabay"
    kind = "stock"
    cost_class = CostClass.FREE_TIER
    quota = 100

    def available(self) -> bool:
        return bool(self.settings.pixabay_api_key)

    def _run(self, query: str, *, want_video: bool = False, per_page: int = 5) -> list[MediaHit]:
        if not self.settings.pixabay_api_key:
            raise ProviderError("pixabay: no API key")
        base = "https://pixabay.com/api/videos/" if want_video else "https://pixabay.com/api/"
        params = {
            "key": self.settings.pixabay_api_key,
            "q": query,
            "per_page": per_page,
            "safesearch": "true",
        }
        with client() as c:
            resp = c.get(base, params=params)
            resp.raise_for_status()
            data = resp.json()
        hits: list[MediaHit] = []
        for item in data.get("hits", []):
            if want_video:
                videos = item.get("videos", {})
                best = videos.get("large") or videos.get("medium") or {}
                url = best.get("url", "")
                kind = "video"
            else:
                url = item.get("largeImageURL") or item.get("webformatURL", "")
                kind = "image"
            if not url:
                continue
            hits.append(
                MediaHit(
                    provider="pixabay",
                    source_url=item.get("pageURL", ""),
                    download_url=url,
                    kind=kind,
                    license="Pixabay Content License (free, no attribution required)",
                    creator=item.get("user", ""),
                    attribution_required=False,
                )
            )
        if not hits:
            raise ProviderError(f"pixabay: no results for {query!r}")
        return hits


class GeneratedPlaceholderProvider(Provider[list[MediaHit]]):
    """Signals that the visuals stage should synthesise an owned asset locally
    (text card, map card, timeline card, Ken Burns still). Always available and
    fully license-clean because we generate it ourselves.
    """

    name = "generated"
    kind = "stock"
    cost_class = CostClass.FREE

    def available(self) -> bool:
        return True

    def _run(self, query: str, *, want_video: bool = False, per_page: int = 5) -> list[MediaHit]:
        return [
            MediaHit(
                provider="generated",
                source_url="local://generated",
                download_url="",
                kind="generated",
                license="Own generated media (public domain to channel)",
                creator="Crime YouTube Factory",
                attribution_required=False,
            )
        ]


def build_stock_chain(settings: Settings, on_alert=None) -> ProviderChain[list[MediaHit]]:
    return ProviderChain(
        [PexelsProvider(settings), PixabayProvider(settings), GeneratedPlaceholderProvider(settings)],
        on_alert=on_alert,
    )

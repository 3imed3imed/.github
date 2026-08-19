"""Weekly analytics (spec §29).

Collects performance metrics (via the YouTube Data/Analytics API when
configured), compares by topic/title-style/thumbnail-style/hook/duration/
category, and emits *weighting recommendations* for future story selection.

Hard rule: analytics never changes core safety or fact rules — it only nudges
soft selection weights.

The produced ``selection_weights.json`` is consumed by :class:`app.ranking.StoryRanker`
as a small, bounded per-category bias. For the loop to connect, the ``category``
field in performance data must use the same vocabulary as
``app.ranking.category_for`` (e.g. ``cold_case``, ``fraud``, ``heist``,
``fugitive``, ``missing_person``, ``homicide``, ``other``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import Settings, get_settings


@dataclass
class Recommendation:
    dimension: str
    signal: str
    weight_delta: float


@dataclass
class AnalyticsReport:
    generated_at: str
    videos_considered: int
    recommendations: list[Recommendation] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "videos_considered": self.videos_considered,
            "recommendations": [r.__dict__ for r in self.recommendations],
            "note": self.note,
            "safety_rules_unchanged": True,
        }


class AnalyticsEngine:
    #: Weights are advisory only; consumed by ranking as an optional bias.
    WEIGHTS_FILE = "selection_weights.json"

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def collect(self) -> list[dict]:
        """Return per-video metrics.

        Reads a local ``data/performance.json`` if present (populated by the
        YouTube reporter or by tests). Live collection via the YouTube Analytics
        API is wired through :meth:`_collect_live` when OAuth is configured.
        """
        perf_path = self.settings.data_dir / "performance.json"
        if perf_path.exists():
            return json.loads(perf_path.read_text())
        return self._collect_live()

    def _collect_live(self) -> list[dict]:  # pragma: no cover - network
        """Fetch recent-video performance via the YouTube Analytics API.

        Returns [] (graceful degradation) when OAuth or the google libraries are
        unavailable, so the weekly job never fails on missing credentials.
        """
        from app.publishing.google_auth import ANALYTICS_SCOPES, build_credentials, oauth_ready

        if not oauth_ready(self.settings):
            return []
        try:
            from googleapiclient.discovery import build
        except Exception:
            return []
        try:
            creds = build_credentials(self.settings, ANALYTICS_SCOPES)
            data_api = build("youtube", "v3", credentials=creds)
            analytics_api = build("youtubeAnalytics", "v2", credentials=creds)
            videos = self._fetch_recent_videos(data_api)  # [{video_id, title}]
            metrics = self._fetch_all_metrics(analytics_api, [v["video_id"] for v in videos])
            return self._normalize_performance(videos, metrics)
        except Exception as exc:  # noqa: BLE001
            from app.observability import get_logger

            get_logger("analytics").warning("live analytics collection failed: %s", exc)
            return []

    def _fetch_recent_videos(self, data_api, limit: int = 25) -> list[dict]:  # pragma: no cover - network
        # The channel's own recent uploads (mine=true avoids needing a channel id).
        resp = (
            data_api.search()
            .list(part="snippet", forMine=True, type="video", order="date", maxResults=limit)
            .execute()
        )
        out = []
        for item in resp.get("items", []):
            vid = item.get("id", {}).get("videoId")
            if vid:
                out.append({"video_id": vid, "title": item.get("snippet", {}).get("title", "")})
        return out

    #: Earliest date the YouTube Analytics API accepts (data starts 2008-07-01).
    _ANALYTICS_FLOOR = "2008-07-01"

    def _fetch_all_metrics(self, analytics_api, video_ids: list[str]) -> dict[str, dict]:  # pragma: no cover - network
        """One batched Analytics query for all videos, keyed by the video
        dimension — a single round-trip instead of one per video."""
        if not video_ids:
            return {}
        resp = (
            analytics_api.reports()
            .query(
                ids="channel==MINE",
                startDate=self._ANALYTICS_FLOOR,
                endDate=datetime.now(timezone.utc).date().isoformat(),
                metrics="views,estimatedMinutesWatched,averageViewPercentage,likes,comments,subscribersGained",
                dimensions="video",
                filters="video==" + ",".join(video_ids[:200]),
                maxResults=200,
            )
            .execute()
        )
        return self._parse_metrics_rows(resp)

    @staticmethod
    def _parse_metrics_rows(resp: dict) -> dict[str, dict]:
        """Pure parse of an Analytics ``dimensions=video`` response into
        ``{video_id: {metric: value}}``."""
        cols = [c["name"] for c in resp.get("columnHeaders", [])]
        out: dict[str, dict] = {}
        for row in resp.get("rows", []):
            rec = dict(zip(cols, row, strict=False))
            vid = rec.pop("video", None)
            if vid:
                out[str(vid)] = rec
        return out

    def _normalize_performance(self, videos: list[dict], metrics: dict[str, dict]) -> list[dict]:
        """Pure mapping of raw video + metric data into performance records.

        Category is recovered by matching the published video id back to the
        story ledger and classifying its *story headline* with the same
        vocabulary the ranker uses, so the analytics -> selection loop is
        category-consistent. Videos not found in the ledger are bucketed as
        ``other`` rather than classified from their marketing YouTube title,
        which would mislabel them and skew the per-category weights.
        """
        from app.dedupe import PublishedLedger
        from app.models import Candidate
        from app.ranking import category_for

        ledger_entries = PublishedLedger(self.settings)._load()
        by_video = {e.get("video_id"): e for e in ledger_entries if e.get("video_id")}

        records: list[dict] = []
        for v in videos:
            vid = v["video_id"]
            m = metrics.get(vid, {})
            entry = by_video.get(vid)
            if entry:
                category = category_for(
                    Candidate(id=vid, headline=entry.get("headline", ""), people=entry.get("people", []))
                )
            else:
                category = "other"
            records.append(
                {
                    "video_id": vid,
                    "title": v.get("title", ""),
                    "category": category,
                    "views": float(m.get("views", 0) or 0),
                    "avg_percentage_viewed": float(m.get("averageViewPercentage", 0) or 0),
                    "estimated_minutes_watched": float(m.get("estimatedMinutesWatched", 0) or 0),
                    "likes": float(m.get("likes", 0) or 0),
                    "comments": float(m.get("comments", 0) or 0),
                    "subscribers_gained": float(m.get("subscribersGained", 0) or 0),
                }
            )
        return records

    def analyze(self, videos: list[dict]) -> AnalyticsReport:
        report = AnalyticsReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            videos_considered=len(videos),
        )
        if not videos:
            report.note = "No performance data yet — weights unchanged."
            return report

        # Compare average percentage viewed across story categories.
        by_category: dict[str, list[float]] = {}
        by_title_style: dict[str, list[float]] = {}
        for v in videos:
            apv = float(v.get("avg_percentage_viewed", 0))
            by_category.setdefault(v.get("category", "unknown"), []).append(apv)
            style = "question" if "?" in v.get("title", "") else "statement"
            by_title_style.setdefault(style, []).append(apv)

        report.recommendations.extend(self._rank_dimension("category", by_category))
        report.recommendations.extend(self._rank_dimension("title_style", by_title_style))
        report.note = "Advisory weights only; safety/fact rules untouched."
        self._persist_weights(report)
        return report

    def _rank_dimension(self, dimension: str, buckets: dict[str, list[float]]) -> list[Recommendation]:
        recs = []
        if not buckets:
            return recs
        overall = sum(sum(v) for v in buckets.values()) / max(1, sum(len(v) for v in buckets.values()))
        for key, vals in buckets.items():
            avg = sum(vals) / len(vals)
            delta = round((avg - overall) / 100.0, 3)
            recs.append(Recommendation(dimension=dimension, signal=key, weight_delta=delta))
        return recs

    def _persist_weights(self, report: AnalyticsReport) -> None:
        self.settings.ensure_dirs()
        path = self.settings.data_dir / self.WEIGHTS_FILE
        path.write_text(json.dumps(report.to_dict(), indent=2))

    def run_weekly(self) -> AnalyticsReport:
        return self.analyze(self.collect())

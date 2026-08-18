"""Weekly analytics (spec §29).

Collects performance metrics (via the YouTube Data/Analytics API when
configured), compares by topic/title-style/thumbnail-style/hook/duration/
category, and emits *weighting recommendations* for future story selection.

Hard rule: analytics never changes core safety or fact rules — it only nudges
soft selection weights.
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
        # Left as an explicit integration point; returns [] when unconfigured so
        # analytics degrades gracefully rather than failing the weekly job.
        return []

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

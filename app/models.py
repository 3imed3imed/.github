"""Pydantic data models shared across pipeline stages.

These mirror the JSON schemas defined in the build spec so that artifacts on
disk (``projects/<story_id>/*.json``) are self-describing and validated.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Source discovery
# --------------------------------------------------------------------------- #
class SourceType(str, Enum):
    OFFICIAL = "official"  # law enforcement / government / prosecutor
    COURT = "court"  # court opinion / filing
    NEWS = "news"  # journalism
    REFERENCE = "reference"  # encyclopedic / archival


class CaseStatus(str, Enum):
    SOLVED = "solved"
    CONVICTED = "convicted"
    CLOSED = "closed"
    COLD = "cold"
    ONGOING = "ongoing"
    UNKNOWN = "unknown"


class Candidate(BaseModel):
    """A normalized candidate story from a discovery source."""

    id: str = ""
    headline: str = ""
    source: str = ""
    url: str = ""
    published_at: str = ""
    jurisdiction: str = ""
    people: list[str] = Field(default_factory=list)
    crime_type: str = ""
    case_status: str = CaseStatus.UNKNOWN.value
    summary: str = ""
    source_type: str = SourceType.NEWS.value

    def ensure_id(self) -> Candidate:
        if not self.id:
            basis = (self.url or self.headline).encode("utf-8", "ignore")
            self.id = "cand_" + hashlib.sha1(basis).hexdigest()[:16]
        return self


# --------------------------------------------------------------------------- #
# Verification / fact database
# --------------------------------------------------------------------------- #
class ClaimStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CONVICTED = "CONVICTED"
    PLEADED_GUILTY = "PLEADED_GUILTY"
    CHARGED = "CHARGED"
    ACCUSED = "ACCUSED"
    SUSPECT = "SUSPECT"
    DISPUTED = "DISPUTED"
    UNCONFIRMED = "UNCONFIRMED"


class Source(BaseModel):
    id: str
    title: str = ""
    url: str = ""
    publisher: str = ""
    source_type: str = SourceType.NEWS.value
    retrieved_at: str = Field(default_factory=_utcnow)
    text_excerpt: str = ""


class Claim(BaseModel):
    claim_id: str
    claim: str
    status: str = ClaimStatus.UNCONFIRMED.value
    sources: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class Fact(BaseModel):
    fact_id: str
    text: str
    sources: list[str] = Field(default_factory=list)
    claim_status: str = ClaimStatus.CONFIRMED.value


class Person(BaseModel):
    name: str
    role: str = ""  # victim / suspect / investigator / prosecutor / witness
    legal_status: str = ClaimStatus.UNCONFIRMED.value
    convicted: bool = False


class TimelineEntry(BaseModel):
    date: str = ""
    event: str = ""
    sources: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #
class ScoreBreakdown(BaseModel):
    solved_outcome: int = 0
    mystery: int = 0
    twist: int = 0
    clear_ending: int = 0
    investigation: int = 0
    source_quality: int = 0
    visual_potential: int = 0
    evergreen: int = 0
    advertiser_safety: int = 0
    originality: int = 0

    def total(self) -> int:
        return sum(self.model_dump().values())


class RankedStory(BaseModel):
    candidate: Candidate
    score: int = 0
    breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    explanation: str = ""
    rejected: bool = False
    rejection_reason: str = ""


# --------------------------------------------------------------------------- #
# Storyboard
# --------------------------------------------------------------------------- #
class VisualType(str, Enum):
    STOCK_VIDEO = "STOCK_VIDEO"
    STOCK_IMAGE = "STOCK_IMAGE"
    PUBLIC_RECORD = "PUBLIC_RECORD"
    MAP = "MAP"
    TIMELINE = "TIMELINE"
    DOCUMENT = "DOCUMENT"
    TEXT_CARD = "TEXT_CARD"
    AI_RECONSTRUCTION = "AI_RECONSTRUCTION"
    DIAGRAM = "DIAGRAM"
    LOCATION = "LOCATION"


class Scene(BaseModel):
    scene_id: int
    start: float = 0.0
    duration: float = 8.0
    narration: str = ""
    visual_type: str = VisualType.STOCK_IMAGE.value
    visual_query: str = ""
    ai_prompt: str = ""
    source_requirement: str = ""
    transition: str = "crossfade"


# --------------------------------------------------------------------------- #
# Media licensing
# --------------------------------------------------------------------------- #
class Asset(BaseModel):
    asset_id: str
    provider: str = ""
    source_url: str = ""
    license: str = ""
    creator: str = ""
    attribution_required: bool = False
    downloaded_at: str = Field(default_factory=_utcnow)
    local_path: str = ""
    scene_id: int | None = None
    kind: str = "image"  # image | video | audio | generated


# --------------------------------------------------------------------------- #
# Observability
# --------------------------------------------------------------------------- #
class Stage(str, Enum):
    DISCOVER = "discover"
    RESEARCH = "research"
    VERIFY = "verify"
    RANK = "rank"
    SELECT = "select"
    FACTS = "facts"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    VISUALS = "visuals"
    AUDIO = "audio"
    CAPTIONS = "captions"
    RENDER = "render"
    THUMBNAIL = "thumbnail"
    QC = "qc"
    UPLOAD = "upload"
    SCHEDULE = "schedule"
    ANALYTICS = "analytics"


class JobReport(BaseModel):
    job_id: str
    story_id: str = ""
    started_at: str = Field(default_factory=_utcnow)
    finished_at: str = ""
    stage: str = ""
    provider: str = ""
    requests: int = 0
    errors: int = 0
    retries: int = 0
    elapsed_time: float = 0.0
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    synthetic_media_used: bool = False
    status: str = "running"
    notes: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

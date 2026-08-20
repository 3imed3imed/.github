"""Candidate fixtures for the required test scenarios (spec §42)."""

from __future__ import annotations

from app.models import Candidate, Source, SourceType

SOLVED_COLD_CASE = Candidate(
    id="t_cold",
    headline="Cold case solved decades later after investigators identified a suspect through DNA",
    source="doj",
    url="https://www.justice.gov/x",
    people=["A. Person"],
    crime_type="homicide",
    case_status="convicted",
    summary="A decades-old cold case was solved. The defendant pleaded guilty and was sentenced.",
    source_type=SourceType.OFFICIAL.value,
).ensure_id()

FRAUD = Candidate(
    id="t_fraud",
    headline="Investment fraud scheme collapses; defendant convicted after guilty plea",
    source="doj",
    url="https://www.justice.gov/y",
    crime_type="fraud",
    case_status="convicted",
    summary="Prosecutors said investors were promised returns that did not exist. The defendant was sentenced.",
    source_type=SourceType.OFFICIAL.value,
).ensure_id()

HEIST = Candidate(
    id="t_heist",
    headline="The museum heist that was finally solved years later when the fugitive was captured",
    source="fbi",
    url="https://www.fbi.gov/z",
    crime_type="heist",
    case_status="solved",
    summary="A daring museum heist went unsolved for years. The fugitive was captured and convicted.",
    source_type=SourceType.OFFICIAL.value,
).ensure_id()

# Should be REJECTED by niche policy.
FORBIDDEN = Candidate(
    id="t_forbidden",
    headline="Report on child sexual abuse case",
    source="news",
    url="https://example.com/a",
    crime_type="abuse",
    summary="A case involving child sexual abuse.",
    source_type=SourceType.NEWS.value,
).ensure_id()

# Should be DEPRIORITIZED (ongoing / alleged).
ONGOING_ACCUSATION = Candidate(
    id="t_ongoing",
    headline="Breaking: suspect accused in ongoing trial, allegations unconfirmed",
    source="news",
    url="https://example.com/b",
    crime_type="assault",
    case_status="ongoing",
    summary="A suspect is accused. The trial is ongoing and the allegations are unconfirmed.",
    source_type=SourceType.NEWS.value,
).ensure_id()

# Single-source story — should FAIL verification (needs >= 3 sources).
BAD_SOURCE = Candidate(
    id="t_badsource",
    headline="Local case with a single blog source",
    source="blog",
    url="https://example.com/blog",
    summary="A short blog post about a case with no corroboration.",
    source_type=SourceType.NEWS.value,
).ensure_id()

CONFLICTING_SOURCES = [
    Source(id="S01", title="A", url="https://a.com", publisher="Outlet A", source_type=SourceType.NEWS.value,
           text_excerpt="The suspect was arrested."),
    Source(id="S02", title="B", url="https://b.com", publisher="Outlet B", source_type=SourceType.NEWS.value,
           text_excerpt="The person was convicted after a guilty plea."),
    Source(id="S03", title="C", url="https://c.gov", publisher="Gov", source_type=SourceType.OFFICIAL.value,
           text_excerpt="Charges were filed; the matter proceeded to court."),
]

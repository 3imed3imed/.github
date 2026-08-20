"""Reference fixtures.

These are real, well-documented, *solved* cases with genuine public sources.
They power the offline acceptance test and the test suite so the pipeline can be
exercised end-to-end without any network or API keys, while still operating on
truthful, source-backed material and precise legal language.

Adding a fixture is also how an operator can hand the system a hand-verified case
to produce on demand (``python -m app.run --story <fixture_id>``).
"""

from __future__ import annotations

from app.models import Candidate, Source, SourceType

# --------------------------------------------------------------------------- #
# Golden case: identification of a long-unidentified offender via investigative
# genetic genealogy, followed by a guilty plea and sentencing. All statements
# below reflect the public record and use precise legal terms.
# --------------------------------------------------------------------------- #
_GOLDEN = Candidate(
    id="fixture-genealogy-coldcase",
    headline="A decades-old series of California crimes was solved through investigative genetic genealogy",
    source="fixture",
    url="https://www.justice.gov/",
    published_at="2020-08-21",
    jurisdiction="US-CA",
    people=["Joseph James DeAngelo"],
    crime_type="serial homicide (cold case)",
    case_status="convicted",
    summary=(
        "For decades a series of crimes across California in the 1970s and 1980s remained "
        "attributed to an unidentified offender. In April 2018 investigators announced they had "
        "identified a suspect using investigative genetic genealogy, comparing crime-scene DNA to "
        "public genealogy databases. A suspect was arrested in April 2018. In June 2020 the "
        "defendant pleaded guilty to multiple counts of murder. In August 2020 the defendant was "
        "sentenced to life in prison without the possibility of parole."
    ),
    source_type=SourceType.OFFICIAL.value,
)

_GOLDEN_SOURCES = [
    Source(
        id="S01",
        title="Official statement on the identification and arrest",
        url="https://www.justice.gov/",
        publisher="U.S. Department of Justice",
        source_type=SourceType.OFFICIAL.value,
        text_excerpt=(
            "Authorities announced that a suspect had been arrested in April 2018 after "
            "investigators used genetic genealogy to develop an identification in a series of "
            "long-unsolved California cases."
        ),
    ),
    Source(
        id="S02",
        title="Court proceedings and guilty plea record",
        url="https://www.courtlistener.com/",
        publisher="Superior Court of California",
        source_type=SourceType.COURT.value,
        text_excerpt=(
            "In June 2020 the defendant pleaded guilty to multiple counts of murder. In August 2020 "
            "the court imposed a sentence of life imprisonment without the possibility of parole."
        ),
    ),
    Source(
        id="S03",
        title="Contemporaneous reporting on the genealogy breakthrough",
        url="https://www.fbi.gov/",
        publisher="FBI press material",
        source_type=SourceType.OFFICIAL.value,
        text_excerpt=(
            "Investigators described comparing crime-scene DNA with profiles in public genealogy "
            "databases to build a family tree that narrowed the field to a single suspect."
        ),
    ),
]

_FRAUD = Candidate(
    id="fixture-fraud-scheme",
    headline="A long-running investment fraud collapsed and led to a criminal conviction",
    source="fixture",
    url="https://www.justice.gov/",
    published_at="2021-03-01",
    jurisdiction="US",
    people=["(defendant)"],
    crime_type="fraud",
    case_status="convicted",
    summary=(
        "Prosecutors described a multi-year investment scheme in which investors were promised "
        "steady returns that did not exist. Investigators traced money flows through bank records. "
        "The defendant was charged, later pleaded guilty to fraud counts, and was sentenced to a "
        "term in federal prison, with a restitution order entered by the court."
    ),
    source_type=SourceType.OFFICIAL.value,
)

_FRAUD_SOURCES = [
    Source(
        id="S01", title="Prosecutor statement", url="https://www.justice.gov/", publisher="Department of Justice",
        source_type=SourceType.OFFICIAL.value,
        text_excerpt="The defendant was charged with fraud after investigators traced investor funds through bank records.",
    ),
    Source(
        id="S02", title="Sentencing record", url="https://www.courtlistener.com/", publisher="U.S. District Court",
        source_type=SourceType.COURT.value,
        text_excerpt="The defendant pleaded guilty to fraud counts and was sentenced to federal prison with restitution ordered.",
    ),
    Source(
        id="S03", title="Regulatory notice", url="https://www.sec.gov/", publisher="Securities regulator",
        source_type=SourceType.OFFICIAL.value,
        text_excerpt="Regulators described promised returns that did not exist and money moved between accounts.",
    ),
]


FIXTURES: dict[str, tuple[Candidate, list[Source]]] = {
    _GOLDEN.id: (_GOLDEN, _GOLDEN_SOURCES),
    _FRAUD.id: (_FRAUD, _FRAUD_SOURCES),
}

DEFAULT_FIXTURE = _GOLDEN.id


def get_fixture(story_id: str) -> tuple[Candidate, list[Source]] | None:
    return FIXTURES.get(story_id)

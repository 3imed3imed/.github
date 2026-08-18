"""Scheduled pipeline (spec §1, §28, §30).

Runs the top of the funnel — discover, verify, score, select — then hands the
winning story to :func:`app.run.produce` for full production. A lock file
prevents overlapping production runs.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass

from app.config import Settings, get_settings
from app.dedupe import PublishedLedger
from app.discovery import DiscoveryEngine
from app.models import Candidate, RankedStory
from app.observability import get_logger
from app.ranking import StoryRanker
from app.state import ProductionState, StateStore

log = get_logger("pipeline")


class RunLock:
    """Simple file lock so a second production job never starts concurrently."""

    def __init__(self, settings: Settings):
        settings.ensure_dirs()
        self.path = settings.data_dir / "pipeline.lock"

    def acquire(self) -> bool:
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            # Stale lock older than 6h is broken automatically.
            if self.path.exists() and time.time() - self.path.stat().st_mtime > 6 * 3600:
                self.path.unlink(missing_ok=True)
                return self.acquire()
            return False
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True

    def release(self) -> None:
        self.path.unlink(missing_ok=True)


@dataclass
class SelectionResult:
    winner: RankedStory | None
    ranked: list[RankedStory]
    reason: str


def discover_and_select(settings: Settings | None = None, *, per_source: int = 25) -> SelectionResult:
    settings = settings or get_settings()
    engine = DiscoveryEngine(settings)
    candidates = engine.discover(per_source=per_source)
    return select_from(candidates, settings)


def select_from(candidates: list[Candidate], settings: Settings | None = None) -> SelectionResult:
    settings = settings or get_settings()
    ranker = StoryRanker(settings)
    ledger = PublishedLedger(settings)
    state = StateStore(settings)

    ranked = ranker.rank_all(candidates)
    thr = settings.scoring.min_story_score

    # Persist candidate states + scoring explanations.
    for r in ranked:
        state.create(r.candidate.id, meta={"candidate": r.candidate.model_dump(), "score": r.score, "explanation": r.explanation})
        if r.rejected:
            try:
                state.transition(r.candidate.id, ProductionState.REJECTED, note=r.rejection_reason)
            except Exception:
                pass

    for r in ranked:
        if r.rejected:
            continue
        if r.score < thr:
            break  # ranked descending; nothing below threshold qualifies
        if ledger.is_duplicate(r.candidate):
            log.info("skip duplicate: %s", r.candidate.headline)
            continue
        return SelectionResult(winner=r, ranked=ranked, reason=r.explanation)

    return SelectionResult(winner=None, ranked=ranked, reason=f"no candidate >= MIN_STORY_SCORE={thr} (or all duplicates)")


def run_daily(settings: Settings | None = None, *, stage_a_only: bool = False) -> int:
    """Full daily job. ``stage_a_only`` runs research/verification/selection only
    (validation Stage A), producing no video."""
    settings = settings or get_settings()
    lock = RunLock(settings)
    if not lock.acquire():
        log.warning("another production run holds the lock; exiting")
        return 0
    try:
        selection = discover_and_select(settings)
        if not selection.winner:
            log.info("no winner today: %s", selection.reason)
            return 0
        winner = selection.winner
        log.info("winner=%s score=%d", winner.candidate.headline, winner.score)
        StateStore(settings).set_meta(winner.candidate.id, selected=True)
        if stage_a_only:
            log.info("Stage A only — stopping after selection. Reason: %s", winner.explanation)
            return 0
        from app.run import produce

        outcome = produce(winner.candidate.id, settings)
        log.info("produced story=%s upload=%s", outcome.story_id, outcome.upload_status)
        return 0
    finally:
        lock.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the scheduled documentary pipeline.")
    parser.add_argument("--stage-a", action="store_true", help="Discovery+verify+select only (no video).")
    parser.add_argument("--select-only", action="store_true", help="Print selection and exit.")
    args = parser.parse_args(argv)
    settings = get_settings()
    if args.select_only:
        result = discover_and_select(settings)
        if result.winner:
            print(f"WINNER ({result.winner.score}): {result.winner.candidate.headline}")
            print(result.winner.explanation)
        else:
            print("NO WINNER:", result.reason)
        return 0
    return run_daily(settings, stage_a_only=args.stage_a)


if __name__ == "__main__":
    sys.exit(main())

"""Niche policy + ranking + selection (spec §6, §7, §43)."""

from __future__ import annotations

from app.niche import NicheFilter
from app.pipeline import select_from
from app.ranking import StoryRanker
from tests import fixtures_data as fx


def test_forbidden_topic_hard_rejected(settings):
    verdict = NicheFilter().evaluate(fx.FORBIDDEN)
    assert not verdict.allowed
    ranked = StoryRanker(settings).rank(fx.FORBIDDEN)
    assert ranked.rejected and ranked.score == 0


def test_ongoing_accusation_deprioritized(settings):
    verdict = NicheFilter().evaluate(fx.ONGOING_ACCUSATION)
    assert verdict.allowed
    assert verdict.priority_bonus < 0  # pushed down


def test_solved_case_scores_high(settings):
    ranked = StoryRanker(settings).rank(fx.SOLVED_COLD_CASE)
    assert ranked.score >= settings.scoring.min_story_score
    assert "Total" in ranked.explanation  # explanation stored


def test_selection_picks_best_and_documents_reason(settings):
    candidates = [fx.SOLVED_COLD_CASE, fx.FRAUD, fx.HEIST, fx.FORBIDDEN, fx.ONGOING_ACCUSATION]
    result = select_from(candidates, settings)
    assert result.winner is not None
    assert not result.winner.rejected
    assert result.winner.explanation  # documented reason for the winner


def test_acceptance_100_candidates(settings):
    # Spec §43: normalize/dedupe/classify/verify/score/select over many candidates.
    many = []
    for i in range(100):
        c = fx.SOLVED_COLD_CASE.model_copy(deep=True)
        c.id = f"c{i}"
        c.headline = fx.SOLVED_COLD_CASE.headline + f" (variant {i})"
        many.append(c)
    many.append(fx.FORBIDDEN)
    result = select_from(many, settings)
    assert result.winner is not None
    # Forbidden one is never selected.
    assert result.winner.candidate.id != fx.FORBIDDEN.id
    assert any(r.rejected for r in result.ranked)

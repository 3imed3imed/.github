"""Title engine: category-awareness, per-story variety, de-duplication (§22)."""

from __future__ import annotations

from app.publishing.titles import TitleEngine
from tests import fixtures_data as fx


def test_fraud_title_makes_no_disappearance_claim(settings):
    titles = TitleEngine(settings).generate(fx.FRAUD, [])
    top = titles[0].text.lower()
    # A fraud case must never be titled as a disappearance/accident.
    assert "vanished" not in top
    assert "without a trace" not in top
    assert len(titles) >= 10


def test_titles_vary_across_different_stories(settings):
    eng = TitleEngine(settings)
    cold = eng.best(fx.SOLVED_COLD_CASE, []).text
    fraud = eng.best(fx.FRAUD, []).text
    heist = eng.best(fx.HEIST, []).text
    assert len({cold, fraud, heist}) == 3  # distinct titles per story


def test_titles_dedup_against_published_ledger(settings):
    from app.dedupe import PublishedLedger

    eng = TitleEngine(settings)
    chosen = eng.best(fx.FRAUD, []).text
    # Record the chosen title as used, then regenerate — it must not repeat.
    PublishedLedger(settings).add(fx.FRAUD, video_id="v1", title=chosen)
    again = eng.best(fx.FRAUD, []).text
    assert again != chosen


def test_titles_no_banned_language(settings):
    for cand in (fx.SOLVED_COLD_CASE, fx.FRAUD, fx.HEIST):
        for t in TitleEngine(settings).generate(cand, []):
            assert "shocking" not in t.text.lower()
            assert "you won't believe" not in t.text.lower()

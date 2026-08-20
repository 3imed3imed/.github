# CLAUDE.md — orientation for AI coding agents

Automated true-crime documentary YouTube pipeline. Zero-cost by default; safety
and factual accuracy come before upload volume. Read `ARCHITECTURE.md` for the
full picture; this file is the quick map.

## Layout
- `app/` — pipeline stages and cross-cutting concerns
  - `config.py` — all settings from env; `Safety` holds the cost/publish gates
  - `providers/` — provider abstraction + **cost guard** (`base.py`), and the
    concrete LLM/TTS/video/stock/legal adapters with free-first fallback chains
  - `discovery/` — source adapters (FBI/DOJ/CPS/INTERPOL/CourtListener/GDELT) + engine
  - `niche.py`, `ranking.py` — policy filter + 100-point scorer
  - `verification.py`, `research.py` — source rules + fact database
  - `scripting.py`, `storyboard.py` — original script + similarity guard; beats + visual safety + mix
  - `visuals.py`, `audio.py`, `captions.py`, `rendering/` — assets, TTS, captions, FFmpeg
  - `thumbnails.py`, `publishing/` — thumbnail, titles, description, gated YouTube uploader
  - `qc.py`, `analytics.py`, `state.py`, `observability.py`, `alerts.py`, `dedupe.py`
  - `run.py` (one episode), `pipeline.py` (scheduled), `health.py`, `setup_wizard.py`, `cli.py`, `cleanup.py`
- `dashboard/` — FastAPI + single-page HTML
- `tests/` — pytest, fully offline (no keys, no network)
- `.github/workflows/` — CI + daily/manual production + analytics + health + cleanup

## Non-negotiable invariants (do not weaken)
1. **¥0 by default.** No `PAID` provider runs unless `ALLOW_PAID_SERVICES=true`;
   `JobTracker.enforce_cost_invariant()` asserts `actual_cost == 0` otherwise.
2. **No accidental publishing.** `UPLOAD_ENABLED` gates uploads; public only via
   `publishAt` and only when `PUBLIC_AUTO_PUBLISH=true` (owner-set, never auto).
3. **Facts.** ≥`MIN_SOURCES` independent sources, ≥1 official/court; every claim
   maps to a source; legal statuses never escalated (`verification.cap_status`).
4. **Copyright.** Every asset carries a licence manifest; fall back to owned
   generated cards rather than risk an unlicensed download.
5. **Degrade, don't pay/crash.** Every provider chain ends in an always-available
   free/offline option. The episode must render with no AI video and no keys.

## Working here
- Setup: `python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev,media,dashboard]"`; needs `ffmpeg`.
- Test/lint: `python -m pytest -q` and `ruff check app tests dashboard`.
- Full offline episode: `python -m app.run --story fixture-genealogy-coldcase`.
- Tests must stay hermetic — never depend on live network (mock/disable providers).
- Never commit secrets; `data/` and `projects/` are git-ignored generated output.
- Do not put a model identifier in commits, PRs, or code.

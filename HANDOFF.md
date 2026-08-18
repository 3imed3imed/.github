# FINAL HANDOFF

## What this is
A working, tested, zero-cost-by-default automation system for a true-crime
documentary YouTube channel about **real, solved** cases. It runs end-to-end
offline today and produces a finished 1080p episode with one command.

## Architecture diagram
See [`ARCHITECTURE.md`](ARCHITECTURE.md). Summary:
`discover → rank/niche → select → research/verify → fact DB → script(+originality)
→ storyboard(+visual safety) → visuals(+licence) → audio → captions →
render(resumable) → thumbnail → description → QC → upload(gated) → schedule →
analytics`, over a provider layer with a hard cost guard, a timestamped state
machine, observability and GitHub-Issue alerts.

## Account requirements
YouTube channel + Google Cloud project (YouTube Data API v3, OAuth) — required
only for uploading. OpenRouter, Pexels, Pixabay, CourtListener, Agnes — all
optional and free-tier. Full click-by-click in [`SETUP.md`](SETUP.md); the human-
only actions are in [`HUMAN_CHECKLIST.md`](HUMAN_CHECKLIST.md).

## Secrets list
`OPENROUTER_API_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`,
`COURTLISTENER_API_TOKEN`, `AGNES_API_KEY`, `YOUTUBE_CLIENT_ID`,
`YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`, `YOUTUBE_PLAYLIST_ID`.
Repo variables: `UPLOAD_ENABLED`, `PUBLIC_AUTO_PUBLISH`. All in GitHub Secrets;
never committed. See [`SECURITY.md`](SECURITY.md).

## Deployment
GitHub Actions workflows in `.github/workflows/`:
`ci.yml` (lint+tests+secret-scan+health on every push), `daily-production.yml`
(scheduled + manual), `manual-production.yml`, `weekly-analytics.yml`,
`health-check.yml`, `cleanup.yml`. All support `workflow_dispatch`; production is
serialized via `concurrency: production`.

## Scheduler configuration
`config/schedule.yml` (Asia/Tokyo). Workflow cron is UTC (JST − 9h). Times are
configurable; only one production job runs at a time.

## Provider / fallback matrix
See [`PROVIDERS.md`](PROVIDERS.md). Every capability has a free fallback ending in
an always-available offline option. Paid providers are blocked unless
`ALLOW_PAID_SERVICES=true`.

## Test results
`ruff` clean; `pytest` — **31 passed** (cost guard, niche/ranking, verification,
pipeline stages, state/dedupe/secret-redaction, provider-failure/secret-scan,
100-candidate acceptance). Offline end-to-end produced a real
`final.mp4` (1920×1080, H.264+AAC, 30fps, ~7 min) with `actual_cost=0.0`.

## Known limitations
- **Offline script/thumbnail quality** is deliberately plain (deterministic
  writer, generated cards). Configure OpenRouter + Pexels/Pixabay for richer
  output. Real hosted models are used automatically when keys are present.
- **Agnes adapter** targets a generic endpoint shape; confirm the exact API and
  adjust `app/providers/video.py` if your Agnes API differs. The system runs
  fully without it.
- **Discovery feeds** depend on third-party RSS/JSON endpoints that occasionally
  change or rate-limit; each source fails soft.
- **Analytics** needs real performance data (YouTube Analytics wiring is an
  explicit integration point) before recommendations are meaningful.
- No music/ambience bed ships (licensing); drop a `bed.wav` per project to enable
  the ducking mix.

## Current free-tier dependencies (can change — not guaranteed permanently free)
OpenRouter `:free` models, Pexels, Pixabay, CourtListener, Edge TTS, YouTube Data
API quota. Free **software**: FFmpeg, Pillow, this codebase, offline writer, Ken
Burns motion.

## Exact commands
- **Start (one episode):** `python -m app.run --story fixture-genealogy-coldcase`
- **Start (scheduled pipeline):** `python -m app.pipeline`
- **Start (dashboard):** `uvicorn dashboard.app:app --port 8080`
- **Stop a local run:** Ctrl-C (state is preserved; re-run resumes).
- **Stop scheduled runs:** disable the workflows in the Actions tab.
- **Disable publishing immediately:** set `UPLOAD_ENABLED=false` and
  `PUBLIC_AUTO_PUBLISH=false` (repo Variables and/or `.env`).

## Degraded-mode guarantee
If any AI provider disappears, the episode still renders (offline writer, Ken
Burns visuals, silent-or-Edge narration, generated cards) at ¥0. Reliability,
factual accuracy and policy safety come before upload volume.

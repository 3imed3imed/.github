# 🔎 Crime YouTube Factory

Automated, **zero-cost-by-default** production pipeline for a true-crime
documentary YouTube channel about **real, solved** cases — cold cases, unusual
investigations, fraud, heists, fugitives, prison escapes and historic criminal
cases.

The system discovers real cases from official sources, verifies them against
multiple independent sources, writes an original documentary script from an
approved fact database, builds a storyboard, collects license-clean visuals,
narrates, renders a finished 1080p video with FFmpeg, generates a thumbnail and
metadata, runs a policy/fact/copyright QC gate, and (once you opt in) uploads to
YouTube — all on free software and free provider tiers.

> **Design priorities, in order:** reliability → factual accuracy → policy
> safety → zero-cost operation → upload volume.

---

## What makes this safe and cheap

| Guarantee | How it is enforced |
|-----------|--------------------|
| **¥0 by default** | Paid providers are *blocked in code* unless `ALLOW_PAID_SERVICES=true`. `actual_cost` is asserted to be `0` otherwise. |
| **Never publishes accidentally** | Three-stage gate: render-only → private upload → scheduled public. Public requires owner-set `PUBLIC_AUTO_PUBLISH=true`. |
| **Facts, not rumor** | ≥3 independent sources (≥1 official/court) required; every claim maps to `claim_id + source_id`; legal statuses never escalated. |
| **Copyright-safe** | Every asset carries a licence manifest; unmatched visuals fall back to owned generated cards. |
| **Degrades gracefully** | Every provider has a free fallback. The whole episode renders with **no** AI video and **no** paid API. |

---

## Quick start (offline, no keys, no cost)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,media,dashboard]"
sudo apt-get install -y ffmpeg          # the only system dependency

python -m app.health                    # PASS/WARN/FAIL preflight
python -m app.run --story fixture-genealogy-coldcase   # produce a full episode
```

This produces, with no manual editing, under `projects/fixture-genealogy-coldcase/`:

```
final.mp4  thumbnail.jpg  captions.srt  metadata.json
facts.json  sources.json  run_report.json  (+ claims/people/timeline/qc/…)
```

Launch the dashboard:

```bash
uvicorn dashboard.app:app --port 8080     # http://localhost:8080
```

---

## The pipeline

```
SCHEDULE → DISCOVER → COLLECT SOURCES → FACT CHECK → RANK → SELECT
   → BUILD FACT DB → SCRIPT → STORYBOARD → VISUALS → NARRATION → CAPTIONS
   → EDIT/RENDER → THUMBNAIL → QC (policy+fact+copyright) → UPLOAD
   → SCHEDULE PUBLICATION → ANALYTICS → improve future selection
```

Each stage is **idempotent and resumable** — a failure in scene 17 retries scene
17, not the whole episode. See [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Commands

| Command | What it does |
|---------|--------------|
| `python -m app.health` | Dependency/connector health (PASS/WARN/FAIL) |
| `python -m app.setup_wizard` | First-run connector setup (writes local `.env`) |
| `python -m app.run --story <id>` | Produce one episode end-to-end |
| `python -m app.pipeline` | Full scheduled run (discover→…→upload) |
| `python -m app.pipeline --select-only` | Show today's winner + reason |
| `python -m app.cli analytics` | Weekly analytics (advisory weights) |
| `python -m app.cli cleanup` | Prune intermediate render files |
| `uvicorn dashboard.app:app` | Operational dashboard |

**Stop / disable immediately:** set `UPLOAD_ENABLED=false` (stops all uploading)
and `PUBLIC_AUTO_PUBLISH=false` (stops public publishing). See
[`OPERATIONS.md`](OPERATIONS.md).

---

## Documentation

- [`SETUP.md`](SETUP.md) — click-by-click account & credential setup (non-developer friendly)
- [`HUMAN_CHECKLIST.md`](HUMAN_CHECKLIST.md) — the only things a human must do
- [`SECURITY.md`](SECURITY.md) — credential model, what is never stored/logged
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — components, data flow, state machine
- [`PROVIDERS.md`](PROVIDERS.md) — provider/fallback matrix, free-tier notes
- [`OPERATIONS.md`](OPERATIONS.md) — run, stop, validation stages, recovery

---

## License & cost honesty

The **software** here is open-source (MIT). It relies on **third-party provider
free tiers** (OpenRouter free models, Pexels, Pixabay, CourtListener, Edge TTS,
YouTube Data API) whose terms and limits are set by those providers and **can
change**. Nothing here is guaranteed permanently free. Paid providers are
optional and off by default. See [`PROVIDERS.md`](PROVIDERS.md) for the exact
distinction between *free software*, *current free tier*, and *paid optional*.

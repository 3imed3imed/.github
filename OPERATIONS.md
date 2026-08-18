# OPERATIONS

## Start the system

**Produce one episode (local):**
```bash
source .venv/bin/activate
python -m app.run --story <story_id>
```

**Run the full scheduled pipeline once (local):**
```bash
python -m app.pipeline            # discover → … → upload (gated)
python -m app.pipeline --stage-a  # research/verify/select only
python -m app.pipeline --select-only
```

**Automated:** the `Daily Production` GitHub Action runs on schedule
(`.github/workflows/daily-production.yml`) or via **Run workflow**
(workflow_dispatch). The `Manual Production` workflow produces a specific story.

**Dashboard:**
```bash
uvicorn dashboard.app:app --port 8080   # http://localhost:8080
```

## Stop the system

- **Stop uploading immediately:** set `UPLOAD_ENABLED=false` (repo variable and/or
  `.env`). The next run renders only; nothing is uploaded.
- **Stop public publishing immediately:** set `PUBLIC_AUTO_PUBLISH=false`. Videos
  will at most be uploaded **private**; none are scheduled public.
- **Stop scheduled runs entirely:** disable the workflows in the repo's
  **Actions** tab, or remove the `schedule:` triggers.
- **Kill a local run:** Ctrl-C. State/artifacts already written are preserved;
  re-running resumes from the last completed stage.

## Disable publishing — the fastest path

```bash
# In GitHub: Settings → Secrets and variables → Actions → Variables
UPLOAD_ENABLED=false
PUBLIC_AUTO_PUBLISH=false
```
`PUBLIC_AUTO_PUBLISH` can only be turned on by the owner and is never flipped
automatically.

## Validation stages (do in order)

| Stage | Command | What to verify |
|-------|---------|----------------|
| **A** research only | `python -m app.pipeline --stage-a` (×3 stories) | selection reasons, verification, scores |
| **B** full videos, no upload | `python -m app.run --story <id>` (×3) | facts, render, audio, visuals, copyright manifests |
| **C** private uploads | set `UPLOAD_ENABLED=true`, rerun | OAuth, processing, thumbnail, captions, metadata, AI disclosure — videos are **private** on your channel |
| **D** public | owner sets `PUBLIC_AUTO_PUBLISH=true` | only after A–C look correct |

## Cost & safety monitoring

- `run_report.json` per episode shows `actual_cost` (must be `0` with paid
  services off) and `synthetic_media_used`.
- Dashboard → **Providers** shows live request/failure/quota and actual ¥.
- Dashboard → **Overview** badges show upload mode and the ¥0 guard state.

## Failure recovery

- **A scene fails to render** → it retries in isolation, then falls back to a
  text card. Other scenes are untouched (their clips are cached).
- **A provider quota is exhausted** → chain falls back to the next free provider;
  if none remain, the job pauses and opens a GitHub Issue. No money is spent.
- **YouTube token expired / upload rejected** → job records the error, opens an
  Issue, and marks the story `qc_failed`/blocked rather than silently skipping.
- **Resume** → simply re-run the same command; completed stages are reused.

## Scheduled times (Asia/Tokyo)

See `config/schedule.yml`. Cron in the workflows is UTC (JST − 9h). Adjust the
`cron:` lines to change timing. Only one production job runs at a time
(`concurrency: production`).

## Cleanup

```bash
python -m app.cli cleanup     # prune scene clips / audio chunks for finished episodes
```
Deliverables (`final.mp4`, `thumbnail.jpg`, captions, metadata, sources,
`run_report.json`) are kept.

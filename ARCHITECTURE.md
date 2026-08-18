# ARCHITECTURE

## Overview

```
                          ┌─────────────────────────────────────────┐
                          │            SCHEDULER (Actions)           │
                          │  daily-production / weekly-analytics     │
                          └───────────────────┬─────────────────────┘
                                              │
  ┌───────────────────────────────────────────────────────────────────────────┐
  │                             app.pipeline (run lock)                          │
  │                                                                             │
  │  DISCOVER ──► RANK+NICHE ──► SELECT ─────────────────────────────┐          │
  │  (sources/*)   (ranking,      (dedupe ledger)                    │          │
  │                 niche)                                           ▼          │
  │                                                          app.run.produce()   │
  │                                                                             │
  │  RESEARCH ─► VERIFY ─► FACT DB ─► SCRIPT ─► STORYBOARD ─► VISUALS ─► AUDIO   │
  │  (research)  (verify)  (*.json)   (+orig.   (+visual      (+licence  (TTS    │
  │                                    check)    safety)       manifest) chain)  │
  │        │                                                                     │
  │        ▼                                                                     │
  │  CAPTIONS ─► RENDER (ffmpeg, resumable) ─► THUMBNAIL ─► DESCRIPTION ─► QC    │
  │                                                                    (policy+  │
  │                                                                     fact+    │
  │                                                                     copyright)│
  │        │                                                             │       │
  │        ▼                                                             ▼       │
  │  UPLOAD (gated) ─► SCHEDULE (publishAt) ─► LEDGER ─► ANALYTICS ─► weights     │
  └───────────────────────────────────────────────────────────────────────────┘
                                              │
                          ┌───────────────────┴─────────────────────┐
                          │  Cross-cutting: providers (cost guard),  │
                          │  state machine, observability, alerts    │
                          └─────────────────────────────────────────┘
```

## Layers

### Provider abstraction (`app/providers/`)
Every external capability is a `Provider` with: **name, kind, cost_class, quota,
request count, failure count, fallback, actual_cost**. A `ProviderChain` tries
providers **free-first** and falls back automatically. The base class blocks any
`PAID` provider unless `ALLOW_PAID_SERVICES=true` and asserts `actual_cost == 0`
otherwise. Chains: `llm`, `tts`, `video`, `stock`, plus `legal`.

### Stages (`app/*.py`)
Discovery → niche → ranking → verification → research(fact DB) → scripting(+
originality) → storyboard(+visual safety) → visuals(+licence manifest) → audio →
captions → rendering(resumable) → thumbnails → titles/description → qc →
publishing(youtube) → analytics.

### State machine (`app/state.py`)
`candidate → researching → verified → selected → scripted → assets → rendering →
ready → uploaded → scheduled → published` (plus `rejected`, `qc_failed`). Every
transition is timestamped and validated; illegal jumps raise.

### Observability & alerts (`app/observability.py`, `app/alerts.py`)
Each job emits a `run_report.json` (job_id, stage, provider, requests, errors,
retries, elapsed, estimated/actual cost, synthetic_media flag). Serious failures
open a GitHub Issue (and always persist locally).

## Idempotency & resume
Artifacts are content-addressed by scene id. Rendering skips scenes whose clip
already exists and is valid; research reuses `sources.json`; audio reuses per-
scene WAVs. A failed scene retries in isolation, then falls back to a text card
rather than failing the whole render.

## Data contracts (`app/models.py`)
Pydantic models mirror the spec's JSON schemas: `Candidate`, `Source`, `Claim`,
`Fact`, `Person`, `TimelineEntry`, `Scene`, `Asset`, `JobReport`. Project
artifacts on disk validate against these.

## Fallback / degraded mode
- No OpenRouter key → deterministic offline script writer.
- No Pexels/Pixabay → owned generated cards.
- No Agnes → Ken Burns still-motion (no synthetic media).
- No Edge TTS/network → timed silent master (timing preserved).
- No YouTube OAuth or `UPLOAD_ENABLED=false` → dry-run (render only).

The episode always renders; the system never pays money to keep running.

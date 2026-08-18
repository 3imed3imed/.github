# PROVIDERS & FALLBACK MATRIX

> **Cost honesty.** Three categories are kept distinct:
> - **Free software** — open-source, runs locally, no third party (FFmpeg,
>   Pillow, this codebase, the deterministic writer, Ken Burns motion).
> - **Current provider free tier** — free *today* under a third party's terms and
>   limits, which **can change** (OpenRouter free models, Pexels, Pixabay,
>   CourtListener, Edge TTS, YouTube Data API quota).
> - **Paid optional** — costs money; **blocked** unless `ALLOW_PAID_SERVICES=true`.
>
> Nothing here is guaranteed permanently free.

## Matrix

| Capability | Provider | Category | Cost class | Fallback | If all exhausted |
|-----------|----------|----------|-----------|----------|------------------|
| LLM | OpenRouter (`:free` models) | free tier | `free_tier` | offline writer | use offline writer |
| LLM | Offline template writer | free software | `free` | — | always available |
| TTS | Edge TTS | free tier | `free` | silent master | timed silence |
| TTS | Silent master | free software | `free` | — | always available |
| AI video | Agnes | free tier* | `free_tier` | still-motion | Ken Burns still |
| AI video | Still-motion (Ken Burns) | free software | `free` | — | always available |
| Stock | Pexels | free tier | `free_tier` | Pixabay | generated card |
| Stock | Pixabay | free tier | `free_tier` | generated | generated card |
| Stock | Generated cards | free software | `free` | — | always available |
| Legal | CourtListener | free tier | `free_tier` | — | verify w/ other sources |

\* Agnes pricing depends on your plan. If your Agnes plan is paid, mark it PAID
and it will be blocked unless you enable paid services.

## The cost guard (how ¥0 is enforced)

1. Each provider declares a `cost_class`.
2. `Provider.call()` raises `PaidServiceBlocked` for any `PAID` provider while
   `ALLOW_PAID_SERVICES=false`.
3. `ProviderChain` skips paid providers entirely in that mode and tries the next
   free option; if none succeed it **raises, alerts, and pauses** — it never
   pays to proceed.
4. `JobTracker.enforce_cost_invariant()` asserts `actual_cost == 0` when paid
   services are disallowed; a violation fails the job loudly.

## When free providers are exhausted

`DO NOT CHARGE MONEY → PAUSE JOB → LOG FAILURE → CREATE ALERT.`
A GitHub Issue is opened (label `provider-failure`) and the job stops. You decide
whether to wait for quota reset or (deliberately) enable a paid provider.

## Swapping providers

Providers are isolated behind adapters (`app/providers/*.py`). To add or replace
one, implement a `Provider` subclass and add it to the relevant `build_*_chain`.
No stage code changes.

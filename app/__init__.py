"""Crime YouTube Factory — automated, zero-cost-by-default documentary pipeline.

The package is organised as a set of pipeline stages (discovery, research,
verification, ranking, scripting, storyboard, visuals, audio, rendering,
thumbnails, qc, publishing, analytics) that all sit on top of a provider
abstraction layer with a hard cost guard.

Design invariants (enforced in code, see ``app.providers.base``):

* No paid provider call may execute unless ``ALLOW_PAID_SERVICES=true``.
* Every provider reports name, cost class, quota, request/failure counts and a
  fallback. When free providers are exhausted the job pauses and alerts — it
  never spends money.
* Every stage is idempotent and resumable so a partial failure retries only the
  failed unit of work.
"""

__version__ = "0.1.0"

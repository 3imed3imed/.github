# SECURITY

## Credential model

This system uses **three** kinds of credentials and **no passwords**:

| Auth type | Used for | Stored as |
|-----------|----------|-----------|
| OAuth refresh token | YouTube upload/metadata/captions | GitHub Secret / local `.env` |
| API key | OpenRouter, Pexels, Pixabay, CourtListener, Agnes | GitHub Secret / local `.env` |
| GitHub token | CI, scheduler, automated failure Issues | Provided by Actions (`GITHUB_TOKEN`) |

### We never
- store or scrape website **username/password** pairs;
- use browser password storage;
- write plaintext credential files beyond the git-ignored local `.env`;
- commit any secret to git (`.env` is in `.gitignore`; a CI secret-scan test
  fails the build if key-shaped strings appear in source).

### We never log secrets
`app/observability.py` installs a `RedactingFilter` on the logger that scrubs
`Authorization: Bearer …`, `Token …`, and `?key=/api_key=/token=` query values
before anything is written. API keys, refresh tokens and OAuth secrets never
appear in logs, run reports, alerts or the dashboard (the dashboard shows only
`CONNECTED/OPTIONAL/MISSING`, never values).

## Least privilege
- YouTube OAuth requests only `youtube.upload` + `youtube` scopes.
- The GitHub token used in Actions is the workflow-scoped `GITHUB_TOKEN`.
- CourtListener/Pexels/Pixabay keys are read-only data keys.

## Revocation
- **YouTube:** revoke the app under Google Account → Security → Third-party
  access. The refresh token stops working immediately.
- **API keys:** rotate/delete in each provider's dashboard, then update the
  GitHub Secret.

## Reporting
Open a private security advisory or contact the repository owner. Do not file
public issues for suspected credential exposure.

## Secret scanning
- `tests/test_providers_failure.py::test_no_hardcoded_secrets_in_source` scans
  the `app/` tree for key-shaped strings on every CI run.
- Enable GitHub **Secret scanning** and **Push protection** in repo settings for
  defense in depth.

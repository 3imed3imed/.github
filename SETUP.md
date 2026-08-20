# SETUP — step by step (written for a non-developer)

You do **not** need to write any code. Follow each numbered step. Whenever you
create a key or token, you will paste it into **GitHub Secrets** (for automation)
or a local **`.env`** file (for testing on your computer). **Never** paste a
password anywhere — this system only uses API keys and OAuth tokens.

> Expected time: ~45–60 minutes. You can stop after Part 1 and already produce
> videos locally with **no accounts at all** (everything falls back to free,
> offline behaviour).

---

## Part 0 — Install the basics (once)

1. Install **Python 3.11+**: <https://www.python.org/downloads/>
2. Install **FFmpeg**:
   - macOS: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt-get install -y ffmpeg`
   - Windows: download from <https://www.gyan.dev/ffmpeg/builds/> and add to PATH
3. Open a terminal in the project folder and run:
   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -e ".[dev,media,dashboard]"
   ```
4. Confirm it works:
   ```bash
   python -m app.health
   ```
   **Expected output:** a list of checks. `ffmpeg` should say `PASS`. Everything
   else may say `WARN` (that's fine — it means "not configured yet, using free
   fallback"). The last line should say `RESULT: OK`.
5. Make your first video with no accounts:
   ```bash
   python -m app.run --story fixture-genealogy-coldcase
   ```
   **Expected output:** `OK story=… qc_passed=True upload=dry-run` and a folder
   `projects/fixture-genealogy-coldcase/` containing `final.mp4`.

You now have a working, zero-cost system. The rest adds real sources and, later,
uploading.

---

## Part 1 — Copy the environment file

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Leave every value blank for now. You will fill some in below. **Do not commit
   `.env`** (it is already git-ignored).

---

## Part 2 — OpenRouter (free LLM for better scripts) — optional

1. Go to <https://openrouter.ai/> and sign up (free).
2. Open <https://openrouter.ai/keys> → **Create Key** → copy it.
3. In `.env`, set:
   ```
   OPENROUTER_API_KEY=sk-or-...paste...
   ```
4. Test:
   ```bash
   python -m app.health
   ```
   **Expected:** `llm_provider  PASS  OpenRouter key present (free models)`.

> The system only uses models whose name ends in `:free`. It will never switch
> to a paid model on its own.

---

## Part 3 — Pexels & Pixabay (free stock visuals) — optional

**Pexels**
1. Go to <https://www.pexels.com/api/> → **Get Started** → sign up.
2. Copy your API key from the dashboard.
3. In `.env`: `PEXELS_API_KEY=...paste...`

**Pixabay**
1. Go to <https://pixabay.com/api/docs/> → sign up/log in.
2. Your API key is shown on that docs page after login.
3. In `.env`: `PIXABAY_API_KEY=...paste...`

Test both: `python -m app.health` → they should read `PASS`.

> Without these, the system generates its own clean documentary cards instead of
> stock footage. It still renders fine.

---

## Part 4 — CourtListener (legal verification) — optional

1. Go to <https://www.courtlistener.com/help/api/rest/> — the API works
   **without** a key at low volume.
2. To raise limits, create an account and copy your API token from your profile.
3. In `.env`: `COURTLISTENER_API_TOKEN=...paste...`

---

## Part 5 — Agnes AI (experimental AI video) — optional

1. Create an account with your Agnes provider and generate an API key.
2. In `.env`:
   ```
   AGNES_API_KEY=...paste...
   AGNES_BASE_URL=https://api.agnes.ai/v1
   ```
> The system works completely without Agnes — it uses Ken Burns motion over
> stills instead. Only enable Agnes if its free tier suits you.

---

## Part 6 — YouTube (upload) — do this only when you're ready to upload

This is the one multi-step account task. You will create a Google Cloud project,
enable the YouTube Data API, create OAuth credentials, and authorize your channel
**once** to get a **refresh token**. You will never store your Google password.

1. **Create/choose a YouTube channel** at <https://www.youtube.com/> (Settings →
   Add/manage channels).
2. **Create a Google Cloud project**: <https://console.cloud.google.com/> →
   project dropdown → **New Project** → name it → **Create**.
3. **Enable the API**: APIs & Services → **Library** → search **"YouTube Data API
   v3"** → **Enable**.
4. **Configure the OAuth consent screen**: APIs & Services → **OAuth consent
   screen** → choose **External** → fill app name and your email → add your
   Google account under **Test users** → Save.
5. **Create OAuth credentials**: APIs & Services → **Credentials** → **Create
   Credentials** → **OAuth client ID** → Application type **Desktop app** →
   **Create**. Copy the **Client ID** and **Client secret**.
6. In `.env`:
   ```
   YOUTUBE_CLIENT_ID=...paste...
   YOUTUBE_CLIENT_SECRET=...paste...
   ```
7. **Get a refresh token (one-time authorization)** — run the helper:
   ```bash
   pip install -e ".[youtube]"
   python -m scripts.youtube_oauth
   ```
   It prints a URL. Open it, sign in, approve the **youtube.upload** permission,
   and paste the code back. The script prints a `YOUTUBE_REFRESH_TOKEN`.
8. In `.env`: `YOUTUBE_REFRESH_TOKEN=...paste...`
9. Test:
   ```bash
   python -m app.health
   ```
   **Expected:** `youtube_oauth  PASS  refresh token configured`.

> **YouTube API audit:** to upload public videos at volume, Google may require an
> API audit of your project. Complete it in the Cloud console when prompted. This
> is a one-time human step.

---

## Part 7 — GitHub Secrets (for automation)

To run on a schedule via GitHub Actions, store the same values as **repository
secrets** (not in the repo):

1. In your GitHub repo → **Settings → Secrets and variables → Actions**.
2. Add each secret you use: `OPENROUTER_API_KEY`, `PEXELS_API_KEY`,
   `PIXABAY_API_KEY`, `COURTLISTENER_API_TOKEN`, `AGNES_API_KEY`,
   `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`,
   `YOUTUBE_PLAYLIST_ID`.
3. Add **repository variables** (Settings → Variables) to control rollout:
   - `UPLOAD_ENABLED` = `false` (start here)
   - `PUBLIC_AUTO_PUBLISH` = `false` (never set to true until validated)

---

## Part 8 — Validation stages (do these in order)

See [`OPERATIONS.md`](OPERATIONS.md) for details.

1. **Stage A** — research only: `python -m app.pipeline --stage-a`
2. **Stage B** — 3 full videos, no upload: `python -m app.run --story <id>` ×3
3. **Stage C** — private uploads: set `UPLOAD_ENABLED=true`, run again, check the
   videos appear **private** on your channel.
4. **Stage D** — public: only after A–C look good, set `PUBLIC_AUTO_PUBLISH=true`.

Done. See [`HUMAN_CHECKLIST.md`](HUMAN_CHECKLIST.md) for the short list of things
only you can do.

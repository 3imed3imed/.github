# HUMAN SETUP CHECKLIST

Everything not on this list is automated. These are the only actions that
genuinely require a person (account creation, authorization, audits, and the one
irreversible safety decision).

- [ ] Create or choose a **YouTube channel**
- [ ] Create a **Google Cloud project**
- [ ] Enable the **YouTube Data API v3**
- [ ] Configure the **OAuth consent screen** (add yourself as a test user)
- [ ] Create **OAuth credentials** (Desktop app) → Client ID + Secret
- [ ] Authorize the channel **once** to obtain a **refresh token**
      (`python -m scripts.youtube_oauth`)
- [ ] Complete the **YouTube API audit** when Google requires it (for public
      uploads at volume)
- [ ] Create an **OpenRouter** API key (optional, free — better scripts)
- [ ] Create a **Pexels** API key (optional, free — stock visuals)
- [ ] Create a **Pixabay** API key (optional, free — stock visuals)
- [ ] Create a **CourtListener** token (optional — raises rate limits)
- [ ] Create an **Agnes** key (optional — experimental AI video)
- [ ] Add all secrets to **GitHub Secrets**; set repo **Variables**
      `UPLOAD_ENABLED` and `PUBLIC_AUTO_PUBLISH`
- [ ] Run **validation Stages A → B → C** (see OPERATIONS.md)
- [ ] **Only after** A–C look correct: set `PUBLIC_AUTO_PUBLISH=true`

## Things the system will NOT do (by design)
- Bypass CAPTCHA, MFA, or account security — ever.
- Circumvent provider quotas or spend money without `ALLOW_PAID_SERVICES=true`.
- Turn on public auto-publishing by itself.
- Store your Google (or any) password.

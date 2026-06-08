// ═══════════════════════════════════════════════════════
// MAKNABIS — Central Configuration
// Edit the 3 URLs below, then deploy. That's it.
// ═══════════════════════════════════════════════════════
window.FARM_CONFIG = {
  // ── Paste your 3 Apps Script /exec URLs here ──────
  GROWING_URL:      'PASTE_YOUR_GROWING_EXEC_URL_HERE',
  FINANCE_URL:      'PASTE_YOUR_FINANCE_EXEC_URL_HERE',
  AI_URL:           'PASTE_YOUR_AI_EXEC_URL_HERE',

  // ── Credentials (change if you changed them) ──────
  DASHBOARD_KEY:    'FARM2026',
  FINANCE_PASSWORD: 'FARM2026',

  // ── Farm info ─────────────────────────────────────
  FARM_NAME:        'MAKNABIS',
  OWNER_1:          'EL HABIB Imed',
  OWNER_2:          'EL HABIB Atef',
  PHONE:            '+216 25 982 388',
  ADDRESS:          'نهج 4860 السيجومي، تونس 2000',
  EMAIL:            'maknabis.tn@gmail.com',

  // ── App settings ──────────────────────────────────
  REFRESH_INTERVAL: 30,   // dashboard auto-refresh seconds
  ROOM_REFRESH:     60,   // 3D room auto-refresh seconds
  MAX_HISTORY_TURNS: 12,  // AI chat history turns kept
  VERSION:          'v3_cycles'
};

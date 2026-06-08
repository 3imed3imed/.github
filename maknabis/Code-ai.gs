/**
 * MAKNABIS - مزرعة الفطر
 * AI Chat Assistant Backend — Google Apps Script
 * Uses Gemini 2.5 Flash API (free tier)
 * Version: v1_ai
 *
 * Script Properties required:
 *   GEMINI_API_KEY   — Gemini API key
 *   GROWING_API_URL  — URL of the growing/room data endpoint
 *   DASHBOARD_KEY    — API key for the dashboard endpoint
 *   FINANCE_API_URL  — URL of the finance data endpoint (reserved for future use)
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

var GEMINI_MODEL = 'gemini-2.5-flash';
var GEMINI_API_VERSION = 'v1beta';
var GEMINI_ENDPOINT =
  'https://generativelanguage.googleapis.com/' +
  GEMINI_API_VERSION +
  '/models/' +
  GEMINI_MODEL +
  ':generateContent';

var CACHE_KEY_FARM_CONTEXT = 'maknabis_farm_context';
var CACHE_TTL_SECONDS = 300; // 5 minutes

var VERSION = 'v1_ai';

// ---------------------------------------------------------------------------
// System Prompt
// ---------------------------------------------------------------------------

var SYSTEM_PROMPT_BASE =
  'أنت مساعد ذكي خبير في زراعة الفطر الأبيض (Agaricus bisporus) وسوق الفطر في تونس،\n' +
  'وأنت جزء من نظام إدارة مزرعة فطر متكامل اسمه "MAKNABIS - مزرعة الفطر".\n\n' +
  'شخصيتك:\n' +
  '- تتكلم بالعربية بلهجة تونسية ودودة ومباشرة\n' +
  '- صريح وعملي، تعطي أرقام وخطوات محددة\n' +
  '- إذا ما تعرفش شي، قول "ما عنديش معطيات دقيقة"\n\n' +
  'معرفتك بسوق الفطر التونسي:\n' +
  '- المشترين: Carrefour, Monoprix, Géant, مطاعم/فنادق, Bir Kassâa جملة\n' +
  '- التسعير المرجعي: جملة 3-5 د/كغ, تقسيط 6-12 د/كغ\n' +
  '- الموسمية: رمضان = ذروة, الصيف = ركود\n\n' +
  'معرفتك بالمشروع:\n' +
  '- اسم المزرعة: MAKNABIS\n' +
  '- المؤسسون: EL HABIB Imed و EL HABIB Atef، Co-Founders & Co-CEOs\n' +
  '- الموقع: نهج 4860 السيجومي، تونس\n' +
  '- دورة الإنتاج 32 يوم: setup → spawn_run → casing → case_run → pinning → waiting → harvest\n' +
  '- 3 قراءات يومية: صباح 06:00، ظهر 14:00، مساء 20:00\n' +
  '- الأهداف البيئية حسب المرحلة:\n' +
  '  spawn_run: حرارة هواء 23-24°C، حرارة كمبوست 24-25°C، رطوبة 90-95%، CO2 10000-15000 ppm\n' +
  '  case_run: حرارة 23-24°C، رطوبة 90-95%، CO2 5000-7500 ppm\n' +
  '  pinning: حرارة 16-18°C، رطوبة 95-100%، CO2 800-1200 ppm\n' +
  '  harvest: حرارة 18-20°C، رطوبة 90-95%، CO2 1000-3000 ppm\n';

// ---------------------------------------------------------------------------
// Entry Points
// ---------------------------------------------------------------------------

/**
 * HTTP GET handler.
 * Supports ?ping=1 for health checks.
 */
function doGet(e) {
  var params = e && e.parameter ? e.parameter : {};

  if (params.ping === '1') {
    var props = PropertiesService.getScriptProperties();
    var hasKey = !!(props.getProperty('GEMINI_API_KEY'));
    return jsonResponse({
      ok: true,
      has_gemini_key: hasKey,
      model: GEMINI_MODEL,
      version: VERSION
    });
  }

  return jsonResponse({
    ok: false,
    error: 'Unknown request. Use ?ping=1 for health check or POST for chat.'
  });
}

/**
 * HTTP POST handler.
 * Expected body: { action: 'ask', messages: [...], context_refresh: bool }
 */
function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    var action = body.action || '';

    if (action === 'ask') {
      return handleAsk(body);
    }

    return jsonResponse({ ok: false, error: 'Unknown action: ' + action });

  } catch (err) {
    return jsonResponse({ ok: false, error: 'Bad request: ' + err.message });
  }
}

// ---------------------------------------------------------------------------
// Action Handlers
// ---------------------------------------------------------------------------

/**
 * Handle action='ask'.
 * Gathers farm context, builds system prompt, calls Gemini.
 */
function handleAsk(body) {
  var messages = body.messages;
  var contextRefresh = body.context_refresh === true;

  if (!messages || !Array.isArray(messages) || messages.length === 0) {
    return jsonResponse({ ok: false, error: 'messages array is required' });
  }

  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty('GEMINI_API_KEY');
  if (!apiKey) {
    return jsonResponse({ ok: false, error: 'GEMINI_API_KEY not configured' });
  }

  // Gather live farm context
  var farmCtx = null;
  try {
    farmCtx = gatherContext(contextRefresh);
  } catch (err) {
    // Non-fatal — proceed without live context
    Logger.log('gatherContext error: ' + err.message);
  }

  var systemContext = SYSTEM_PROMPT_BASE;
  if (farmCtx) {
    systemContext += '\n\n' + formatContextForPrompt(farmCtx);
  }

  var result = callGemini(messages, systemContext, apiKey);
  return jsonResponse(result);
}

// ---------------------------------------------------------------------------
// Farm Context
// ---------------------------------------------------------------------------

/**
 * Gather live farm context from GROWING_API_URL.
 * Results are cached for CACHE_TTL_SECONDS seconds.
 * Pass forceRefresh=true to bypass cache.
 *
 * @param {boolean} forceRefresh
 * @returns {Object|null} parsed JSON context or null on failure
 */
function gatherContext(forceRefresh) {
  var cache = CacheService.getScriptCache();

  if (!forceRefresh) {
    var cached = cache.get(CACHE_KEY_FARM_CONTEXT);
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch (e) {
        // Cache entry corrupt — fall through to fetch
      }
    }
  }

  var props = PropertiesService.getScriptProperties();
  var growingUrl = props.getProperty('GROWING_API_URL');
  var dashKey = props.getProperty('DASHBOARD_KEY');

  if (!growingUrl) {
    throw new Error('GROWING_API_URL not configured');
  }

  var url = growingUrl + '?mode=room&key=' + encodeURIComponent(dashKey || '');

  var response = UrlFetchApp.fetch(url, {
    method: 'GET',
    muteHttpExceptions: true,
    headers: { 'Accept': 'application/json' }
  });

  var code = response.getResponseCode();
  if (code !== 200) {
    throw new Error('Growing API returned HTTP ' + code);
  }

  var ctx = JSON.parse(response.getContentText());

  // Store in cache
  try {
    cache.put(CACHE_KEY_FARM_CONTEXT, JSON.stringify(ctx), CACHE_TTL_SECONDS);
  } catch (e) {
    Logger.log('Cache put error: ' + e.message);
  }

  return ctx;
}

/**
 * Format farm context object into an Arabic text block for the system prompt.
 *
 * @param {Object} ctx
 * @returns {string}
 */
function formatContextForPrompt(ctx) {
  var lines = [];
  lines.push('📡 الحالة الحية للمزرعة:');

  // Active cycle
  var cycle = ctx.cycle || ctx.active_cycle || ctx.current_cycle || null;
  if (cycle) {
    var cycleId = cycle.id || cycle.batch_id || cycle.name || 'غير محدد';
    lines.push('• الدورة النشطة: ' + cycleId);

    if (cycle.day !== undefined && cycle.day !== null) {
      lines.push('• يوم الدورة: ' + cycle.day);
    }

    var stage = cycle.stage || cycle.phase || cycle.status || null;
    if (stage) {
      lines.push('• المرحلة: ' + stage);
    }
  }

  // Latest reading
  var reading = ctx.latest_reading || ctx.last_reading || ctx.readings || null;
  if (reading) {
    // Handle array of readings — pick the first/latest
    if (Array.isArray(reading)) {
      reading = reading[0];
    }
    var readingParts = [];
    if (reading.temperature !== undefined && reading.temperature !== null) {
      readingParts.push('حرارة ' + reading.temperature + '°C');
    }
    if (reading.humidity !== undefined && reading.humidity !== null) {
      readingParts.push('رطوبة ' + reading.humidity + '%');
    }
    if (reading.co2 !== undefined && reading.co2 !== null) {
      readingParts.push('CO2 ' + reading.co2 + ' ppm');
    }
    if (reading.compost_temp !== undefined && reading.compost_temp !== null) {
      readingParts.push('حرارة كمبوست ' + reading.compost_temp + '°C');
    }
    if (readingParts.length > 0) {
      lines.push('• آخر قراءة: ' + readingParts.join('، '));
    }
    if (reading.timestamp || reading.recorded_at || reading.time) {
      lines.push('• وقت القراءة: ' + (reading.timestamp || reading.recorded_at || reading.time));
    }
  }

  // Room environment (alternative flat structure)
  if (!reading) {
    var tempParts = [];
    if (ctx.temperature !== undefined) tempParts.push('حرارة ' + ctx.temperature + '°C');
    if (ctx.humidity !== undefined) tempParts.push('رطوبة ' + ctx.humidity + '%');
    if (ctx.co2 !== undefined) tempParts.push('CO2 ' + ctx.co2 + ' ppm');
    if (tempParts.length > 0) {
      lines.push('• آخر قراءة: ' + tempParts.join('، '));
    }
  }

  // Alerts
  var alerts = ctx.alerts || ctx.warnings || ctx.alarms || [];
  if (Array.isArray(alerts) && alerts.length > 0) {
    var alertTexts = alerts.map(function(a) {
      return typeof a === 'string' ? a : (a.message || a.text || JSON.stringify(a));
    });
    lines.push('• التنبيهات: ' + alertTexts.join(' | '));
  } else if (alerts && typeof alerts === 'object' && Object.keys(alerts).length > 0) {
    lines.push('• التنبيهات: ' + JSON.stringify(alerts));
  } else {
    lines.push('• التنبيهات: لا توجد تنبيهات');
  }

  // Extra fields if present
  if (ctx.next_harvest_estimate || ctx.harvest_estimate) {
    lines.push('• تقدير الحصاد القادم: ' + (ctx.next_harvest_estimate || ctx.harvest_estimate));
  }
  if (ctx.total_weight_kg !== undefined) {
    lines.push('• الإنتاج الكلي المتوقع: ' + ctx.total_weight_kg + ' كغ');
  }

  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Gemini API Call
// ---------------------------------------------------------------------------

/**
 * Call the Gemini 2.5 Flash API with the provided messages and system context.
 *
 * @param {Array}  messages      Array of {role, parts:[{text}]} objects (Gemini format)
 *                               or {role, content} objects (OpenAI-style, auto-converted)
 * @param {string} systemContext Full system prompt text
 * @param {string} [apiKey]      Optional — if omitted, reads from Script Properties
 * @returns {{ ok: boolean, reply?: string, sources?: Array, error?: string }}
 */
function callGemini(messages, systemContext, apiKey) {
  var props = PropertiesService.getScriptProperties();
  var key = apiKey || props.getProperty('GEMINI_API_KEY');

  if (!key) {
    return { ok: false, error: 'GEMINI_API_KEY not configured' };
  }

  // Normalise messages to Gemini format
  var contents = normaliseMessages(messages);

  if (contents.length === 0) {
    return { ok: false, error: 'No valid messages to send' };
  }

  var requestBody = {
    systemInstruction: {
      parts: [{ text: systemContext || SYSTEM_PROMPT_BASE }]
    },
    contents: contents,
    tools: [
      { google_search: {} }
    ],
    generationConfig: {
      temperature: 0.7,
      maxOutputTokens: 2048
    }
  };

  var url = GEMINI_ENDPOINT + '?key=' + encodeURIComponent(key);

  var options = {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify(requestBody),
    muteHttpExceptions: true,
    headers: {
      'Accept': 'application/json'
    }
  };

  var response;
  try {
    response = UrlFetchApp.fetch(url, options);
  } catch (err) {
    return { ok: false, error: 'Network error: ' + err.message };
  }

  var code = response.getResponseCode();
  var rawText = response.getContentText();

  if (code !== 200) {
    var errMsg = 'Gemini API error HTTP ' + code;
    try {
      var errBody = JSON.parse(rawText);
      if (errBody.error && errBody.error.message) {
        errMsg += ': ' + errBody.error.message;
      }
    } catch (e) { /* ignore */ }
    Logger.log(errMsg);
    return { ok: false, error: errMsg };
  }

  var data;
  try {
    data = JSON.parse(rawText);
  } catch (e) {
    return { ok: false, error: 'Failed to parse Gemini response: ' + e.message };
  }

  return extractGeminiReply(data);
}

/**
 * Extract reply text and grounding sources from a Gemini API response.
 *
 * @param {Object} data  Parsed Gemini API JSON response
 * @returns {{ ok: boolean, reply?: string, sources?: Array, error?: string }}
 */
function extractGeminiReply(data) {
  try {
    var candidates = data.candidates;
    if (!candidates || candidates.length === 0) {
      // Check for prompt feedback (blocked content etc.)
      if (data.promptFeedback) {
        return {
          ok: false,
          error: 'Request blocked: ' + (data.promptFeedback.blockReason || 'unknown reason')
        };
      }
      return { ok: false, error: 'No candidates returned by Gemini' };
    }

    var candidate = candidates[0];

    // Extract text from parts
    var replyText = '';
    var parts = (candidate.content && candidate.content.parts) ? candidate.content.parts : [];
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i];
      if (part.text) {
        replyText += part.text;
      }
    }

    if (!replyText) {
      return { ok: false, error: 'Empty reply from Gemini' };
    }

    // Extract grounding sources (web search results)
    var sources = [];
    var meta = candidate.groundingMetadata;
    if (meta) {
      var chunks = meta.groundingChunks || meta.webSearchQueries || [];
      // groundingChunks is the structured form
      if (meta.groundingChunks && Array.isArray(meta.groundingChunks)) {
        for (var j = 0; j < meta.groundingChunks.length; j++) {
          var chunk = meta.groundingChunks[j];
          if (chunk.web) {
            sources.push({
              title: chunk.web.title || '',
              url: chunk.web.uri || ''
            });
          }
        }
      }
    }

    return { ok: true, reply: replyText.trim(), sources: sources };

  } catch (err) {
    return { ok: false, error: 'Error parsing Gemini response: ' + err.message };
  }
}

// ---------------------------------------------------------------------------
// Message Format Utilities
// ---------------------------------------------------------------------------

/**
 * Normalise a mixed array of messages into Gemini API `contents` format.
 * Accepts both Gemini-native format and OpenAI-style {role, content} format.
 *
 * Gemini roles: 'user' | 'model'
 * OpenAI roles mapped: 'user' → 'user', 'assistant' → 'model', 'system' → skipped (handled separately)
 *
 * @param {Array} messages
 * @returns {Array} Gemini-format contents array
 */
function normaliseMessages(messages) {
  var contents = [];

  for (var i = 0; i < messages.length; i++) {
    var msg = messages[i];
    var role = msg.role || 'user';
    var text = '';

    // Extract text from either format
    if (typeof msg.content === 'string') {
      text = msg.content;
    } else if (Array.isArray(msg.content)) {
      // OpenAI content array
      for (var k = 0; k < msg.content.length; k++) {
        if (msg.content[k].type === 'text') {
          text += msg.content[k].text;
        }
      }
    } else if (msg.parts && Array.isArray(msg.parts)) {
      // Already Gemini format
      for (var p = 0; p < msg.parts.length; p++) {
        if (msg.parts[p].text) {
          text += msg.parts[p].text;
        }
      }
    }

    // Skip system messages (handled via systemInstruction) and empty messages
    if (role === 'system' || !text.trim()) continue;

    // Map roles
    var geminiRole = (role === 'assistant') ? 'model' : 'user';

    // Gemini requires alternating user/model turns — merge consecutive same-role messages
    if (contents.length > 0 && contents[contents.length - 1].role === geminiRole) {
      contents[contents.length - 1].parts[0].text += '\n' + text;
    } else {
      contents.push({
        role: geminiRole,
        parts: [{ text: text }]
      });
    }
  }

  return contents;
}

// ---------------------------------------------------------------------------
// Response Helper
// ---------------------------------------------------------------------------

/**
 * Create a JSON ContentService response.
 *
 * @param {Object} obj
 * @returns {ContentService.TextOutput}
 */
function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ---------------------------------------------------------------------------
// Test Function (run from Apps Script editor)
// ---------------------------------------------------------------------------

/**
 * testGemini — run this manually in the Apps Script editor to verify
 * the Gemini integration is working correctly.
 *
 * Steps:
 *  1. Open the Apps Script editor.
 *  2. Select "testGemini" from the function dropdown.
 *  3. Click Run.
 *  4. Check the Execution log for results.
 */
function testGemini() {
  Logger.log('=== MAKNABIS AI Test — Gemini 2.5 Flash ===');

  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty('GEMINI_API_KEY');

  if (!apiKey) {
    Logger.log('ERROR: GEMINI_API_KEY is not set in Script Properties.');
    Logger.log('Go to Project Settings → Script Properties and add GEMINI_API_KEY.');
    return;
  }

  Logger.log('GEMINI_API_KEY found ✓');
  Logger.log('Model: ' + GEMINI_MODEL);

  var testMessages = [
    {
      role: 'user',
      content: 'مرحبا، كيف حالك؟ اشرحلي باختصار ايش هي المراحل الأساسية في زراعة الفطر الأبيض.'
    }
  ];

  Logger.log('Sending test message to Gemini...');

  var result = callGemini(testMessages, SYSTEM_PROMPT_BASE, apiKey);

  if (result.ok) {
    Logger.log('SUCCESS ✓');
    Logger.log('Reply: ' + result.reply);
    if (result.sources && result.sources.length > 0) {
      Logger.log('Sources (' + result.sources.length + '):');
      for (var i = 0; i < result.sources.length; i++) {
        Logger.log('  - ' + result.sources[i].title + ' → ' + result.sources[i].url);
      }
    } else {
      Logger.log('No external sources used.');
    }
  } else {
    Logger.log('FAILED ✗');
    Logger.log('Error: ' + result.error);
  }

  Logger.log('=== Test complete ===');
}

/**
 * testContext — run this to verify the farm context endpoint is reachable.
 */
function testContext() {
  Logger.log('=== MAKNABIS Farm Context Test ===');

  var props = PropertiesService.getScriptProperties();
  var growingUrl = props.getProperty('GROWING_API_URL');
  var dashKey = props.getProperty('DASHBOARD_KEY');

  if (!growingUrl) {
    Logger.log('ERROR: GROWING_API_URL is not set in Script Properties.');
    return;
  }

  Logger.log('GROWING_API_URL: ' + growingUrl);
  Logger.log('DASHBOARD_KEY set: ' + (dashKey ? 'yes' : 'no'));

  try {
    var ctx = gatherContext(true); // force refresh
    Logger.log('Context fetch SUCCESS ✓');
    Logger.log('Raw context: ' + JSON.stringify(ctx, null, 2));
    Logger.log('Formatted prompt section:');
    Logger.log(formatContextForPrompt(ctx));
  } catch (err) {
    Logger.log('Context fetch FAILED ✗: ' + err.message);
  }

  Logger.log('=== Context test complete ===');
}

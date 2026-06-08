/**
 * MAKNABIS - Tunisian Mushroom Farm Management System
 * Google Apps Script Backend
 * Version: v3_cycles
 * © 2026 MAKNABIS
 */

// ─────────────────────────────────────────────────────────
// CONSTANTS
// ─────────────────────────────────────────────────────────

var VERSION = 'v3_cycles';
var CHECKLISTS_VERSION = 'v3_cycles';
var DASHBOARD_KEY = 'FARM2026';
var PASSWORD = 'FARM2026';

var CYCLES_TAB = '🔄 الدورات';
var CYCLE_ID_HEADER = 'رقم الدورة';

// Reading session labels
var READ_AM   = 'القراءة الصباحية 06:00';
var READ_NOON = 'القراءة الظهرية 14:00';
var READ_PM   = 'القراءة المسائية 20:00';

// Cycles tab column order
var CYCLES_COLUMNS = [
  'رقم الدورة',      // A
  'الاسم',           // B
  'تاريخ البدء',     // C
  'الحصاد المتوقع',  // D
  'الغرفة',          // E
  'نوع الركيزة',     // F
  'عدد الأكياس',     // G
  'الحالة',          // H
  'ملاحظات',         // I
  'تاريخ الإنشاء'    // J
];

// ─────────────────────────────────────────────────────────
// CHECKLIST SCHEMA
// ─────────────────────────────────────────────────────────

/**
 * Returns env fields for spawn_run / case_run readings (with compost temp)
 */
function envFieldsFull(prefix) {
  return [
    prefix + '_air_temp',
    prefix + '_compost_temp',
    prefix + '_humidity',
    prefix + '_co2',
    prefix + '_notes'
  ];
}

/**
 * Returns env fields for waiting / harvest readings (no compost temp)
 */
function envFieldsLight(prefix) {
  return [
    prefix + '_air_temp',
    prefix + '_humidity',
    prefix + '_co2',
    prefix + '_notes'
  ];
}

/**
 * Base headers shared by every checklist tab
 */
var BASE_HEADERS = ['التاريخ', 'العامل', 'رقم الدورة'];

/**
 * CHECKLISTS definition
 * key → { tab, fields[] }
 */
var CHECKLISTS = {
  setup: {
    tab: '1 - استلام الأكياس',
    fields: BASE_HEADERS.concat([
      'عدد الأكياس المستلمة',
      'حالة الأكياس',
      'درجة الحرارة عند الاستلام',
      'مصدر الركيزة',
      'ملاحظات الاستلام',
      'توقيع المسؤول'
    ])
  },
  spawn_run: {
    tab: '2 - انتشار الميسيليوم',
    fields: BASE_HEADERS.concat(
      // AM
      [READ_AM].concat(envFieldsFull('am')),
      // NOON
      [READ_NOON].concat(envFieldsFull('noon')),
      // PM
      [READ_PM].concat(envFieldsFull('pm')),
      // summary
      ['ملاحظات عامة', 'تقييم اليوم']
    )
  },
  casing: {
    tab: '3 - التغطية',
    fields: BASE_HEADERS.concat([
      'نوع مادة التغطية',
      'سماكة التغطية (سم)',
      'درجة رطوبة مادة التغطية',
      'درجة الحرارة عند التغطية',
      'عدد الأكياس المغطاة',
      'ملاحظات التغطية',
      'توقيع المسؤول'
    ])
  },
  case_run: {
    tab: '4 - نمو الميسيليوم',
    fields: BASE_HEADERS.concat(
      [READ_AM].concat(envFieldsFull('am')),
      [READ_NOON].concat(envFieldsFull('noon')),
      [READ_PM].concat(envFieldsFull('pm')),
      ['نسبة تغطية الميسيليوم (%)', 'ملاحظات عامة', 'تقييم اليوم']
    )
  },
  pinning: {
    tab: '5 - تحفيز الإثمار',
    fields: BASE_HEADERS.concat(
      [READ_AM].concat(envFieldsLight('am')),
      [READ_NOON].concat(envFieldsLight('noon')),
      [READ_PM].concat(envFieldsLight('pm')),
      ['عدد نقاط التثمير المرئية', 'ملاحظات التحفيز', 'تقييم اليوم']
    )
  },
  waiting: {
    tab: '6 - انتظار الرؤوس',
    fields: BASE_HEADERS.concat(
      [READ_AM].concat(envFieldsLight('am')),
      [READ_NOON].concat(envFieldsLight('noon')),
      [READ_PM].concat(envFieldsLight('pm')),
      ['حجم الرؤوس الملاحظة', 'ملاحظات', 'تقييم اليوم']
    )
  },
  harvest: {
    tab: '7 - الحصاد',
    fields: BASE_HEADERS.concat(
      [READ_AM].concat(envFieldsLight('am')),
      [READ_NOON].concat(envFieldsLight('noon')),
      [READ_PM].concat(envFieldsLight('pm')),
      ['harvest_kg_1', 'harvest_kg_2', 'إجمالي الحصاد (كغ)', 'جودة المحصول', 'ملاحظات الحصاد']
    )
  },
  between: {
    tab: '8 - بين الموجات',
    fields: BASE_HEADERS.concat([
      'رقم الموجة المنتهية',
      'تاريخ بداية الراحة',
      'إجراءات التنظيف',
      'معالجة الأكياس',
      'درجة الحرارة',
      'الرطوبة',
      'ملاحظات'
    ])
  },
  emergency: {
    tab: '9 - طوارئ',
    fields: BASE_HEADERS.concat([
      'نوع الطارئ',
      'مستوى الخطورة',
      'الغرفة المتأثرة',
      'الوصف التفصيلي',
      'الإجراء المتخذ',
      'نتيجة الإجراء',
      'هل تم حل المشكلة؟',
      'ملاحظات المتابعة',
      'توقيع المسؤول'
    ])
  }
};

// ─────────────────────────────────────────────────────────
// STAGE CONFIGURATION
// ─────────────────────────────────────────────────────────

var STAGES = [
  { id: 'setup',     label: 'استلام الأكياس',      dayStart: 1,  dayEnd: 1  },
  { id: 'spawn_run', label: 'انتشار الميسيليوم',   dayStart: 2,  dayEnd: 16 },
  { id: 'casing',    label: 'التغطية',              dayStart: 17, dayEnd: 17 },
  { id: 'case_run',  label: 'نمو الميسيليوم',      dayStart: 18, dayEnd: 24 },
  { id: 'pinning',   label: 'تحفيز الإثمار',       dayStart: 25, dayEnd: 26 },
  { id: 'waiting',   label: 'انتظار الرؤوس',       dayStart: 27, dayEnd: 31 },
  { id: 'harvest',   label: 'الحصاد',              dayStart: 32, dayEnd: 999 }
];

var STAGE_TARGETS = {
  spawn_run: {
    air_temp:     [23, 24],
    compost_temp: [24, 25],
    humidity:     [90, 95],
    co2:          [10000, 15000]
  },
  case_run: {
    air_temp:     [23, 24],
    compost_temp: [24, 25],
    humidity:     [90, 95],
    co2:          [5000, 7500]
  },
  pinning: {
    air_temp:     [16, 18],
    humidity:     [95, 100],
    co2:          [800, 1200]
  },
  waiting: {
    air_temp:     [18, 20],
    humidity:     [90, 95],
    co2:          [1000, 3000]
  },
  harvest: {
    air_temp:     [18, 20],
    humidity:     [90, 95],
    co2:          [1000, 3000]
  },
  setup: {},
  casing: {},
  between: {},
  emergency: {}
};

// ─────────────────────────────────────────────────────────
// SETUP
// ─────────────────────────────────────────────────────────

/**
 * Creates all required sheets with headers.
 * Run once from the Apps Script editor.
 */
function setupEverything() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // 1. Cycles tab
  _ensureSheet(ss, CYCLES_TAB, CYCLES_COLUMNS);

  // 2. Checklist tabs
  var keys = Object.keys(CHECKLISTS);
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    var def = CHECKLISTS[key];
    _ensureSheet(ss, def.tab, def.fields);
  }

  SpreadsheetApp.getUi().alert('✅ تم إعداد جميع الأوراق بنجاح! MAKNABIS ' + VERSION);
}

/**
 * Ensures a sheet exists with the given headers in row 1.
 * If the sheet doesn't exist, creates it.
 * Always sets row 1 headers (non-destructive to data below).
 */
function _ensureSheet(ss, name, headers) {
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
  }
  // Set headers in row 1
  var range = sheet.getRange(1, 1, 1, headers.length);
  range.setValues([headers]);
  range.setFontWeight('bold');
  range.setBackground('#1a5276');
  range.setFontColor('#ffffff');
  sheet.setFrozenRows(1);
  return sheet;
}

// ─────────────────────────────────────────────────────────
// HTTP HANDLERS
// ─────────────────────────────────────────────────────────

function doGet(e) {
  try {
    var params = e.parameter || {};
    var key    = params.key   || '';
    var mode   = params.mode  || '';

    // Health check — no auth needed
    if (params.ping === '1') {
      return jsonOut({ ok: true, version: VERSION, ts: new Date().toISOString() });
    }

    // cycle_active — no auth needed (lightweight)
    if (mode === 'cycle_active') {
      return jsonOut({ ok: true, active: getActiveCycle() });
    }

    // All other modes require key
    if (key !== DASHBOARD_KEY) {
      return jsonOut({ ok: false, error: 'Unauthorized' }, 403);
    }

    if (mode === 'dashboard') {
      var cycleId = params.cycle_id || null;
      return jsonOut(buildDashboardPayload(cycleId));
    }

    if (mode === 'room') {
      var cycleId = params.cycle_id || null;
      return jsonOut(buildRoomPayload(cycleId));
    }

    if (mode === 'cycles') {
      return jsonOut({ ok: true, cycles: listCycles(), active: getActiveCycle() });
    }

    if (mode === 'recent') {
      var sheet    = params.sheet    || '';
      var cycleId  = params.cycle_id || null;
      var limit    = parseInt(params.limit || '50', 10);
      return jsonOut(buildRecentPayload(sheet, cycleId, limit));
    }

    return jsonOut({ ok: false, error: 'Unknown mode: ' + mode }, 400);

  } catch (err) {
    return jsonOut({ ok: false, error: err.message, stack: err.stack }, 500);
  }
}

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents || '{}');
    var type = body.type || '';
    var key  = body.key  || body.password || '';

    // Checklist append — requires key
    if (type === 'checklist') {
      if (key !== DASHBOARD_KEY) return jsonOut({ ok: false, error: 'Unauthorized' }, 403);
      return jsonOut(appendToChecklist(body.data || body));
    }

    // Cycle create
    if (type === 'cycle_create') {
      if (key !== DASHBOARD_KEY) return jsonOut({ ok: false, error: 'Unauthorized' }, 403);
      return jsonOut(createCycle(body.data || body));
    }

    // Set active cycle
    if (type === 'cycle_set_active') {
      if (key !== DASHBOARD_KEY) return jsonOut({ ok: false, error: 'Unauthorized' }, 403);
      return jsonOut(setActiveCycle(body.cycle_id || (body.data && body.data.cycle_id)));
    }

    // Close cycle
    if (type === 'cycle_close') {
      if (key !== DASHBOARD_KEY) return jsonOut({ ok: false, error: 'Unauthorized' }, 403);
      return jsonOut(closeCycle(body.cycle_id || (body.data && body.data.cycle_id)));
    }

    // Delete row from checklist
    if (type === 'delete_row') {
      if (key !== DASHBOARD_KEY) return jsonOut({ ok: false, error: 'Unauthorized' }, 403);
      return jsonOut(deleteRowFromChecklist(body.sheet, body.row_number));
    }

    return jsonOut({ ok: false, error: 'Unknown type: ' + type }, 400);

  } catch (err) {
    return jsonOut({ ok: false, error: err.message, stack: err.stack }, 500);
  }
}

// ─────────────────────────────────────────────────────────
// JSON OUTPUT HELPER
// ─────────────────────────────────────────────────────────

function jsonOut(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ─────────────────────────────────────────────────────────
// CYCLE CRUD
// ─────────────────────────────────────────────────────────

/**
 * Lists all cycles from the cycles tab.
 * Returns array of objects keyed by column headers.
 */
function listCycles() {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(CYCLES_TAB);
  if (!sheet) return [];

  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];

  var headers = sheet.getRange(1, 1, 1, CYCLES_COLUMNS.length).getValues()[0];
  var data    = sheet.getRange(2, 1, lastRow - 1, CYCLES_COLUMNS.length).getValues();

  var cycles = [];
  for (var i = 0; i < data.length; i++) {
    var row = data[i];
    // Skip completely empty rows
    if (!row[0] && !row[1]) continue;
    var obj = {};
    for (var j = 0; j < headers.length; j++) {
      var val = row[j];
      if (val instanceof Date) {
        obj[headers[j]] = Utilities.formatDate(val, Session.getScriptTimeZone(), 'yyyy-MM-dd');
      } else {
        obj[headers[j]] = val;
      }
    }
    // Attach row number for updates
    obj._row = i + 2;
    // Expose english key aliases for convenience
    obj.cycle_id   = obj['رقم الدورة'];
    obj.name       = obj['الاسم'];
    obj.start_date = obj['تاريخ البدء'];
    obj.expected_harvest = obj['الحصاد المتوقع'];
    obj.room       = obj['الغرفة'];
    obj.substrate  = obj['نوع الركيزة'];
    obj.bag_count  = obj['عدد الأكياس'];
    obj.status     = obj['الحالة'];
    obj.notes      = obj['ملاحظات'];
    obj.created_at = obj['تاريخ الإنشاء'];
    cycles.push(obj);
  }
  return cycles;
}

/**
 * Returns the currently active cycle object, or null.
 */
function getActiveCycle() {
  var cycles = listCycles();
  for (var i = 0; i < cycles.length; i++) {
    if (cycles[i].status === 'active') return cycles[i];
  }
  return null;
}

/**
 * Generates the next cycle ID in format B-YYYY-NN
 */
function _nextCycleId() {
  var year   = new Date().getFullYear();
  var cycles = listCycles();
  var max    = 0;
  var prefix = 'B-' + year + '-';
  for (var i = 0; i < cycles.length; i++) {
    var id = cycles[i].cycle_id || '';
    if (id.indexOf(prefix) === 0) {
      var num = parseInt(id.replace(prefix, ''), 10);
      if (!isNaN(num) && num > max) max = num;
    }
  }
  var nn = String(max + 1);
  while (nn.length < 2) nn = '0' + nn;
  return prefix + nn;
}

/**
 * Creates a new cycle and optionally sets it as active.
 * data: { name, start_date, expected_harvest, room, substrate, bag_count, notes, set_active }
 */
function createCycle(data) {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(CYCLES_TAB);
  if (!sheet) throw new Error('Cycles tab not found');

  var cycleId = _nextCycleId();
  var status  = data.set_active ? 'active' : 'planning';
  var now     = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');

  var startDate = data.start_date || Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
  var expectedHarvest = data.expected_harvest || '';

  // If setting active, demote others
  if (data.set_active) {
    _demoteActiveCycles();
  }

  var row = [
    cycleId,
    data.name            || '',
    startDate,
    expectedHarvest,
    data.room            || '',
    data.substrate       || '',
    data.bag_count       || '',
    status,
    data.notes           || '',
    now
  ];

  sheet.appendRow(row);

  return { ok: true, cycle_id: cycleId, status: status };
}

/**
 * Sets a cycle as active; demotes all others to 'planning'.
 */
function setActiveCycle(cycleId) {
  if (!cycleId) return { ok: false, error: 'cycle_id required' };

  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(CYCLES_TAB);
  if (!sheet) throw new Error('Cycles tab not found');

  var cycles = listCycles();
  var found  = false;
  var statusCol = CYCLES_COLUMNS.indexOf('الحالة') + 1; // 1-based

  for (var i = 0; i < cycles.length; i++) {
    var c = cycles[i];
    if (c.cycle_id === cycleId) {
      sheet.getRange(c._row, statusCol).setValue('active');
      found = true;
    } else if (c.status === 'active') {
      sheet.getRange(c._row, statusCol).setValue('planning');
    }
  }

  if (!found) return { ok: false, error: 'Cycle not found: ' + cycleId };
  return { ok: true, cycle_id: cycleId, status: 'active' };
}

/**
 * Closes a cycle (status → 'closed').
 */
function closeCycle(cycleId) {
  if (!cycleId) return { ok: false, error: 'cycle_id required' };

  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(CYCLES_TAB);
  if (!sheet) throw new Error('Cycles tab not found');

  var cycles    = listCycles();
  var statusCol = CYCLES_COLUMNS.indexOf('الحالة') + 1;

  for (var i = 0; i < cycles.length; i++) {
    if (cycles[i].cycle_id === cycleId) {
      sheet.getRange(cycles[i]._row, statusCol).setValue('closed');
      return { ok: true, cycle_id: cycleId, status: 'closed' };
    }
  }
  return { ok: false, error: 'Cycle not found: ' + cycleId };
}

/**
 * Internal: sets all active cycles to 'planning'.
 */
function _demoteActiveCycles() {
  var ss     = SpreadsheetApp.getActiveSpreadsheet();
  var sheet  = ss.getSheetByName(CYCLES_TAB);
  if (!sheet) return;

  var cycles    = listCycles();
  var statusCol = CYCLES_COLUMNS.indexOf('الحالة') + 1;

  for (var i = 0; i < cycles.length; i++) {
    if (cycles[i].status === 'active') {
      sheet.getRange(cycles[i]._row, statusCol).setValue('planning');
    }
  }
}

// ─────────────────────────────────────────────────────────
// CHECKLIST OPERATIONS
// ─────────────────────────────────────────────────────────

/**
 * Appends a row to a checklist tab.
 * data must include: sheet_key (e.g. 'spawn_run'), plus all field values.
 */
function appendToChecklist(data) {
  var sheetKey = data.sheet_key || data.sheet || '';
  var def      = CHECKLISTS[sheetKey];
  if (!def) return { ok: false, error: 'Unknown sheet_key: ' + sheetKey };

  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(def.tab);
  if (!sheet) return { ok: false, error: 'Tab not found: ' + def.tab };

  var fields  = def.fields;
  var rowData = [];
  for (var i = 0; i < fields.length; i++) {
    var fieldName = fields[i];
    var val       = data[fieldName];
    if (val === undefined || val === null) val = '';
    rowData.push(val);
  }

  sheet.appendRow(rowData);
  var newRow = sheet.getLastRow();

  return { ok: true, row: newRow, sheet: def.tab };
}

/**
 * Reads rows from a checklist tab, optionally filtered by cycle_id.
 * Returns headers, rows with row numbers.
 */
function buildRecentPayload(sheetKeyOrTab, cycleId, limit) {
  limit = limit || 50;

  // Resolve key → tab name
  var tabName = sheetKeyOrTab;
  if (CHECKLISTS[sheetKeyOrTab]) {
    tabName = CHECKLISTS[sheetKeyOrTab].tab;
  }

  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(tabName);
  if (!sheet) return { ok: false, error: 'Sheet not found: ' + tabName };

  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return { ok: true, headers: [], rows: [], sheet: tabName };

  var lastCol = sheet.getLastColumn();
  var headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  var allData = sheet.getRange(2, 1, lastRow - 1, lastCol).getValues();

  // Find cycle_id column index
  var cycleIdColIdx = -1;
  for (var i = 0; i < headers.length; i++) {
    if (headers[i] === 'رقم الدورة') { cycleIdColIdx = i; break; }
  }

  var rows = [];
  for (var r = allData.length - 1; r >= 0; r--) {
    var rowValues = allData[r];
    // Filter by cycle_id if provided
    if (cycleId && cycleIdColIdx >= 0) {
      if (rowValues[cycleIdColIdx] !== cycleId) continue;
    }
    // Skip blank rows
    if (!rowValues[0] && !rowValues[1] && !rowValues[2]) continue;

    // Serialize dates
    var serialized = rowValues.map(function(v) {
      return v instanceof Date ? Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss') : v;
    });

    rows.push({ row: r + 2, values: serialized });
    if (rows.length >= limit) break;
  }

  return { ok: true, headers: headers, rows: rows, sheet: tabName };
}

/**
 * Deletes a specific row from a checklist tab.
 */
function deleteRowFromChecklist(sheetKeyOrTab, rowNumber) {
  rowNumber = parseInt(rowNumber, 10);
  if (isNaN(rowNumber) || rowNumber < 2) {
    return { ok: false, error: 'Invalid row_number (must be >= 2)' };
  }

  // Resolve tab name
  var tabName = sheetKeyOrTab;
  if (CHECKLISTS[sheetKeyOrTab]) {
    tabName = CHECKLISTS[sheetKeyOrTab].tab;
  }

  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(tabName);
  if (!sheet) return { ok: false, error: 'Sheet not found: ' + tabName };

  var lastRow = sheet.getLastRow();
  if (rowNumber > lastRow) {
    return { ok: false, error: 'Row ' + rowNumber + ' does not exist (last row: ' + lastRow + ')' };
  }

  sheet.deleteRow(rowNumber);
  return { ok: true, deleted: rowNumber, sheet: tabName };
}

// ─────────────────────────────────────────────────────────
// STAGE DETECTION
// ─────────────────────────────────────────────────────────

/**
 * Calculates the day number given a start date string (yyyy-MM-dd).
 */
function _calcDayNumber(startDateStr) {
  if (!startDateStr) return 1;
  var start = new Date(startDateStr);
  var today = new Date();
  // Zero out time
  start.setHours(0, 0, 0, 0);
  today.setHours(0, 0, 0, 0);
  var diff = Math.floor((today - start) / (1000 * 60 * 60 * 24)) + 1;
  return diff < 1 ? 1 : diff;
}

/**
 * Returns stage object for a given day number.
 */
function _detectStage(dayNumber) {
  for (var i = 0; i < STAGES.length; i++) {
    var s = STAGES[i];
    if (dayNumber >= s.dayStart && dayNumber <= s.dayEnd) return s;
  }
  // Fallback: harvest
  return STAGES[STAGES.length - 1];
}

// ─────────────────────────────────────────────────────────
// ROOM PAYLOAD
// ─────────────────────────────────────────────────────────

/**
 * Builds the room monitoring payload for the mobile app.
 */
function buildRoomPayload(cycleId) {
  var cycle = cycleId ? _getCycleById(cycleId) : getActiveCycle();
  if (!cycle) return { ok: false, error: 'No active cycle found' };

  var dayNumber  = _calcDayNumber(cycle.start_date);
  var stage      = _detectStage(dayNumber);
  var stageId    = stage.id;
  var stageLabel = stage.label;
  var targets    = STAGE_TARGETS[stageId] || {};
  var bagCount   = parseInt(cycle.bag_count, 10) || 0;

  // Fetch latest readings from the stage's checklist tab
  var latestReading = _getLatestReading(stageId, cycle.cycle_id);

  // Harvest stats (from harvest tab)
  var harvestData = _getHarvestStats(cycle.cycle_id);

  // Emergency count
  var emergencyCount = _countRows('emergency', cycle.cycle_id);

  // Alerts
  var alerts = _generateAlerts(latestReading, targets, stageId, dayNumber, cycle);

  return {
    ok:              true,
    cycle:           cycle,
    day_number:      dayNumber,
    stage_id:        stageId,
    stage_label:     stageLabel,
    bag_count:       bagCount,
    latest_reading:  latestReading,
    targets:         targets,
    harvest_today:   harvestData.today,
    harvest_total:   harvestData.total,
    alerts:          alerts,
    emergency_count: emergencyCount,
    generated_at:    new Date().toISOString()
  };
}

/**
 * Gets latest reading rows (morning/noon/evening) from a checklist.
 */
function _getLatestReading(stageId, cycleId) {
  var def = CHECKLISTS[stageId];
  if (!def) return null;

  var result = buildRecentPayload(stageId, cycleId, 3);
  if (!result.ok || !result.rows.length) return null;

  var headers = result.headers;
  var rows    = result.rows;

  // The most recent row is first (we reversed in buildRecentPayload)
  var latestRow    = rows[0].values;
  var latestObj    = {};
  for (var i = 0; i < headers.length; i++) {
    latestObj[headers[i]] = latestRow[i];
  }

  // Extract per-session env data
  var reading = {
    date:     latestObj['التاريخ'] || '',
    worker:   latestObj['العامل']  || '',
    morning:  _extractSession(latestObj, 'am'),
    noon:     _extractSession(latestObj, 'noon'),
    evening:  _extractSession(latestObj, 'pm')
  };

  return reading;
}

/**
 * Extracts environment readings for a session prefix (am/noon/pm).
 */
function _extractSession(obj, prefix) {
  var session = {};
  var keys    = ['air_temp', 'compost_temp', 'humidity', 'co2', 'notes'];
  for (var i = 0; i < keys.length; i++) {
    var k = prefix + '_' + keys[i];
    if (obj[k] !== undefined) session[keys[i]] = obj[k];
  }
  return Object.keys(session).length ? session : null;
}

/**
 * Returns harvest stats: today's kg and total kg for the cycle.
 */
function _getHarvestStats(cycleId) {
  var result = buildRecentPayload('harvest', cycleId, 500);
  if (!result.ok || !result.rows.length) return { today: 0, total: 0 };

  var headers = result.headers;
  var kg1Idx  = headers.indexOf('harvest_kg_1');
  var kg2Idx  = headers.indexOf('harvest_kg_2');
  var dateIdx = headers.indexOf('التاريخ');

  if (kg1Idx < 0 && kg2Idx < 0) return { today: 0, total: 0 };

  var todayStr = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
  var total    = 0;
  var today    = 0;

  for (var i = 0; i < result.rows.length; i++) {
    var row  = result.rows[i].values;
    var kg1  = parseFloat(row[kg1Idx] || 0) || 0;
    var kg2  = parseFloat(row[kg2Idx] || 0) || 0;
    var sum  = kg1 + kg2;
    total   += sum;

    var rowDate = String(row[dateIdx] || '').substring(0, 10);
    if (rowDate === todayStr) today += sum;
  }

  return { today: Math.round(today * 100) / 100, total: Math.round(total * 100) / 100 };
}

/**
 * Counts rows in a checklist for a cycle.
 */
function _countRows(sheetKey, cycleId) {
  var result = buildRecentPayload(sheetKey, cycleId, 1000);
  if (!result.ok) return 0;
  return result.rows.length;
}

/**
 * Generates alerts based on latest readings vs targets.
 */
function _generateAlerts(latestReading, targets, stageId, dayNumber, cycle) {
  var alerts = [];

  if (!latestReading) {
    alerts.push({ level: 'warning', message: 'لا توجد قراءات مسجلة لهذه الدورة اليوم' });
    return alerts;
  }

  var sessions = ['morning', 'noon', 'evening'];
  var sessionLabels = { morning: 'الصباحية', noon: 'الظهرية', evening: 'المسائية' };

  for (var s = 0; s < sessions.length; s++) {
    var session = sessions[s];
    var data    = latestReading[session];
    if (!data) continue;

    _checkRange(alerts, data.air_temp,     targets.air_temp,     'درجة الهواء ' + sessionLabels[session]);
    _checkRange(alerts, data.compost_temp, targets.compost_temp, 'درجة الكومبوست ' + sessionLabels[session]);
    _checkRange(alerts, data.humidity,     targets.humidity,     'الرطوبة ' + sessionLabels[session]);
    _checkRange(alerts, data.co2,          targets.co2,          'ثاني أكسيد الكربون ' + sessionLabels[session]);
  }

  // Stage-specific alerts
  if (stageId === 'spawn_run' && dayNumber > 16) {
    alerts.push({ level: 'info', message: 'يجب الانتقال إلى مرحلة التغطية' });
  }

  return alerts;
}

/**
 * Adds an alert if value is out of [min, max] range.
 */
function _checkRange(alerts, value, range, label) {
  if (!range || value === '' || value === null || value === undefined) return;
  var v   = parseFloat(value);
  if (isNaN(v)) return;
  var min = range[0];
  var max = range[1];
  if (v < min) {
    alerts.push({ level: 'warning', message: label + ': ' + v + ' أقل من الحد الأدنى ' + min });
  } else if (v > max) {
    alerts.push({ level: 'danger', message: label + ': ' + v + ' أعلى من الحد الأقصى ' + max });
  }
}

/**
 * Gets a cycle by ID.
 */
function _getCycleById(cycleId) {
  var cycles = listCycles();
  for (var i = 0; i < cycles.length; i++) {
    if (cycles[i].cycle_id === cycleId) return cycles[i];
  }
  return null;
}

// ─────────────────────────────────────────────────────────
// DASHBOARD PAYLOAD
// ─────────────────────────────────────────────────────────

/**
 * Builds the full dashboard payload.
 */
function buildDashboardPayload(cycleId) {
  var cycle = cycleId ? _getCycleById(cycleId) : getActiveCycle();

  var kpis          = _buildKpis(cycle);
  var recentReadings = _buildRecentReadings(cycle);
  var alerts         = [];
  var waves          = _buildWaveSummary(cycle);
  var workerActivity = _buildWorkerActivity(cycle);

  if (cycle) {
    var dayNumber = _calcDayNumber(cycle.start_date);
    var stage     = _detectStage(dayNumber);
    var targets   = STAGE_TARGETS[stage.id] || {};
    var latestR   = _getLatestReading(stage.id, cycle.cycle_id);
    alerts        = _generateAlerts(latestR, targets, stage.id, dayNumber, cycle);
  }

  return {
    ok:              true,
    cycle:           cycle,
    kpis:            kpis,
    recent_readings: recentReadings,
    alerts:          alerts,
    waves:           waves,
    worker_activity: workerActivity,
    generated_at:    new Date().toISOString()
  };
}

/**
 * Key Performance Indicators for the dashboard.
 */
function _buildKpis(cycle) {
  if (!cycle) return { error: 'No active cycle' };

  var harvestStats = _getHarvestStats(cycle.cycle_id);
  var dayNumber    = _calcDayNumber(cycle.start_date);
  var stage        = _detectStage(dayNumber);
  var bagCount     = parseInt(cycle.bag_count, 10) || 0;
  var emergencies  = _countRows('emergency', cycle.cycle_id);

  // Efficiency: kg per bag
  var efficiency = bagCount > 0 ? Math.round((harvestStats.total / bagCount) * 1000) / 1000 : 0;

  return {
    day_number:       dayNumber,
    stage_id:         stage.id,
    stage_label:      stage.label,
    bag_count:        bagCount,
    harvest_total_kg: harvestStats.total,
    harvest_today_kg: harvestStats.today,
    efficiency_kg_per_bag: efficiency,
    emergency_count:  emergencies,
    cycle_id:         cycle.cycle_id,
    cycle_name:       cycle.name,
    start_date:       cycle.start_date
  };
}

/**
 * Summarizes recent readings from the current stage.
 */
function _buildRecentReadings(cycle) {
  if (!cycle) return [];

  var dayNumber = _calcDayNumber(cycle.start_date);
  var stage     = _detectStage(dayNumber);
  var result    = buildRecentPayload(stage.id, cycle.cycle_id, 10);

  if (!result.ok || !result.rows.length) return [];

  var headers = result.headers;
  var out     = [];

  for (var i = 0; i < result.rows.length; i++) {
    var rowValues = result.rows[i].values;
    var obj       = {};
    for (var j = 0; j < headers.length; j++) {
      obj[headers[j]] = rowValues[j];
    }
    obj._row = result.rows[i].row;
    out.push(obj);
  }

  return out;
}

/**
 * Summarizes harvest waves.
 * A "wave" is a group of consecutive harvest entries separated by between_waves entries.
 */
function _buildWaveSummary(cycle) {
  if (!cycle) return [];

  var result = buildRecentPayload('harvest', cycle.cycle_id, 500);
  if (!result.ok || !result.rows.length) return [];

  var headers = result.headers;
  var kg1Idx  = headers.indexOf('harvest_kg_1');
  var kg2Idx  = headers.indexOf('harvest_kg_2');
  var dateIdx = headers.indexOf('التاريخ');

  // Reverse to chronological order
  var rows = result.rows.slice().reverse();

  var waves   = [];
  var current = { wave: 1, dates: [], total: 0 };

  for (var i = 0; i < rows.length; i++) {
    var row  = rows[i].values;
    var kg1  = parseFloat(row[kg1Idx] || 0) || 0;
    var kg2  = parseFloat(row[kg2Idx] || 0) || 0;
    var date = String(row[dateIdx] || '').substring(0, 10);

    if (current.dates.length > 0) {
      // Check for a gap > 5 days = new wave
      var lastDate    = new Date(current.dates[current.dates.length - 1]);
      var thisDate    = new Date(date);
      var gapDays     = Math.floor((thisDate - lastDate) / (1000 * 60 * 60 * 24));
      if (gapDays > 5) {
        waves.push({ wave: current.wave, total_kg: Math.round(current.total * 100) / 100, days: current.dates.length });
        current = { wave: current.wave + 1, dates: [], total: 0 };
      }
    }

    current.dates.push(date);
    current.total += kg1 + kg2;
  }

  if (current.dates.length > 0) {
    waves.push({ wave: current.wave, total_kg: Math.round(current.total * 100) / 100, days: current.dates.length });
  }

  return waves;
}

/**
 * Summarizes worker activity (number of entries per worker).
 */
function _buildWorkerActivity(cycle) {
  if (!cycle) return [];

  var workerCounts = {};
  var sheetKeys    = Object.keys(CHECKLISTS);

  for (var k = 0; k < sheetKeys.length; k++) {
    var result = buildRecentPayload(sheetKeys[k], cycle.cycle_id, 500);
    if (!result.ok || !result.rows.length) continue;

    var workerIdx = result.headers.indexOf('العامل');
    if (workerIdx < 0) continue;

    for (var r = 0; r < result.rows.length; r++) {
      var worker = String(result.rows[r].values[workerIdx] || '').trim();
      if (!worker) continue;
      workerCounts[worker] = (workerCounts[worker] || 0) + 1;
    }
  }

  var out = [];
  var workers = Object.keys(workerCounts);
  for (var w = 0; w < workers.length; w++) {
    out.push({ worker: workers[w], entries: workerCounts[workers[w]] });
  }

  // Sort descending by entries
  out.sort(function(a, b) { return b.entries - a.entries; });
  return out;
}

// ─────────────────────────────────────────────────────────
// UTILITIES
// ─────────────────────────────────────────────────────────

/**
 * Stores a value in script properties.
 */
function _setProp(key, value) {
  PropertiesService.getScriptProperties().setProperty(key, JSON.stringify(value));
}

/**
 * Gets a value from script properties.
 */
function _getProp(key, defaultVal) {
  var raw = PropertiesService.getScriptProperties().getProperty(key);
  if (raw === null || raw === undefined) return defaultVal;
  try { return JSON.parse(raw); } catch (e) { return raw; }
}

/**
 * Formats a date as yyyy-MM-dd.
 */
function _fmtDate(d) {
  if (!d) return '';
  if (!(d instanceof Date)) d = new Date(d);
  return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd');
}

/**
 * Formats a date as yyyy-MM-dd HH:mm:ss.
 */
function _fmtDateTime(d) {
  if (!d) return '';
  if (!(d instanceof Date)) d = new Date(d);
  return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
}

// ─────────────────────────────────────────────────────────
// MENU (Optional: run from the spreadsheet)
// ─────────────────────────────────────────────────────────

function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('🍄 MAKNABIS')
    .addItem('⚙️ إعداد الجداول', 'setupEverything')
    .addSeparator()
    .addItem('📊 الدورة النشطة', 'showActiveCycle')
    .addItem('🔄 قائمة الدورات', 'showCyclesList')
    .addSeparator()
    .addItem('ℹ️ معلومات النظام', 'showSystemInfo')
    .addToUi();
}

function showActiveCycle() {
  var cycle = getActiveCycle();
  var msg   = cycle
    ? 'الدورة النشطة: ' + cycle.cycle_id + '\nالاسم: ' + cycle.name + '\nتاريخ البدء: ' + cycle.start_date + '\nاليوم: ' + _calcDayNumber(cycle.start_date)
    : 'لا توجد دورة نشطة حالياً.';
  SpreadsheetApp.getUi().alert(msg);
}

function showCyclesList() {
  var cycles = listCycles();
  if (!cycles.length) {
    SpreadsheetApp.getUi().alert('لا توجد دورات مسجلة.');
    return;
  }
  var lines = cycles.map(function(c) {
    return c.cycle_id + ' | ' + c.name + ' | ' + c.status;
  });
  SpreadsheetApp.getUi().alert('الدورات:\n' + lines.join('\n'));
}

function showSystemInfo() {
  var info = [
    'MAKNABIS System Info',
    '─────────────────────',
    'Version: ' + VERSION,
    'Checklists version: ' + CHECKLISTS_VERSION,
    'Timezone: ' + Session.getScriptTimeZone(),
    'Spreadsheet: ' + SpreadsheetApp.getActiveSpreadsheet().getName(),
    'Generated: ' + new Date().toISOString()
  ].join('\n');
  SpreadsheetApp.getUi().alert(info);
}

// ─────────────────────────────────────────────────────────
// TEST HELPERS (run manually from editor)
// ─────────────────────────────────────────────────────────

/**
 * Quick test: logs the room payload for the active cycle.
 */
function testRoomPayload() {
  var payload = buildRoomPayload(null);
  Logger.log(JSON.stringify(payload, null, 2));
}

/**
 * Quick test: logs the dashboard payload.
 */
function testDashboardPayload() {
  var payload = buildDashboardPayload(null);
  Logger.log(JSON.stringify(payload, null, 2));
}

/**
 * Quick test: creates a sample cycle.
 */
function testCreateCycle() {
  var result = createCycle({
    name:       'دورة تجريبية',
    start_date: _fmtDate(new Date()),
    room:       'غرفة 1',
    substrate:  'قش القمح',
    bag_count:  200,
    notes:      'دورة اختبار',
    set_active: true
  });
  Logger.log(JSON.stringify(result));
}

/**
 * Quick test: appends a sample spawn_run reading.
 */
function testAppendSpawnRun() {
  var result = appendToChecklist({
    sheet_key:   'spawn_run',
    'التاريخ':   _fmtDate(new Date()),
    'العامل':    'أحمد',
    'رقم الدورة': 'B-2026-01',
    'القراءة الصباحية 06:00': READ_AM,
    'am_air_temp':     23.5,
    'am_compost_temp': 24.1,
    'am_humidity':     92,
    'am_co2':          12000,
    'am_notes':        'كل شيء طبيعي',
    'القراءة الظهرية 14:00': READ_NOON,
    'noon_air_temp':     23.8,
    'noon_compost_temp': 24.3,
    'noon_humidity':     91,
    'noon_co2':          13500,
    'noon_notes':        '',
    'القراءة المسائية 20:00': READ_PM,
    'pm_air_temp':     23.2,
    'pm_compost_temp': 24.0,
    'pm_humidity':     93,
    'pm_co2':          11000,
    'pm_notes':        '',
    'ملاحظات عامة': 'يوم جيد',
    'تقييم اليوم':  'ممتاز'
  });
  Logger.log(JSON.stringify(result));
}

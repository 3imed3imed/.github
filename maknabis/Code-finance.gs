// ============================================================
//  MAKNABIS – Finance Backend  (Google Apps Script)
//  Version : v2_cycles
//  Handles : Purchases, Sales, Construction, Operating,
//             Payroll, Production, Inventory + Cycle mgmt
// ============================================================

const FINANCE_VERSION = 'v2_cycles';
const PASSWORD        = 'FARM2026';
const GROWING_API_URL = '';          // set to deployed growing-side URL when ready

// ── Sheet tab names ─────────────────────────────────────────
const SHEETS = {
  PURCHASES   : 'المشتريات',
  SALES       : 'المبيعات',
  CONSTRUCTION: 'البناء',
  OPERATING   : 'مصاريف التشغيل',
  PAYROLL     : 'الأجور',
  PRODUCTION  : 'دورات الإنتاج',
  INVENTORY   : 'المخزون'
};

const CYCLES_TAB = '🔄 الدورات';

// ── Column definitions for each finance sheet ────────────────
const SHEET_HEADERS = {
  [SHEETS.PURCHASES]   : ['التاريخ','العامل','رقم الدورة','الصنف','المورد','الكمية','الوحدة','السعر/وحدة','الإجمالي','الفئة','ملاحظات'],
  [SHEETS.SALES]       : ['التاريخ','العامل','رقم الدورة','الصنف','العميل','الكمية_كغ','سعر_كغ','الإجمالي','طريقة_الدفع','قناة_البيع','ملاحظات'],
  [SHEETS.CONSTRUCTION]: ['التاريخ','العامل','رقم الدورة','البند','المورد','الكمية','الوحدة','التكلفة','الإجمالي','ملاحظات'],
  [SHEETS.OPERATING]   : ['التاريخ','العامل','رقم الدورة','الصنف','الفئة','المبلغ','طريقة_الدفع','ملاحظات'],
  [SHEETS.PAYROLL]     : ['التاريخ','العامل','رقم الدورة','اسم_العامل','الفترة','المبلغ','نوع_الراتب','ملاحظات'],
  [SHEETS.PRODUCTION]  : ['التاريخ','العامل','رقم الدورة','وزن_الحصاد_كغ','نوع_الغلة','السعر_كغ','الإيرادات','ملاحظات'],
  [SHEETS.INVENTORY]   : ['التاريخ','العامل','رقم الدورة','الصنف','الكمية','الوحدة','نوع_الحركة','ملاحظات']
};

// ── Cycle columns (mirrors growing side) ────────────────────
const CYCLE_HEADERS = [
  'رقم الدورة','الاسم','تاريخ البدء','الحصاد المتوقع',
  'الغرفة','نوع الركيزة','عدد الأكياس','الحالة','ملاحظات','تاريخ الإنشاء'
];

// Col indices (0-based) used in sumSheet / stats
const COL = {
  DATE      : 0,   // A – التاريخ
  WORKER    : 1,   // B – العامل
  CYCLE     : 2,   // C – رقم الدورة
  // sheet-specific amount columns (0-based)
  PURCHASES_TOTAL    : 8,   // I
  SALES_TOTAL        : 7,   // H
  CONSTRUCTION_TOTAL : 8,   // I
  OPERATING_AMOUNT   : 5,   // F
  PAYROLL_AMOUNT     : 5,   // F
  PRODUCTION_KG      : 3,   // D  وزن_الحصاد_كغ
  PRODUCTION_REVENUE : 6    // G  الإيرادات
};

// ============================================================
//  ENTRY POINT
// ============================================================
function doPost(e) {
  try {
    const body   = JSON.parse(e.postData.contents);
    const action = body.action || '';
    const data   = body.data   || {};

    // Auth gate (checkAuth itself is exempt from password check internally)
    if (action !== 'checkAuth') {
      if (data.password !== PASSWORD) {
        return jsonOut({ ok: false, error: 'كلمة مرور غير صحيحة' });
      }
    }

    switch (action) {
      case 'checkAuth'       : return handleCheckAuth(data);
      case 'addPurchase'     : return handleAdd(SHEETS.PURCHASES,    data, buildPurchaseRow);
      case 'addSale'         : return handleAdd(SHEETS.SALES,        data, buildSaleRow);
      case 'addConstruction' : return handleAdd(SHEETS.CONSTRUCTION, data, buildConstructionRow);
      case 'addOperating'    : return handleAdd(SHEETS.OPERATING,    data, buildOperatingRow);
      case 'addPayroll'      : return handleAdd(SHEETS.PAYROLL,      data, buildPayrollRow);
      case 'addProduction'   : return handleAdd(SHEETS.PRODUCTION,   data, buildProductionRow);
      case 'addInventory'    : return handleAdd(SHEETS.INVENTORY,    data, buildInventoryRow);
      case 'getTodayStats'   : return handleGetTodayStats(data);
      case 'getRecent'       : return handleGetRecent(data);
      case 'deleteRow'       : return handleDeleteRow(data);
      case 'listCycles'      : return handleListCycles(data);
      case 'createCycle'     : return handleCreateCycle(data);
      case 'setActiveCycle'  : return handleSetActiveCycle(data);
      case 'getActiveCycle'  : return handleGetActiveCycle(data);
      case 'setupEverything' : return handleSetupEverything();
      default:
        return jsonOut({ ok: false, error: 'إجراء غير معروف: ' + action });
    }
  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

// Also expose via GET for quick health-check
function doGet(e) {
  return jsonOut({ ok: true, version: FINANCE_VERSION, service: 'finance' });
}

// ============================================================
//  SETUP
// ============================================================
function handleSetupEverything() {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    // Create / verify finance sheets
    Object.values(SHEETS).forEach(name => {
      ensureSheet(ss, name, SHEET_HEADERS[name]);
    });

    // Create / verify cycles tab
    ensureSheet(ss, CYCLES_TAB, CYCLE_HEADERS);

    return jsonOut({ ok: true, data: { message: 'تم الإعداد بنجاح', version: FINANCE_VERSION }, version: FINANCE_VERSION });
  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

function ensureSheet(ss, name, headers) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
  }
  if (sheet.getLastRow() === 0) {
    const headerRow = sheet.getRange(1, 1, 1, headers.length);
    headerRow.setValues([headers]);
    headerRow.setFontWeight('bold');
    headerRow.setBackground('#34a853');
    headerRow.setFontColor('#ffffff');
    sheet.setFrozenRows(1);
    sheet.setRightToLeft(true);
  }
  return sheet;
}

// ============================================================
//  AUTH
// ============================================================
function handleCheckAuth(data) {
  try {
    if (data.password !== PASSWORD) {
      return jsonOut({ ok: false, error: 'كلمة مرور غير صحيحة' });
    }
    const activeCycle = getActiveCycleData();
    return jsonOut({
      ok  : true,
      data: { version: FINANCE_VERSION, active_cycle: activeCycle },
      version: FINANCE_VERSION
    });
  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

// ============================================================
//  ADD ROW HANDLERS
// ============================================================
function handleAdd(sheetName, data, buildFn) {
  try {
    const ss    = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(sheetName);
    if (!sheet) throw new Error('الورقة غير موجودة: ' + sheetName);

    const row       = buildFn(data);
    const lastRow   = sheet.getLastRow();
    const newRow    = lastRow + 1;
    sheet.getRange(newRow, 1, 1, row.length).setValues([row]);

    return jsonOut({
      ok  : true,
      data: { row: newRow, inserted: row },
      version: FINANCE_VERSION
    });
  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

// ── Row builders ─────────────────────────────────────────────

function buildPurchaseRow(d) {
  const qty   = parseFloat(d.quantity  || 0);
  const price = parseFloat(d.unitPrice || 0);
  return [
    d.date       || getTodayStr(),
    d.workerName || '',
    d.cycleId    || '',
    d.item       || '',
    d.supplier   || '',
    qty,
    d.unit       || '',
    price,
    qty * price,
    d.category   || '',
    d.notes      || ''
  ];
}

function buildSaleRow(d) {
  const kg    = parseFloat(d.weightKg || 0);
  const price = parseFloat(d.priceKg  || 0);
  return [
    d.date          || getTodayStr(),
    d.workerName    || '',
    d.cycleId       || '',
    d.item          || '',
    d.customer      || '',
    kg,
    price,
    kg * price,
    d.paymentMethod || '',
    d.salesChannel  || '',
    d.notes         || ''
  ];
}

function buildConstructionRow(d) {
  const qty  = parseFloat(d.quantity || 0);
  const cost = parseFloat(d.cost     || 0);
  return [
    d.date       || getTodayStr(),
    d.workerName || '',
    d.cycleId    || '',
    d.item       || '',
    d.supplier   || '',
    qty,
    d.unit       || '',
    cost,
    qty * cost,
    d.notes      || ''
  ];
}

function buildOperatingRow(d) {
  return [
    d.date          || getTodayStr(),
    d.workerName    || '',
    d.cycleId       || '',
    d.item          || '',
    d.category      || '',
    parseFloat(d.amount || 0),
    d.paymentMethod || '',
    d.notes         || ''
  ];
}

function buildPayrollRow(d) {
  return [
    d.date           || getTodayStr(),
    d.workerName     || '',
    d.cycleId        || '',
    d.employeeName   || d.workerName || '',
    d.period         || '',
    parseFloat(d.amount || 0),
    d.salaryType     || '',
    d.notes          || ''
  ];
}

function buildProductionRow(d) {
  const kg    = parseFloat(d.harvestKg || 0);
  const price = parseFloat(d.priceKg   || 0);
  return [
    d.date       || getTodayStr(),
    d.workerName || '',
    d.cycleId    || '',
    kg,
    d.yieldType  || '',
    price,
    kg * price,
    d.notes      || ''
  ];
}

function buildInventoryRow(d) {
  return [
    d.date         || getTodayStr(),
    d.workerName   || '',
    d.cycleId      || '',
    d.item         || '',
    parseFloat(d.quantity || 0),
    d.unit         || '',
    d.movementType || '',
    d.notes        || ''
  ];
}

// ============================================================
//  TODAY STATS
// ============================================================
function handleGetTodayStats(data) {
  try {
    const ss      = SpreadsheetApp.getActiveSpreadsheet();
    const today   = getTodayStr();
    const cycleId = data.cycleId || getActiveCycleId();

    const todaySales       = sumSheet(ss, SHEETS.SALES,        COL.DATE, COL.SALES_TOTAL,        today,  null);
    const todayPurchases   = sumSheet(ss, SHEETS.PURCHASES,    COL.DATE, COL.PURCHASES_TOTAL,    today,  null);
    const todayOperating   = sumSheet(ss, SHEETS.OPERATING,    COL.DATE, COL.OPERATING_AMOUNT,   today,  null);
    const todayPayroll     = sumSheet(ss, SHEETS.PAYROLL,      COL.DATE, COL.PAYROLL_AMOUNT,     today,  null);

    const cycleSales       = cycleId ? sumSheet(ss, SHEETS.SALES,        COL.DATE, COL.SALES_TOTAL,        null, cycleId) : 0;
    const cyclePurchases   = cycleId ? sumSheet(ss, SHEETS.PURCHASES,    COL.DATE, COL.PURCHASES_TOTAL,    null, cycleId) : 0;
    const cycleOperating   = cycleId ? sumSheet(ss, SHEETS.OPERATING,    COL.DATE, COL.OPERATING_AMOUNT,   null, cycleId) : 0;
    const cyclePayroll     = cycleId ? sumSheet(ss, SHEETS.PAYROLL,      COL.DATE, COL.PAYROLL_AMOUNT,     null, cycleId) : 0;
    const cycleConstruct   = cycleId ? sumSheet(ss, SHEETS.CONSTRUCTION, COL.DATE, COL.CONSTRUCTION_TOTAL, null, cycleId) : 0;
    const cycleProductionR = cycleId ? sumSheet(ss, SHEETS.PRODUCTION,   COL.DATE, COL.PRODUCTION_REVENUE, null, cycleId) : 0;
    const productionKg     = cycleId ? sumSheet(ss, SHEETS.PRODUCTION,   COL.DATE, COL.PRODUCTION_KG,      null, cycleId) : 0;

    const totalCosts  = cyclePurchases + cycleOperating + cyclePayroll + cycleConstruct;
    const pnl         = cycleProductionR + cycleSales - totalCosts;
    const costPerKg   = productionKg > 0 ? (totalCosts / productionKg) : 0;

    return jsonOut({
      ok: true,
      data: {
        today_sales       : todaySales,
        today_purchases   : todayPurchases,
        today_operating   : todayOperating,
        today_payroll     : todayPayroll,
        cycle_sales       : cycleSales,
        cycle_purchases   : cyclePurchases,
        cycle_operating   : cycleOperating,
        cycle_payroll     : cyclePayroll,
        cycle_construction: cycleConstruct,
        cycle_production  : cycleProductionR,
        pnl               : pnl,
        production_kg     : productionKg,
        cost_per_kg       : Math.round(costPerKg * 100) / 100,
        cycle_id          : cycleId
      },
      version: FINANCE_VERSION
    });
  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

// ============================================================
//  GET RECENT ROWS
// ============================================================
function handleGetRecent(data) {
  try {
    const ss        = SpreadsheetApp.getActiveSpreadsheet();
    const limit     = parseInt(data.limit || 50);
    const cycleId   = data.cycleId || null;

    // Resolve sheet name – accept either SHEETS key or direct tab name
    let sheetName = data.sheetName || '';
    if (SHEETS[sheetName]) sheetName = SHEETS[sheetName];  // e.g. 'SALES' → 'المبيعات'

    const sheet = ss.getSheetByName(sheetName);
    if (!sheet) throw new Error('الورقة غير موجودة: ' + sheetName);

    const lastRow = sheet.getLastRow();
    if (lastRow < 2) {
      return jsonOut({ ok: true, data: { headers: [], rows: [], sheet: sheetName }, version: FINANCE_VERSION });
    }

    const numCols   = sheet.getLastColumn();
    const allData   = sheet.getRange(1, 1, lastRow, numCols).getValues();
    const headers   = allData[0].map(String);

    const rows = [];
    for (let r = lastRow; r >= 2; r--) {
      const rowVals = allData[r - 1];
      if (cycleId && String(rowVals[COL.CYCLE]) !== String(cycleId)) continue;
      rows.push({ row: r, values: rowVals.map(v => (v instanceof Date ? Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd') : v)) });
      if (rows.length >= limit) break;
    }

    return jsonOut({
      ok  : true,
      data: { headers, rows, sheet: sheetName },
      version: FINANCE_VERSION
    });
  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

// ============================================================
//  DELETE ROW
// ============================================================
function handleDeleteRow(data) {
  try {
    const sheetName = resolveSheetName(data.sheetName);
    const rowNumber = parseInt(data.rowNumber);
    const result    = deleteFinanceRow(sheetName, rowNumber);
    return jsonOut({ ok: true, data: result, version: FINANCE_VERSION });
  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

function deleteFinanceRow(sheetName, rowNumber) {
  if (!sheetName) throw new Error('اسم الورقة مطلوب');
  if (!rowNumber || isNaN(rowNumber)) throw new Error('رقم الصف مطلوب');
  if (rowNumber <= 1) throw new Error('لا يمكن حذف صف الرأس');

  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) throw new Error('الورقة غير موجودة: ' + sheetName);

  const lastRow = sheet.getLastRow();
  if (rowNumber > lastRow) throw new Error('رقم الصف خارج النطاق: ' + rowNumber);

  sheet.deleteRow(rowNumber);
  return { deleted: true, row: rowNumber, sheet: sheetName };
}

// ============================================================
//  CYCLE MANAGEMENT
// ============================================================
function handleListCycles(data) {
  try {
    const ss    = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(CYCLES_TAB);
    if (!sheet || sheet.getLastRow() < 2) {
      return jsonOut({ ok: true, data: { cycles: [], source: 'local' }, version: FINANCE_VERSION });
    }

    const numCols = sheet.getLastColumn();
    const allData = sheet.getRange(2, 1, sheet.getLastRow() - 1, numCols).getValues();
    const cycles  = allData.map((row, idx) => {
      const obj = {};
      CYCLE_HEADERS.forEach((h, i) => { obj[h] = row[i] !== undefined ? row[i] : ''; });
      obj._row = idx + 2;
      return obj;
    });

    // Optionally merge remote cycles from growing side
    let source = 'local';
    if (GROWING_API_URL) {
      try {
        const resp         = UrlFetchApp.fetch(GROWING_API_URL, {
          method : 'post',
          contentType: 'application/json',
          payload: JSON.stringify({ action: 'listCycles', data: { password: PASSWORD } }),
          muteHttpExceptions: true
        });
        const remoteResult = JSON.parse(resp.getContentText());
        if (remoteResult.ok && Array.isArray(remoteResult.data.cycles)) {
          source = 'merged';
          const localIds = new Set(cycles.map(c => String(c['رقم الدورة'])));
          remoteResult.data.cycles.forEach(rc => {
            if (!localIds.has(String(rc['رقم الدورة']))) cycles.push(rc);
          });
        }
      } catch (_) { /* remote unavailable – use local */ }
    }

    return jsonOut({ ok: true, data: { cycles, source }, version: FINANCE_VERSION });
  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

function handleCreateCycle(data) {
  try {
    const ss    = SpreadsheetApp.getActiveSpreadsheet();
    let sheet   = ss.getSheetByName(CYCLES_TAB);
    if (!sheet) sheet = ensureSheet(ss, CYCLES_TAB, CYCLE_HEADERS);

    const now = getTodayStr();
    const row = [
      data.cycleId       || generateCycleId(),
      data.name          || '',
      data.startDate     || now,
      data.expectedYield || '',
      data.room          || '',
      data.substrateType || '',
      data.bagCount      || '',
      data.status        || 'جارية',
      data.notes         || '',
      now
    ];

    const newRow = sheet.getLastRow() + 1;
    sheet.getRange(newRow, 1, 1, row.length).setValues([row]);

    return jsonOut({ ok: true, data: { row: newRow, cycle: row }, version: FINANCE_VERSION });
  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

function handleSetActiveCycle(data) {
  try {
    const cycleId = data.cycleId;
    if (!cycleId) throw new Error('رقم الدورة مطلوب');

    const ss    = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(CYCLES_TAB);
    if (!sheet || sheet.getLastRow() < 2) throw new Error('لا توجد دورات');

    const statusColIdx = CYCLE_HEADERS.indexOf('الحالة') + 1; // 1-based
    const idColIdx     = CYCLE_HEADERS.indexOf('رقم الدورة') + 1;
    const lastRow      = sheet.getLastRow();

    let found = false;
    for (let r = 2; r <= lastRow; r++) {
      const id = sheet.getRange(r, idColIdx).getValue();
      if (String(id) === String(cycleId)) {
        sheet.getRange(r, statusColIdx).setValue('جارية');
        found = true;
      } else {
        const cur = sheet.getRange(r, statusColIdx).getValue();
        if (cur === 'جارية') sheet.getRange(r, statusColIdx).setValue('منتهية');
      }
    }

    if (!found) throw new Error('لم يتم العثور على الدورة: ' + cycleId);

    return jsonOut({ ok: true, data: { active_cycle: cycleId }, version: FINANCE_VERSION });
  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

function handleGetActiveCycle(data) {
  try {
    const activeCycle = getActiveCycleData();
    return jsonOut({ ok: true, data: { active_cycle: activeCycle }, version: FINANCE_VERSION });
  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

// ============================================================
//  HELPERS
// ============================================================

/**
 * Returns today as 'YYYY-MM-DD' in the script's timezone.
 */
function getTodayStr() {
  return Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
}

/**
 * Sum values in `amountCol` of `sheetName` where:
 *   - if filterDate is set  → COL.DATE cell matches filterDate string
 *   - if cycleId is set     → COL.CYCLE cell matches cycleId
 * Both filters are combined with AND when both are provided.
 *
 * @param {Spreadsheet} ss
 * @param {string}      sheetName
 * @param {number}      dateCol      0-based index of date column
 * @param {number}      amountCol    0-based index of amount column
 * @param {string|null} filterDate   'YYYY-MM-DD' or null
 * @param {string|null} cycleId      cycle number string or null
 * @returns {number}
 */
function sumSheet(ss, sheetName, dateCol, amountCol, filterDate, cycleId) {
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet || sheet.getLastRow() < 2) return 0;

  const numCols = sheet.getLastColumn();
  const data    = sheet.getRange(2, 1, sheet.getLastRow() - 1, numCols).getValues();
  const tz      = Session.getScriptTimeZone();

  let total = 0;
  data.forEach(row => {
    // Date matching
    if (filterDate) {
      let cellDate = row[dateCol];
      if (cellDate instanceof Date) cellDate = Utilities.formatDate(cellDate, tz, 'yyyy-MM-dd');
      if (String(cellDate) !== String(filterDate)) return;
    }
    // Cycle matching
    if (cycleId && String(row[COL.CYCLE]) !== String(cycleId)) return;

    const val = parseFloat(row[amountCol]);
    if (!isNaN(val)) total += val;
  });

  return Math.round(total * 100) / 100;
}

/**
 * Resolve a sheet name from either a SHEETS key ('SALES') or direct tab name.
 */
function resolveSheetName(name) {
  if (!name) throw new Error('اسم الورقة مطلوب');
  return SHEETS[name] || name;
}

/**
 * Return active cycle data object or null.
 */
function getActiveCycleData() {
  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CYCLES_TAB);
  if (!sheet || sheet.getLastRow() < 2) return null;

  const statusIdx = CYCLE_HEADERS.indexOf('الحالة');
  const lastRow   = sheet.getLastRow();
  const numCols   = sheet.getLastColumn();
  const allData   = sheet.getRange(2, 1, lastRow - 1, numCols).getValues();

  for (let i = 0; i < allData.length; i++) {
    if (String(allData[i][statusIdx]) === 'جارية') {
      const obj = {};
      CYCLE_HEADERS.forEach((h, j) => { obj[h] = allData[i][j] !== undefined ? allData[i][j] : ''; });
      obj._row = i + 2;
      return obj;
    }
  }
  return null;
}

/**
 * Return active cycle ID string or empty string.
 */
function getActiveCycleId() {
  const ac = getActiveCycleData();
  return ac ? String(ac['رقم الدورة']) : '';
}

/**
 * Generate a simple cycle ID based on timestamp.
 */
function generateCycleId() {
  return 'C' + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyyMMddHHmm');
}

/**
 * Wrap any object as a JSON ContentService response.
 */
function jsonOut(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ============================================================
//  MANUAL TRIGGER (run from Apps Script editor for first-time setup)
// ============================================================
function setupEverything() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  Object.values(SHEETS).forEach(name => {
    ensureSheet(ss, name, SHEET_HEADERS[name]);
  });

  ensureSheet(ss, CYCLES_TAB, CYCLE_HEADERS);

  SpreadsheetApp.getUi().alert(
    'MAKNABIS Finance ' + FINANCE_VERSION + '\n\nتم إنشاء جميع الأوراق بنجاح ✓'
  );
}

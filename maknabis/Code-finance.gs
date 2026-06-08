// ============================================================
//  MAKNABIS – Finance Backend  (Google Apps Script)
//  Version : v2_cycles
//  Handles : Purchases, Sales, Construction, Operating,
//             Payroll, Production, Inventory + 4 Dashboards
//             + Cycle management + Photo upload to Drive
// ============================================================

const FINANCE_VERSION  = 'v2_cycles';
const PASSWORD         = 'FARM2026';
const DRIVE_FOLDER_NAME = 'MAKNABIS - مرفقات المالية';
const GROWING_API_URL  = '';   // paste growing app exec URL here for cross-app cycle sync

// ── Sheet tab names ──────────────────────────────────────────
const SHEETS = {
  PURCHASES   : 'المشتريات',
  SALES       : 'المبيعات',
  CONSTRUCTION: 'البناء',
  OPERATING   : 'مصاريف التشغيل',
  PAYROLL     : 'الأجور',
  PRODUCTION  : 'دورات الإنتاج',
  INVENTORY   : 'المخزون'
};

// ── Dashboard tab names ──────────────────────────────────────
const DASHBOARDS = {
  MAIN      : '🏠 الداشبورد',
  MONTHLY   : '📊 ملخص شهري',
  YEARLY    : '📈 ملخص سنوي',
  PRODUCTION: '🌱 تحليل الإنتاج'
};

// ── Cycles tab ───────────────────────────────────────────────
const CYCLES_TAB = '🔄 الدورات';

const CYCLE_COLUMNS = [
  'رقم الدورة','الاسم','تاريخ البدء','الحصاد المتوقع',
  'الغرفة','نوع الركيزة','عدد الأكياس','الحالة','ملاحظات','تاريخ الإنشاء'
];

// ── Sheet headers (original schemas + رقم الدورة as col 3) ──
const SHEET_HEADERS = {
  [SHEETS.PURCHASES]   : ['التاريخ','العامل','رقم الدورة','المورد','الصنف','الكمية','الوحدة','سعر الوحدة','الإجمالي','طريقة الدفع','رقم الفاتورة','صورة','ملاحظات','وقت الإدخال'],
  [SHEETS.SALES]       : ['التاريخ','العامل','رقم الدورة','العميل','المنتج','الكمية (كغ)','سعر الكيلو','الإجمالي','طريقة الدفع','مدفوع؟','رقم الفاتورة','صورة','ملاحظات','وقت الإدخال'],
  [SHEETS.CONSTRUCTION]: ['التاريخ','العامل','رقم الدورة','وصف العمل','المقاول/العامل','المواد','التكلفة','مرحلة المشروع','صورة','ملاحظات','وقت الإدخال'],
  [SHEETS.OPERATING]   : ['التاريخ','العامل','رقم الدورة','نوع المصروف','الوصف','المبلغ','طريقة الدفع','صورة','ملاحظات','وقت الإدخال'],
  [SHEETS.PAYROLL]     : ['التاريخ','العامل','رقم الدورة','الاسم','الوظيفة','الفترة','الأجر','الحالة','ملاحظات','وقت الإدخال'],
  [SHEETS.PRODUCTION]  : ['رقم الدورة','العامل','تاريخ البدء','نوع الركيزة','كمية الركيزة (كغ)','كمية البذور (كغ)','عدد الأكياس','تاريخ أول حصاد','تاريخ آخر حصاد','الإنتاج (كغ)','الأكياس التالفة','الكفاءة الحيوية %','ملاحظات','وقت الإدخال'],
  [SHEETS.INVENTORY]   : ['التاريخ','العامل','رقم الدورة','الصنف','نوع الحركة','الكمية','الوحدة','ملاحظات','وقت الإدخال']
};

// ── 0-based column indices ───────────────────────────────────
const COL = {
  DATE   : 0,   // A
  WORKER : 1,   // B
  CYCLE  : 2,   // C  (رقم الدورة – col 3 in all data sheets)
  // amount columns per sheet (0-based)
  PURCHASES_TOTAL    : 8,   // I  الإجمالي
  SALES_TOTAL        : 7,   // H  الإجمالي
  CONSTRUCTION_COST  : 6,   // G  التكلفة
  OPERATING_AMOUNT   : 5,   // F  المبلغ
  PAYROLL_AMOUNT     : 6,   // G  الأجر
  PRODUCTION_KG      : 9,   // J  الإنتاج (كغ)
  PRODUCTION_CYCLE_COL: 0   // A  رقم الدورة in production sheet
};

// Tunisian month names
const TN_MONTHS = ['جانفي','فيفري','مارس','أفريل','ماي','جوان','جويلية','أوت','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];

// ============================================================
//  ENTRY POINT
// ============================================================
function doPost(e) {
  try {
    const body   = JSON.parse(e.postData.contents);
    const action = body.action || '';
    const data   = body.data   || {};

    if (action !== 'checkAuth') {
      if (data.password !== PASSWORD) {
        return jsonOut({ ok: false, error: 'كلمة مرور غير صحيحة' });
      }
    }

    let result;
    switch (action) {
      case 'checkAuth':
        result = { ok: data.password === PASSWORD, version: FINANCE_VERSION, active_cycle: getActiveCycle_() };
        return jsonOut(result.ok
          ? { ok: true, data: result, version: FINANCE_VERSION }
          : { ok: false, error: 'كلمة مرور غير صحيحة' });

      case 'addPurchase':
        result = addPurchase(data); break;
      case 'addSale':
        result = addSale(data); break;
      case 'addConstruction':
        result = addConstruction(data); break;
      case 'addExpense':
      case 'addOperating':
        result = addOperating(data); break;
      case 'addPayroll':
        result = addPayroll(data); break;
      case 'addProduction':
        result = addProduction(data); break;
      case 'addInventory':
        result = addInventory(data); break;

      case 'getTodayStats':
        result = getTodayStats(data.cycleId || null); break;
      case 'getRecent':
        result = getRecent(data.sheetName, data.limit || 50, data.cycleId || null); break;
      case 'deleteRow':
        result = deleteFinanceRow_(data.sheetName, parseInt(data.rowNumber, 10)); break;
      case 'uploadPhoto':
        result = { url: uploadPhoto(data.base64, data.filename) }; break;

      case 'listCycles':
        result = { cycles: listCycles_(), active: getActiveCycle_() }; break;
      case 'createCycle':
        result = createFinanceCycle(data); break;
      case 'setActiveCycle':
        result = setActiveCycle_(data.cycleId); break;
      case 'getActiveCycle':
        result = { active_cycle: getActiveCycle_() }; break;

      case 'setupEverything':
        setupEverything();
        result = { message: 'تم الإعداد بنجاح', version: FINANCE_VERSION }; break;
      case 'rebuildDashboards':
        buildMainDashboard();
        buildMonthlySummary();
        buildYearlySummary();
        buildProductionAnalysis();
        result = { message: 'تم تحديث الداشبوردات' }; break;

      default:
        return jsonOut({ ok: false, error: 'إجراء غير معروف: ' + action });
    }

    return jsonOut({ ok: true, data: result, version: FINANCE_VERSION });

  } catch (err) {
    return jsonOut({ ok: false, error: err.message });
  }
}

function doGet(e) {
  return jsonOut({ ok: true, version: FINANCE_VERSION, service: 'finance' });
}

// ============================================================
//  SETUP
// ============================================================
function setupEverything() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // Create cycles tab first
  ensureSheet_(ss, CYCLES_TAB, CYCLE_COLUMNS);

  // Create all 7 data sheets
  Object.values(SHEETS).forEach(name => {
    ensureSheet_(ss, name, SHEET_HEADERS[name]);
  });

  // Build all 4 dashboards
  setupDashboard();

  try {
    SpreadsheetApp.getUi().alert(
      '✅ اكتمل الإعداد الكامل\n\n' +
      '- تبويب الدورات\n' +
      '- 7 أوراق بيانات\n' +
      '- 4 داشبوردات ديناميكية'
    );
  } catch(_) {}
}

function setupDashboard() {
  buildMainDashboard();
  buildMonthlySummary();
  buildYearlySummary();
  buildProductionAnalysis();
}

function testSetup() {
  Logger.log('MAKNABIS Finance ' + FINANCE_VERSION + ' – test OK');
  Logger.log('Sheets: ' + JSON.stringify(Object.values(SHEETS)));
  Logger.log('Dashboards: ' + JSON.stringify(Object.values(DASHBOARDS)));
}

function reorderSheets() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const order = [
    DASHBOARDS.MAIN, DASHBOARDS.MONTHLY, DASHBOARDS.YEARLY, DASHBOARDS.PRODUCTION,
    CYCLES_TAB,
    SHEETS.SALES, SHEETS.PURCHASES, SHEETS.OPERATING, SHEETS.PAYROLL,
    SHEETS.CONSTRUCTION, SHEETS.PRODUCTION, SHEETS.INVENTORY
  ];
  let pos = 0;
  order.forEach(name => {
    const sh = ss.getSheetByName(name);
    if (sh) { ss.setActiveSheet(sh); ss.moveActiveSheet(++pos); }
  });
}

function ensureSheet_(ss, name, headers) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  if (sheet.getLastRow() === 0) {
    const range = sheet.getRange(1, 1, 1, headers.length);
    range.setValues([headers]);
    range.setFontWeight('bold');
    range.setBackground('#34a853');
    range.setFontColor('#ffffff');
    sheet.setFrozenRows(1);
    sheet.setRightToLeft(true);
  }
  return sheet;
}

// ============================================================
//  PHOTO UPLOAD
// ============================================================
function uploadPhoto(base64Data, filename) {
  try {
    if (!base64Data || base64Data.indexOf(',') === -1) return '';
    const folders = DriveApp.getFoldersByName(DRIVE_FOLDER_NAME);
    const folder  = folders.hasNext() ? folders.next() : DriveApp.createFolder(DRIVE_FOLDER_NAME);
    const contentType = base64Data.substring(base64Data.indexOf(':') + 1, base64Data.indexOf(';'));
    const bytes   = Utilities.base64Decode(base64Data.split(',')[1]);
    const blob    = Utilities.newBlob(bytes, contentType, filename || ('photo_' + Date.now() + '.jpg'));
    const file    = folder.createFile(blob);
    file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
    return file.getUrl();
  } catch (e) { return ''; }
}

// ============================================================
//  ADD ROWS
// ============================================================
function _append(sheetName, row) {
  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) throw new Error('الورقة غير موجودة: ' + sheetName);
  const newRow = sheet.getLastRow() + 1;
  sheet.getRange(newRow, 1, 1, row.length).setValues([row]);
  return { row: newRow, inserted: row };
}

function addPurchase(d) {
  const qty   = Number(d.quantity  || 0);
  const price = Number(d.unitPrice || d.pricePerUnit || 0);
  return _append(SHEETS.PURCHASES, [
    d.date || getTodayStr(), d.workerName || '', d.cycleId || '',
    d.supplier || '', d.item || '', qty, d.unit || '',
    price, qty * price,
    d.paymentMethod || '', d.invoiceNumber || '', d.photoUrl || '',
    d.notes || '', new Date()
  ]);
}

function addSale(d) {
  const qty   = Number(d.quantity || d.weightKg || 0);
  const price = Number(d.pricePerKg || d.priceKg || 0);
  const isPaid = d.paid === 'true' || d.paid === true;
  return _append(SHEETS.SALES, [
    d.date || getTodayStr(), d.workerName || '', d.cycleId || '',
    d.customer || '', d.product || d.item || '',
    qty, price, qty * price,
    d.paymentMethod || '', isPaid ? 'نعم' : 'لا',
    d.invoiceNumber || '', d.photoUrl || '', d.notes || '', new Date()
  ]);
}

function addConstruction(d) {
  return _append(SHEETS.CONSTRUCTION, [
    d.date || getTodayStr(), d.workerName || '', d.cycleId || '',
    d.description || d.item || '', d.contractor || d.supplier || '',
    d.materials || '', Number(d.cost || 0),
    d.projectPhase || d.phase || '', d.photoUrl || '',
    d.notes || '', new Date()
  ]);
}

function addOperating(d) {
  return _append(SHEETS.OPERATING, [
    d.date || getTodayStr(), d.workerName || '', d.cycleId || '',
    d.expenseType || d.item || '', d.description || '',
    Number(d.amount || 0), d.paymentMethod || '',
    d.photoUrl || '', d.notes || '', new Date()
  ]);
}

function addPayroll(d) {
  return _append(SHEETS.PAYROLL, [
    d.date || getTodayStr(), d.workerName || '', d.cycleId || '',
    d.name || d.employeeName || '', d.role || d.position || '',
    d.period || '', Number(d.amount || d.wage || 0),
    d.status || '', d.notes || '', new Date()
  ]);
}

function addProduction(d) {
  return _append(SHEETS.PRODUCTION, [
    d.cycleId || '', d.workerName || '', d.startDate || getTodayStr(),
    d.substrateType || '', Number(d.substrateKg || 0),
    Number(d.seedKg || 0), Number(d.bagCount || 0),
    d.firstHarvestDate || '', d.lastHarvestDate || '',
    Number(d.productionKg || 0), Number(d.damagedBags || 0),
    Number(d.biologicalEfficiency || 0),
    d.notes || '', new Date()
  ]);
}

function addInventory(d) {
  return _append(SHEETS.INVENTORY, [
    d.date || getTodayStr(), d.workerName || '', d.cycleId || '',
    d.item || '', d.movementType || '',
    Number(d.quantity || 0), d.unit || '',
    d.notes || '', new Date()
  ]);
}

// ============================================================
//  TODAY STATS  (today + cycle totals)
// ============================================================
function getTodayStats(cycleId) {
  const ss  = SpreadsheetApp.getActiveSpreadsheet();
  const tz  = Session.getScriptTimeZone();
  const today = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd');

  function sumBy(sheetName, dateColIdx, amountColIdx, filterDate, filterCycle) {
    const sh = ss.getSheetByName(sheetName);
    if (!sh || sh.getLastRow() < 2) return { total: 0, count: 0 };
    const vals = sh.getRange(2, 1, sh.getLastRow() - 1, sh.getLastColumn()).getValues();
    let total = 0, count = 0;
    vals.forEach(r => {
      if (!r[dateColIdx] && filterDate) return;
      if (filterCycle && String(r[COL.CYCLE]) !== String(filterCycle)) return;
      if (filterDate) {
        const ds = r[dateColIdx] instanceof Date
          ? Utilities.formatDate(r[dateColIdx], tz, 'yyyy-MM-dd')
          : String(r[dateColIdx]).substring(0, 10);
        if (ds !== filterDate) return;
      }
      total += Number(r[amountColIdx]) || 0;
      count++;
    });
    return { total: Math.round(total * 100) / 100, count };
  }

  const activeCycleId = cycleId || getActiveCycleId_();

  return {
    today_sales      : sumBy(SHEETS.SALES,        0, COL.SALES_TOTAL,       today, null).total,
    today_purchases  : sumBy(SHEETS.PURCHASES,     0, COL.PURCHASES_TOTAL,   today, null).total,
    today_operating  : sumBy(SHEETS.OPERATING,     0, COL.OPERATING_AMOUNT,  today, null).total,
    today_payroll    : sumBy(SHEETS.PAYROLL,        0, COL.PAYROLL_AMOUNT,    today, null).total,
    cycle_sales      : activeCycleId ? sumBy(SHEETS.SALES,        0, COL.SALES_TOTAL,       null, activeCycleId).total : 0,
    cycle_purchases  : activeCycleId ? sumBy(SHEETS.PURCHASES,     0, COL.PURCHASES_TOTAL,   null, activeCycleId).total : 0,
    cycle_operating  : activeCycleId ? sumBy(SHEETS.OPERATING,     0, COL.OPERATING_AMOUNT,  null, activeCycleId).total : 0,
    cycle_payroll    : activeCycleId ? sumBy(SHEETS.PAYROLL,        0, COL.PAYROLL_AMOUNT,    null, activeCycleId).total : 0,
    cycle_construction: activeCycleId ? sumBy(SHEETS.CONSTRUCTION, 0, COL.CONSTRUCTION_COST, null, activeCycleId).total : 0,
    cycle_production : activeCycleId ? sumBy(SHEETS.PRODUCTION,    COL.PRODUCTION_CYCLE_COL, COL.PRODUCTION_KG, null, activeCycleId).total : 0,
    get pnl() {
      return this.cycle_sales - this.cycle_purchases - this.cycle_operating -
             this.cycle_payroll - this.cycle_construction;
    },
    active_cycle: activeCycleId || null
  };
}

// ============================================================
//  GET RECENT ROWS  (with row numbers, optional cycle filter)
// ============================================================
function getRecent(sheetName, limit, cycleId) {
  limit = limit || 50;
  const name  = SHEETS[sheetName] || sheetName;
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(name);
  if (!sheet || sheet.getLastRow() < 2) return { headers: [], rows: [], sheet: name };

  const tz      = Session.getScriptTimeZone();
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const allRows = sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn()).getValues();

  let withRows = allRows.map((vals, i) => ({ row: i + 2, values: vals }));
  if (cycleId) {
    withRows = withRows.filter(r => String(r.values[COL.CYCLE]) === String(cycleId));
  }
  const sliced   = withRows.slice(-limit).reverse();
  const formatted = sliced.map(r => ({
    row: r.row,
    values: r.values.map(c => {
      if (c instanceof Date) return Utilities.formatDate(c, tz, 'yyyy-MM-dd HH:mm');
      return c;
    })
  }));
  return { headers, rows: formatted, sheet: name };
}

// ============================================================
//  DELETE ROW
// ============================================================
function deleteFinanceRow_(sheetName, rowNumber) {
  const name  = SHEETS[sheetName] || sheetName;
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(name);
  if (!sheet) return { ok: false, error: 'الورقة غير موجودة: ' + name };
  if (!rowNumber || rowNumber < 2) return { ok: false, error: 'رقم الصف غير صالح' };
  if (rowNumber > sheet.getLastRow()) return { ok: false, error: 'الصف خارج النطاق' };
  sheet.deleteRow(rowNumber);
  return { ok: true, deleted: true, sheet: name };
}

// ============================================================
//  CYCLE MANAGEMENT
// ============================================================
function listCycles_() {
  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CYCLES_TAB);
  if (!sheet || sheet.getLastRow() < 2) return [];
  const data   = sheet.getRange(2, 1, sheet.getLastRow() - 1, CYCLE_COLUMNS.length).getValues();
  return data.map((row, i) => {
    const obj = { _row: i + 2 };
    CYCLE_COLUMNS.forEach((h, j) => { obj[h] = row[j] !== undefined ? row[j] : ''; });
    // convenience alias
    obj.id     = String(obj['رقم الدورة']);
    obj.status = String(obj['الحالة']);
    return obj;
  });
}

function getActiveCycle_() {
  return listCycles_().find(c => c.status === 'جارية') || null;
}

function getActiveCycleId_() {
  const ac = getActiveCycle_();
  return ac ? ac.id : '';
}

function createFinanceCycle(data) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ensureSheet_(ss, CYCLES_TAB, CYCLE_COLUMNS);
  const now   = getTodayStr();
  const row   = [
    data.cycleId       || generateCycleId_(),
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
  return { row: newRow, cycle: row };
}

function setActiveCycle_(cycleId) {
  if (!cycleId) throw new Error('رقم الدورة مطلوب');
  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CYCLES_TAB);
  if (!sheet || sheet.getLastRow() < 2) throw new Error('لا توجد دورات');

  const statusColIdx = CYCLE_COLUMNS.indexOf('الحالة') + 1;
  const idColIdx     = CYCLE_COLUMNS.indexOf('رقم الدورة') + 1;
  const lastRow      = sheet.getLastRow();
  let found = false;

  for (let r = 2; r <= lastRow; r++) {
    const id = sheet.getRange(r, idColIdx).getValue();
    if (String(id) === String(cycleId)) {
      sheet.getRange(r, statusColIdx).setValue('جارية');
      found = true;
    } else {
      if (sheet.getRange(r, statusColIdx).getValue() === 'جارية') {
        sheet.getRange(r, statusColIdx).setValue('منتهية');
      }
    }
  }

  if (!found) throw new Error('لم يتم العثور على الدورة: ' + cycleId);
  return { active_cycle: cycleId };
}

// ============================================================
//  DASHBOARD BUILDERS
// ============================================================

// ── Helper: column letter ────────────────────────────────────
function colLetter(n) {
  let s = '';
  while (n > 0) {
    const rem = (n - 1) % 26;
    s = String.fromCharCode(65 + rem) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

// ── Helper: clear and prepare dashboard sheet ────────────────
function getDashSheet_(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh   = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  sh.clearContents();
  sh.clearFormats();
  sh.setRightToLeft(true);
  return sh;
}

// ── Style helpers ────────────────────────────────────────────
function styleHeader_(range, bg, fg) {
  bg = bg || '#1a73e8';
  fg = fg || '#ffffff';
  range.setBackground(bg).setFontColor(fg).setFontWeight('bold').setFontSize(11);
}

function styleKpi_(range) {
  range.setFontSize(20).setFontWeight('bold').setHorizontalAlignment('center');
}

// ── 1. MAIN DASHBOARD ────────────────────────────────────────
function buildMainDashboard() {
  const sh  = getDashSheet_(DASHBOARDS.MAIN);
  const ss  = SpreadsheetApp.getActiveSpreadsheet();
  const tz  = Session.getScriptTimeZone();
  const now = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd HH:mm');

  // Title row
  const titleRange = sh.getRange('A1:H1');
  titleRange.merge();
  titleRange.setValue('🏠 داشبورد MAKNABIS – المالية');
  titleRange.setBackground('#0d47a1').setFontColor('#ffffff').setFontWeight('bold')
    .setFontSize(16).setHorizontalAlignment('center').setRowHeight;
  sh.setRowHeight(1, 45);

  sh.getRange('A2').setValue('آخر تحديث: ' + now).setFontColor('#666666').setFontSize(9);

  // ── KPI Cards ──────────────────────────────────────────────
  const salesRef  = "=SUMPRODUCT((" + SHEETS.SALES + "!A2:A5000<>\"\")*(" + SHEETS.SALES + "!H2:H5000))";
  const purRef    = "=SUMPRODUCT((" + SHEETS.PURCHASES + "!A2:A5000<>\"\")*(" + SHEETS.PURCHASES + "!I2:I5000))";
  const opRef     = "=SUMPRODUCT((" + SHEETS.OPERATING + "!A2:A5000<>\"\")*(" + SHEETS.OPERATING + "!F2:F5000))";
  const payRef    = "=SUMPRODUCT((" + SHEETS.PAYROLL + "!A2:A5000<>\"\")*(" + SHEETS.PAYROLL + "!G2:G5000))";
  const conRef    = "=SUMPRODUCT((" + SHEETS.CONSTRUCTION + "!A2:A5000<>\"\")*(" + SHEETS.CONSTRUCTION + "!G2:G5000))";

  const kpis = [
    { label: '💰 إجمالي المبيعات', formula: salesRef,                         bg: '#e8f5e9', fg: '#2e7d32' },
    { label: '🛒 إجمالي المشتريات', formula: purRef,                           bg: '#fff3e0', fg: '#e65100' },
    { label: '⚙️ مصاريف التشغيل',   formula: opRef,                            bg: '#fce4ec', fg: '#880e4f' },
    { label: '👷 الأجور',           formula: payRef,                           bg: '#e3f2fd', fg: '#0d47a1' },
    { label: '🏗️ البناء',          formula: conRef,                           bg: '#f3e5f5', fg: '#4a148c' },
    { label: '📈 صافي الربح',       formula: '=' + salesRef.slice(1) + '-' + purRef.slice(1) + '-' + opRef.slice(1) + '-' + payRef.slice(1) + '-' + conRef.slice(1),
                                                                                bg: '#e8f5e9', fg: '#1b5e20' }
  ];

  let row = 4;
  sh.getRange(row, 1, 1, 3).merge().setValue('📊 مؤشرات الأداء الرئيسية')
    .setBackground('#37474f').setFontColor('#fff').setFontWeight('bold').setFontSize(12);
  row++;

  kpis.forEach((k, i) => {
    const col = (i % 2 === 0) ? 1 : 5;
    if (i % 2 === 0 && i > 0) row++;
    sh.getRange(row, col, 1, 2).merge().setValue(k.label)
      .setBackground(k.bg).setFontColor(k.fg).setFontWeight('bold');
    sh.getRange(row, col + 2, 1, 2).merge().setFormula(k.formula)
      .setBackground(k.bg).setFontColor(k.fg).setFontWeight('bold')
      .setNumberFormat('#,##0.00 "د.ت"').setFontSize(13).setHorizontalAlignment('center');
  });
  row += 3;

  // ── Profit Margin ─────────────────────────────────────────
  sh.getRange(row, 1, 1, 4).merge().setValue('هامش الربح %')
    .setBackground('#e0f7fa').setFontColor('#006064').setFontWeight('bold');
  const marginFormula = '=IFERROR((' + salesRef.slice(1) + '-' + purRef.slice(1) + '-' + opRef.slice(1) + '-' + payRef.slice(1) + '-' + conRef.slice(1) + ')/' + salesRef.slice(1) + '*100,0)';
  sh.getRange(row, 5, 1, 2).merge().setFormula('=' + marginFormula.slice(1))
    .setBackground('#e0f7fa').setFontColor('#006064').setFontWeight('bold')
    .setNumberFormat('0.00"%"').setFontSize(13).setHorizontalAlignment('center');
  row += 2;

  // ── Best Customers ────────────────────────────────────────
  sh.getRange(row, 1, 1, 6).merge().setValue('🏆 أفضل العملاء')
    .setBackground('#1565c0').setFontColor('#fff').setFontWeight('bold').setFontSize(11);
  row++;
  ['العميل', 'إجمالي المبيعات', 'عدد المعاملات'].forEach((h, i) => {
    sh.getRange(row, i * 2 + 1, 1, 2).merge().setValue(h)
      .setBackground('#1976d2').setFontColor('#fff').setFontWeight('bold');
  });
  row++;
  // QUERY to get top 5 customers by sales total
  const custQuery = '=IFERROR(QUERY(\'' + SHEETS.SALES + '\'!D2:H5000,"SELECT D,SUM(H),COUNT(H) WHERE D<>\'\' GROUP BY D ORDER BY SUM(H) DESC LIMIT 5 LABEL D \'العميل\',SUM(H) \'المبيعات\',COUNT(H) \'عدد\'",0),{"لا بيانات","",""})';
  sh.getRange(row, 1).setFormula(custQuery);
  row += 7;

  // ── Expense Breakdown ─────────────────────────────────────
  sh.getRange(row, 1, 1, 6).merge().setValue('💸 توزيع المصروفات')
    .setBackground('#4a148c').setFontColor('#fff').setFontWeight('bold').setFontSize(11);
  row++;
  const expBreakdown = [
    ['المشتريات', purRef],
    ['التشغيل',   opRef],
    ['الأجور',    payRef],
    ['البناء',    conRef]
  ];
  const totalCostsFormula = purRef.slice(1) + '+' + opRef.slice(1) + '+' + payRef.slice(1) + '+' + conRef.slice(1);
  expBreakdown.forEach(([label, formula]) => {
    sh.getRange(row, 1, 1, 2).merge().setValue(label).setBackground('#f3e5f5');
    sh.getRange(row, 3, 1, 2).merge().setFormula(formula)
      .setNumberFormat('#,##0.00 "د.ت"').setBackground('#f3e5f5');
    sh.getRange(row, 5, 1, 2).merge()
      .setFormula('=IFERROR(' + formula.slice(1) + '/(' + totalCostsFormula + ')*100,0)')
      .setNumberFormat('0.00"%"').setBackground('#f3e5f5');
    row++;
  });
  row += 2;

  // ── Production Summary ────────────────────────────────────
  sh.getRange(row, 1, 1, 6).merge().setValue('🌱 ملخص الإنتاج')
    .setBackground('#1b5e20').setFontColor('#fff').setFontWeight('bold').setFontSize(11);
  row++;
  const prodKgRef  = "=SUMPRODUCT((" + SHEETS.PRODUCTION + "!A2:A5000<>\"\")*(" + SHEETS.PRODUCTION + "!J2:J5000))";
  const prodItems  = [
    ['إجمالي الإنتاج (كغ)', prodKgRef],
    ['عدد الدورات',          '=COUNTA(\'' + SHEETS.PRODUCTION + '\'!A2:A5000)'],
    ['متوسط الكفاءة البيولوجية %', '=IFERROR(AVERAGE(\'' + SHEETS.PRODUCTION + '\'!L2:L5000),0)']
  ];
  prodItems.forEach(([label, formula]) => {
    sh.getRange(row, 1, 1, 3).merge().setValue(label).setBackground('#e8f5e9');
    sh.getRange(row, 4, 1, 3).merge().setFormula(formula)
      .setBackground('#e8f5e9').setFontWeight('bold').setHorizontalAlignment('center');
    row++;
  });
  row += 2;

  // ── Cash Flow summary ─────────────────────────────────────
  sh.getRange(row, 1, 1, 6).merge().setValue('💵 التدفق النقدي الإجمالي')
    .setBackground('#004d40').setFontColor('#fff').setFontWeight('bold').setFontSize(11);
  row++;
  const cashIn  = salesRef;
  const cashOut = '=(' + purRef.slice(1) + '+' + opRef.slice(1) + '+' + payRef.slice(1) + '+' + conRef.slice(1) + ')';
  [['تدفق داخل', cashIn, '#e8f5e9', '#2e7d32'],
   ['تدفق خارج', cashOut, '#fce4ec', '#b71c1c'],
   ['صافي',      '=' + cashIn.slice(1) + '-' + cashOut.slice(1), '#e0f2f1', '#004d40']
  ].forEach(([label, formula, bg, fg]) => {
    sh.getRange(row, 1, 1, 3).merge().setValue(label).setBackground(bg).setFontColor(fg).setFontWeight('bold');
    sh.getRange(row, 4, 1, 3).merge().setFormula(formula)
      .setBackground(bg).setFontColor(fg).setFontWeight('bold')
      .setNumberFormat('#,##0.00 "د.ت"').setHorizontalAlignment('center').setFontSize(13);
    row++;
  });

  // Column widths
  [1,2,3,4,5,6,7,8].forEach((c, i) => sh.setColumnWidth(c, [160,120,120,120,160,120,120,80][i] || 100));
}

// ── 2. MONTHLY SUMMARY ───────────────────────────────────────
function buildMonthlySummary() {
  const sh  = getDashSheet_(DASHBOARDS.MONTHLY);
  const now = new Date();
  const yr  = now.getFullYear();

  // Title
  const t = sh.getRange('A1:H1');
  t.merge().setValue('📊 الملخص الشهري – ' + yr);
  t.setBackground('#1565c0').setFontColor('#fff').setFontWeight('bold')
   .setFontSize(15).setHorizontalAlignment('center');
  sh.setRowHeight(1, 45);

  // Header row
  const hdrs = ['الشهر', 'المبيعات', 'المشتريات', 'التشغيل', 'الأجور', 'البناء', 'إجمالي التكاليف', 'صافي الربح'];
  sh.getRange(3, 1, 1, hdrs.length).setValues([hdrs])
    .setBackground('#1976d2').setFontColor('#fff').setFontWeight('bold');

  // Data rows — one per Tunisian month name, SUMIFS by month
  TN_MONTHS.forEach((monthName, mi) => {
    const m     = mi + 1;  // 1–12
    const mStr  = m < 10 ? '0' + m : String(m);
    const row   = mi + 4;

    sh.getRange(row, 1).setValue(monthName + ' ' + yr);

    function sumifMonth(sheetTab, amountCol) {
      // SUMPRODUCT with YEAR+MONTH extraction
      return '=SUMPRODUCT((YEAR(\'' + sheetTab + '\'!A2:A5000)=' + yr +
             ')*(MONTH(\'' + sheetTab + '\'!A2:A5000)=' + m +
             ')*(\'' + sheetTab + '\'!A2:A5000<>"")*(\'' + sheetTab + '\'!' +
             amountCol + '2:' + amountCol + '5000))';
    }

    const salesF = sumifMonth(SHEETS.SALES,        colLetter(COL.SALES_TOTAL + 1));
    const purF   = sumifMonth(SHEETS.PURCHASES,    colLetter(COL.PURCHASES_TOTAL + 1));
    const opF    = sumifMonth(SHEETS.OPERATING,    colLetter(COL.OPERATING_AMOUNT + 1));
    const payF   = sumifMonth(SHEETS.PAYROLL,      colLetter(COL.PAYROLL_AMOUNT + 1));
    const conF   = sumifMonth(SHEETS.CONSTRUCTION, colLetter(COL.CONSTRUCTION_COST + 1));

    sh.getRange(row, 2).setFormula(salesF).setNumberFormat('#,##0.00');
    sh.getRange(row, 3).setFormula(purF).setNumberFormat('#,##0.00');
    sh.getRange(row, 4).setFormula(opF).setNumberFormat('#,##0.00');
    sh.getRange(row, 5).setFormula(payF).setNumberFormat('#,##0.00');
    sh.getRange(row, 6).setFormula(conF).setNumberFormat('#,##0.00');
    // Total costs
    sh.getRange(row, 7).setFormula('=C' + row + '+D' + row + '+E' + row + '+F' + row)
      .setNumberFormat('#,##0.00');
    // Net profit
    sh.getRange(row, 8).setFormula('=B' + row + '-G' + row)
      .setNumberFormat('#,##0.00');

    // Alternating row colors
    const bg = mi % 2 === 0 ? '#f8f9fa' : '#ffffff';
    sh.getRange(row, 1, 1, 8).setBackground(bg);
    // Red profit if negative
    const profitRange = sh.getRange(row, 8);
    profitRange.setFontColor(null); // clear; conditional formatting via note
  });

  // Totals row
  const totRow = 16;
  sh.getRange(totRow, 1).setValue('الإجمالي السنوي').setFontWeight('bold');
  for (let c = 2; c <= 8; c++) {
    sh.getRange(totRow, c)
      .setFormula('=SUM(' + colLetter(c) + '4:' + colLetter(c) + '15)')
      .setFontWeight('bold').setNumberFormat('#,##0.00');
  }
  sh.getRange(totRow, 1, 1, 8).setBackground('#bbdefb');

  // Column widths
  [150,120,120,120,120,120,150,120].forEach((w, i) => sh.setColumnWidth(i + 1, w));

  // Try to add a basic chart (sales vs costs)
  try {
    const chartRange = sh.getRange('A3:H15');
    const chart = sh.newChart()
      .setChartType(Charts.ChartType.COLUMN)
      .addRange(sh.getRange('A3:A15'))
      .addRange(sh.getRange('B3:B15'))
      .addRange(sh.getRange('G3:G15'))
      .addRange(sh.getRange('H3:H15'))
      .setOption('title', 'مقارنة شهرية: المبيعات والتكاليف والربح – ' + yr)
      .setOption('vAxis.title', 'المبلغ (د.ت)')
      .setOption('isStacked', false)
      .setPosition(18, 1, 0, 0)
      .setNumRows(15)
      .setNumColumns(8)
      .build();
    sh.insertChart(chart);
  } catch(_) {}
}

// ── 3. YEARLY SUMMARY ────────────────────────────────────────
function buildYearlySummary() {
  const sh      = getDashSheet_(DASHBOARDS.YEARLY);
  const curYear = new Date().getFullYear();

  const t = sh.getRange('A1:H1');
  t.merge().setValue('📈 الملخص السنوي – مقارنة 5 سنوات');
  t.setBackground('#4a148c').setFontColor('#fff').setFontWeight('bold')
   .setFontSize(15).setHorizontalAlignment('center');
  sh.setRowHeight(1, 45);

  const hdrs = ['السنة', 'المبيعات', 'المشتريات', 'التشغيل', 'الأجور', 'البناء', 'إجمالي التكاليف', 'صافي الربح'];
  sh.getRange(3, 1, 1, hdrs.length).setValues([hdrs])
    .setBackground('#6a1b9a').setFontColor('#fff').setFontWeight('bold');

  for (let yi = 0; yi < 5; yi++) {
    const yr  = curYear - yi;
    const row = 4 + yi;

    sh.getRange(row, 1).setValue(yr);

    function sumYear(sheetTab, amountCol) {
      return '=SUMPRODUCT((YEAR(\'' + sheetTab + '\'!A2:A5000)=' + yr +
             ')*(\'' + sheetTab + '\'!A2:A5000<>"")*(\'' + sheetTab + '\'!' +
             amountCol + '2:' + amountCol + '5000))';
    }

    const salesF = sumYear(SHEETS.SALES,        colLetter(COL.SALES_TOTAL + 1));
    const purF   = sumYear(SHEETS.PURCHASES,    colLetter(COL.PURCHASES_TOTAL + 1));
    const opF    = sumYear(SHEETS.OPERATING,    colLetter(COL.OPERATING_AMOUNT + 1));
    const payF   = sumYear(SHEETS.PAYROLL,      colLetter(COL.PAYROLL_AMOUNT + 1));
    const conF   = sumYear(SHEETS.CONSTRUCTION, colLetter(COL.CONSTRUCTION_COST + 1));

    sh.getRange(row, 2).setFormula(salesF).setNumberFormat('#,##0.00');
    sh.getRange(row, 3).setFormula(purF).setNumberFormat('#,##0.00');
    sh.getRange(row, 4).setFormula(opF).setNumberFormat('#,##0.00');
    sh.getRange(row, 5).setFormula(payF).setNumberFormat('#,##0.00');
    sh.getRange(row, 6).setFormula(conF).setNumberFormat('#,##0.00');
    sh.getRange(row, 7).setFormula('=C' + row + '+D' + row + '+E' + row + '+F' + row)
      .setNumberFormat('#,##0.00');
    sh.getRange(row, 8).setFormula('=B' + row + '-G' + row)
      .setNumberFormat('#,##0.00');

    const bg = yi % 2 === 0 ? '#f3e5f5' : '#fce4ec';
    sh.getRange(row, 1, 1, 8).setBackground(bg);
  }

  // Growth rates row
  const gr = 4 + 5 + 1;
  sh.getRange(gr, 1).setValue('نمو سنة/سنة %').setFontWeight('bold');
  for (let c = 2; c <= 8; c++) {
    sh.getRange(gr, c)
      .setFormula('=IFERROR((' + colLetter(c) + '4-' + colLetter(c) + '5)/' + colLetter(c) + '5*100,0)')
      .setNumberFormat('0.00"%"').setFontWeight('bold');
  }
  sh.getRange(gr, 1, 1, 8).setBackground('#e1bee7');

  // Column widths
  [100,120,120,120,120,120,150,120].forEach((w, i) => sh.setColumnWidth(i + 1, w));

  // Chart
  try {
    const chart = sh.newChart()
      .setChartType(Charts.ChartType.LINE)
      .addRange(sh.getRange('A3:A8'))
      .addRange(sh.getRange('B3:B8'))
      .addRange(sh.getRange('H3:H8'))
      .setOption('title', 'تطور المبيعات والربح على 5 سنوات')
      .setOption('vAxis.title', 'المبلغ (د.ت)')
      .setPosition(11, 1, 0, 0)
      .build();
    sh.insertChart(chart);
  } catch(_) {}
}

// ── 4. PRODUCTION ANALYSIS ───────────────────────────────────
function buildProductionAnalysis() {
  const sh = getDashSheet_(DASHBOARDS.PRODUCTION);

  const t = sh.getRange('A1:H1');
  t.merge().setValue('🌱 تحليل الإنتاج والدورات');
  t.setBackground('#1b5e20').setFontColor('#fff').setFontWeight('bold')
   .setFontSize(15).setHorizontalAlignment('center');
  sh.setRowHeight(1, 45);

  let row = 3;

  // KPIs
  sh.getRange(row, 1, 1, 8).merge().setValue('📊 مؤشرات الإنتاج الكلية')
    .setBackground('#2e7d32').setFontColor('#fff').setFontWeight('bold').setFontSize(12);
  row++;

  const prodSheet = SHEETS.PRODUCTION;
  const kpis = [
    ['عدد الدورات الكلي',            '=COUNTA(\'' + prodSheet + '\'!A2:A5000)'],
    ['إجمالي الإنتاج (كغ)',           '=SUMPRODUCT((' + prodSheet + '!A2:A5000<>"")*(' + prodSheet + '!J2:J5000))'],
    ['متوسط الإنتاج/دورة (كغ)',      '=IFERROR(AVERAGE(\'' + prodSheet + '\'!J2:J5000),0)'],
    ['متوسط الكفاءة البيولوجية %',   '=IFERROR(AVERAGE(\'' + prodSheet + '\'!L2:L5000),0)'],
    ['إجمالي الأكياس التالفة',        '=SUMPRODUCT((' + prodSheet + '!A2:A5000<>"")*(' + prodSheet + '!K2:K5000))'],
    ['إجمالي عدد الأكياس',            '=SUMPRODUCT((' + prodSheet + '!A2:A5000<>"")*(' + prodSheet + '!G2:G5000))']
  ];

  kpis.forEach(([label, formula], i) => {
    const col = (i % 2 === 0) ? 1 : 5;
    if (i % 2 === 0 && i > 0) row++;
    sh.getRange(row, col, 1, 2).merge().setValue(label)
      .setBackground('#e8f5e9').setFontWeight('bold');
    sh.getRange(row, col + 2, 1, 2).merge().setFormula(formula)
      .setBackground('#e8f5e9').setFontWeight('bold')
      .setHorizontalAlignment('center').setFontSize(13);
  });
  row += 3;

  // Substrate performance table via QUERY
  sh.getRange(row, 1, 1, 8).merge().setValue('🌿 أداء أنواع الركيزة')
    .setBackground('#33691e').setFontColor('#fff').setFontWeight('bold').setFontSize(11);
  row++;

  const substrateQuery = '=IFERROR(QUERY(\'' + prodSheet + '\'!D2:L5000,' +
    '"SELECT D,COUNT(D),SUM(J),AVG(J),AVG(L) ' +
    'WHERE D<>\'\' ' +
    'GROUP BY D ' +
    'ORDER BY SUM(J) DESC ' +
    'LABEL D \'نوع الركيزة\',COUNT(D) \'عدد الدورات\',SUM(J) \'إجمالي الإنتاج كغ\',AVG(J) \'متوسط الإنتاج\',AVG(L) \'متوسط الكفاءة%\'" ' +
    ',0),{"لا بيانات","","","",""})';
  sh.getRange(row, 1).setFormula(substrateQuery);
  row += 10;

  // Recent cycles table
  sh.getRange(row, 1, 1, 8).merge().setValue('🔄 آخر الدورات')
    .setBackground('#004d40').setFontColor('#fff').setFontWeight('bold').setFontSize(11);
  row++;

  const cycleQuery = '=IFERROR(QUERY(\'' + CYCLES_TAB + '\'!A2:J5000,' +
    '"SELECT A,B,C,G,H,I WHERE A<>\'\' ORDER BY C DESC LIMIT 10 ' +
    'LABEL A \'رقم الدورة\',B \'الاسم\',C \'تاريخ البدء\',G \'عدد الأكياس\',H \'الحالة\',I \'ملاحظات\'",0),' +
    '{"لا دورات","","","","",""})';
  sh.getRange(row, 1).setFormula(cycleQuery);
  row += 12;

  // Top cycles by production
  sh.getRange(row, 1, 1, 6).merge().setValue('🏆 أفضل الدورات إنتاجاً')
    .setBackground('#1a237e').setFontColor('#fff').setFontWeight('bold').setFontSize(11);
  row++;
  const topCycles = '=IFERROR(QUERY(\'' + prodSheet + '\'!A2:L5000,' +
    '"SELECT A,D,J,L WHERE A<>\'\' ORDER BY J DESC LIMIT 10 ' +
    'LABEL A \'رقم الدورة\',D \'نوع الركيزة\',J \'الإنتاج كغ\',L \'الكفاءة%\'",0),' +
    '{"لا بيانات","","",""})';
  sh.getRange(row, 1).setFormula(topCycles);

  // Column widths
  [140,130,130,130,130,130,130,130].forEach((w, i) => sh.setColumnWidth(i + 1, w));

  // Chart: production per cycle
  try {
    const chart = sh.newChart()
      .setChartType(Charts.ChartType.BAR)
      .addRange(sh.getRange('\'' + prodSheet + '\'!A2:A50'))
      .addRange(sh.getRange('\'' + prodSheet + '\'!J2:J50'))
      .setOption('title', 'الإنتاج (كغ) لكل دورة')
      .setOption('hAxis.title', 'الإنتاج (كغ)')
      .setPosition(row + 12, 1, 0, 0)
      .build();
    sh.insertChart(chart);
  } catch(_) {}
}

// ============================================================
//  UTILITY HELPERS
// ============================================================
function getTodayStr() {
  return Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
}

function generateCycleId_() {
  return 'C' + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyyMMddHHmm');
}

function jsonOut(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

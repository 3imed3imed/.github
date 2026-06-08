/**
 * MAKNABIS — مزرعة الفطر تونس 2026
 * Google Apps Script Backend — Definitive Merged Version
 * Version: v3_cycles
 * © 2026 MAKNABIS
 *
 * Combines:
 *   - Original: rich checklist sections, dashboard with formulas,
 *               photo upload, sharing, conditional formatting, tab reorder
 *   - v3 improvements: Cycle ID everywhere, cycle CRUD, room API,
 *                       recent API, delete row, 3 standardised readings
 */

// ─────────────────────────────────────────────────────────
// CONSTANTS
// ─────────────────────────────────────────────────────────

var VERSION           = 'v3_cycles';
var CHECKLISTS_VERSION = 'v3_cycles';
var DASHBOARD_KEY     = 'FARM2026';
var PASSWORD          = 'FARM2026';

var CYCLES_TAB       = '🔄 الدورات';
var CYCLE_ID_HEADER  = 'رقم الدورة';
var DASHBOARD_TAB    = '📊 لوحة القيادة';

var CYCLE_STATUSES = ['planning', 'active', 'harvesting', 'between', 'closed'];

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
// CONFIGURATION
// ─────────────────────────────────────────────────────────

var CONFIG = {
  spreadsheetName: 'MAKNABIS — مزرعة الفطر تونس 2026',
  timezone:  'Africa/Tunis',
  locale:    'ar_TN',
  operators: ['Imed', 'Atef', 'Chedi', 'Mariem'],
  shareWith: [
    { email: 'atefelhabib7@gmail.com', role: 'editor', notify: true }
  ]
};

// ─────────────────────────────────────────────────────────
// CHECKLIST DEFINITIONS
// ─────────────────────────────────────────────────────────
//
// Each entry: {
//   tab:      string  — sheet tab name
//   label:    string  — human-readable Arabic label
//   targets:  object  — env targets (optional)
//   sections: array   — [{ title, items: [{label, type?}] }]
// }
//
// buildHeaders(cl) builds the flat header array automatically.
// CYCLE_ID_HEADER is injected as column 3 by buildHeaders.
//
// Photo section appended to every checklist via PHOTO_SECTION constant.

var PHOTO_SECTION = {
  title: 'الصور',
  items: [
    { label: 'صورة 1',        type: 'photo' },
    { label: 'صورة 2',        type: 'photo' },
    { label: 'ملاحظات الصور'               }
  ]
};

var CHECKLISTS = {

  // ── 1. SETUP ──────────────────────────────────────────
  setup: {
    tab:   '1 - استلام الأكياس',
    label: 'استلام الأكياس',
    sections: [
      {
        title: 'تجهيز الغرفة',
        items: [
          { label: 'تنظيف الأرضية والجدران'          },
          { label: 'تعقيم الغرفة (نوع المعقم)'        },
          { label: 'فحص مضخة الهواء'                  },
          { label: 'فحص المرطب'                       },
          { label: 'فحص مستشعر CO2'                   },
          { label: 'فحص الإضاءة'                      },
          { label: 'درجة الحرارة قبل الاستلام (°C)'   },
          { label: 'الرطوبة قبل الاستلام (%)'          },
          { label: 'CO2 قبل الاستلام (ppm)'            },
          { label: 'حالة الغرفة العامة'               },
          { label: 'ملاحظات تجهيز الغرفة'             }
        ]
      },
      {
        title: 'استلام الأكياس',
        items: [
          { label: 'عدد الأكياس المستلمة'             },
          { label: 'حالة الأكياس (ممتاز/جيد/رديء)'   },
          { label: 'درجة حرارة الأكياس عند الاستلام' },
          { label: 'مصدر / مورّد الركيزة'             },
          { label: 'نوع الركيزة'                      },
          { label: 'وزن الشحنة (كغ)'                  },
          { label: 'ملاحظات الاستلام'                 }
        ]
      },
      {
        title: 'القراءات الأولية',
        items: [
          { label: 'درجة الهواء الأولية (°C)'         },
          { label: 'الرطوبة الأولية (%)'              },
          { label: 'CO2 الأولي (ppm)'                  },
          { label: 'توقيع المسؤول'                    },
          { label: 'ملاحظات عامة'                     }
        ]
      },
      PHOTO_SECTION
    ]
  },

  // ── 2. SPAWN RUN ──────────────────────────────────────
  spawn_run: {
    tab:   '2 - انتشار الميسيليوم',
    label: 'انتشار الميسيليوم',
    targets: {
      air_temp:     [22, 24],
      compost_temp: [24, 25],
      humidity:     [90, 95],
      co2:          [10000, 20000]
    },
    sections: [
      {
        title: 'صباحاً 06:00',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'درجة الكومبوست (°C)'             },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         },
          { label: 'حالة بخاخات الرطوبة'              },
          { label: 'حالة مضخة الهواء'                 },
          { label: 'مظهر الأكياس'                     },
          { label: 'نسبة الميسيليوم المرئية (%)'      },
          { label: 'ملاحظات الصباح'                  }
        ]
      },
      {
        title: 'ظهراً 12:00',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      }
        ]
      },
      {
        title: 'مساءً 18:00',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'درجة الكومبوست (°C)'             },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         }
        ]
      },
      {
        title: 'ليلاً 22:00',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      }
        ]
      },
      {
        title: 'ملاحظات اليوم',
        items: [
          { label: 'ملاحظات عامة / تقييم اليوم'      }
        ]
      },
      PHOTO_SECTION
    ]
  },

  // ── 3. CASING ─────────────────────────────────────────
  casing: {
    tab:   '3 - التغطية',
    label: 'التغطية',
    sections: [
      {
        title: 'التحضير',
        items: [
          { label: 'نوع مادة التغطية'                 },
          { label: 'كمية مادة التغطية (لتر)'          },
          { label: 'درجة رطوبة مادة التغطية (%)'      },
          { label: 'pH مادة التغطية'                  },
          { label: 'هل تم تعقيم مادة التغطية؟'        },
          { label: 'ملاحظات التحضير'                  }
        ]
      },
      {
        title: 'فحص الجاهزية',
        items: [
          { label: 'نسبة تغطية الميسيليوم (%)'        },
          { label: 'هل الميسيليوم جاهز للتغطية؟'      },
          { label: 'تاريخ استكمال الميسيليوم'         }
        ]
      },
      {
        title: 'تنفيذ التغطية',
        items: [
          { label: 'سماكة طبقة التغطية (سم)'          },
          { label: 'عدد الأكياس المغطاة'              },
          { label: 'درجة الحرارة أثناء التغطية (°C)'  },
          { label: 'الرطوبة أثناء التغطية (%)'        },
          { label: 'مدة عملية التغطية (دقيقة)'        }
        ]
      },
      {
        title: 'بعد الانتهاء',
        items: [
          { label: 'درجة الهواء بعد التغطية (°C)'     },
          { label: 'الرطوبة بعد التغطية (%)'          },
          { label: 'CO2 بعد التغطية (ppm)'             },
          { label: 'تعديلات المضخة / المرطّب'         },
          { label: 'صورة ما بعد التغطية'              },
          { label: 'توقيع المسؤول'                    },
          { label: 'ملاحظات ختامية'                   }
        ]
      },
      PHOTO_SECTION
    ]
  },

  // ── 4. CASE RUN ───────────────────────────────────────
  case_run: {
    tab:   '4 - نمو الميسيليوم',
    label: 'نمو الميسيليوم',
    targets: {
      air_temp:     [23, 24],
      compost_temp: [24, 25],
      humidity:     [90, 95],
      co2:          [5000, 7500]
    },
    sections: [
      {
        title: 'صباحاً 06:00',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'درجة الكومبوست (°C)'             },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         },
          { label: 'نسبة تغطية الميسيليوم (%)'        },
          { label: 'حالة الغطاء العلوي'               },
          { label: 'ملاحظات الصباح'                  }
        ]
      },
      {
        title: 'ظهراً 12:00',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      }
        ]
      },
      {
        title: 'مساءً 18:00',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'درجة الكومبوست (°C)'             },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         }
        ]
      },
      {
        title: 'ملاحظات اليوم',
        items: [
          { label: 'ملاحظات عامة / تقييم اليوم'      }
        ]
      },
      PHOTO_SECTION
    ]
  },

  // ── 5. PINNING ────────────────────────────────────────
  pinning: {
    tab:   '5 - تحفيز الإثمار',
    label: 'تحفيز الإثمار',
    targets: {
      air_temp: [16, 18],
      humidity: [85, 90],
      co2:      [0, 1000]
    },
    sections: [
      {
        title: 'خطوات الصدمة',
        items: [
          { label: 'هل تم خفض درجة الحرارة؟'          },
          { label: 'هل تم زيادة التهوية؟'              },
          { label: 'هل تم رش الماء البارد؟'            },
          { label: 'هل تم كشف الأكياس؟'               },
          { label: 'وقت بداية الصدمة'                 },
          { label: 'ملاحظات الصدمة'                   }
        ]
      },
      {
        title: 'القراءة 1',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         },
          { label: 'ملاحظات'                          }
        ]
      },
      {
        title: 'القراءة 2',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         },
          { label: 'ملاحظات'                          }
        ]
      },
      {
        title: 'القراءة 3',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         },
          { label: 'ملاحظات'                          }
        ]
      },
      {
        title: 'القراءة 4',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         },
          { label: 'ملاحظات'                          }
        ]
      },
      {
        title: 'التأكيد النهائي',
        items: [
          { label: 'عدد نقاط التثمير المرئية'         },
          { label: 'هل ظهرت رؤوس صغيرة (Pins)؟'      },
          { label: 'جودة الصدمة (ممتاز/جيد/ضعيف)'    },
          { label: 'هل نجحت مرحلة التحفيز؟'           },
          { label: 'توقيع المسؤول'                    },
          { label: 'ملاحظات ختامية'                   }
        ]
      },
      PHOTO_SECTION
    ]
  },

  // ── 6. WAITING ────────────────────────────────────────
  waiting: {
    tab:   '6 - انتظار الرؤوس',
    label: 'انتظار الرؤوس',
    targets: {
      air_temp: [16, 18],
      humidity: [85, 90],
      co2:      [800, 1000]
    },
    sections: [
      {
        title: 'صباحاً 06:00',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         },
          { label: 'حجم الرؤوس الملاحظة'              },
          { label: 'عدد الأكياس بها رؤوس'             },
          { label: 'هل يوجد تلوث؟'                    },
          { label: 'وصف التلوث إن وجد'                },
          { label: 'إجراء مُتّخذ'                      },
          { label: 'ملاحظات الصباح'                  }
        ]
      },
      {
        title: 'ظهراً 12:00',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         }
        ]
      },
      {
        title: 'مساءً 18:00',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         },
          { label: 'حجم الرؤوس الملاحظة'              },
          { label: 'هل الحصاد متوقع غداً؟'            },
          { label: 'ملاحظات المساء'                   }
        ]
      },
      PHOTO_SECTION
    ]
  },

  // ── 7. HARVEST ────────────────────────────────────────
  harvest: {
    tab:   '7 - الحصاد',
    label: 'الحصاد',
    targets: {
      air_temp: [17, 18],
      humidity: [85, 88],
      co2:      [800, 1200]
    },
    sections: [
      {
        title: '06:00 — قياسات الصباح الباكر',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         }
        ]
      },
      {
        title: '07:00 — بداية الحصاد',
        items: [
          { label: 'هل الرؤوس جاهزة للحصاد؟'         },
          { label: 'وزن الحصاد الجزء الأول (كغ)'      },
          { label: 'عدد الأكياس المحصودة (الدفعة 1)' }
        ]
      },
      {
        title: '08:00 — منتصف الحصاد',
        items: [
          { label: 'وزن الحصاد الجزء الثاني (كغ)'     },
          { label: 'عدد الأكياس المحصودة (الدفعة 2)' },
          { label: 'جودة المحصول (ممتاز/جيد/متوسط)'  }
        ]
      },
      {
        title: '12:00 — قياسات الظهر',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         }
        ]
      },
      {
        title: '16:00 — الحصاد المسائي',
        items: [
          { label: 'وزن الحصاد المسائي (كغ)'          },
          { label: 'ملاحظات الحصاد المسائي'           }
        ]
      },
      {
        title: '17:00 — التغليف والتوزيع',
        items: [
          { label: 'إجمالي وزن الحصاد اليومي (كغ)'   },
          { label: 'وجهة المبيعات'                    },
          { label: 'سعر البيع (دت/كغ)'                }
        ]
      },
      {
        title: '21:00 — إغلاق اليوم',
        items: [
          { label: 'درجة الهواء (°C)'                 },
          { label: 'الرطوبة (%)'                      },
          { label: 'CO2 (ppm)'                         },
          { label: 'هل تم الري بعد الحصاد؟'           },
          { label: 'ملاحظات نهاية اليوم'              },
          { label: 'توقيع المسؤول'                    }
        ]
      },
      PHOTO_SECTION
    ]
  },

  // ── 8. BETWEEN WAVES ──────────────────────────────────
  between: {
    tab:   '8 - بين الموجات',
    label: 'بين الموجات',
    sections: [
      {
        title: 'بعد الموجة مباشرة',
        items: [
          { label: 'رقم الموجة المنتهية'              },
          { label: 'إجمالي حصاد الموجة (كغ)'          },
          { label: 'هل تم تنظيف السطح؟'               },
          { label: 'هل تم إزالة جذور الفطر؟'          },
          { label: 'هل تم الرش بالماء؟'               },
          { label: 'درجة الحرارة بعد الموجة (°C)'     },
          { label: 'الرطوبة بعد الموجة (%)'           }
        ]
      },
      {
        title: 'بيانات الموجة المنتهية',
        items: [
          { label: 'مدة الموجة (أيام)'                },
          { label: 'متوسط حصاد يومي (كغ)'             },
          { label: 'أعلى يوم حصاد'                    },
          { label: 'ملاحظات الموجة'                   }
        ]
      },
      {
        title: 'انتظار الموجة الجديدة',
        items: [
          { label: 'أيام الراحة المتوقعة'             },
          { label: 'هل يوجد ميسيليوم جديد ظاهر؟'     },
          { label: 'تقدير تاريخ الموجة القادمة'       },
          { label: 'ملاحظات'                          }
        ]
      },
      PHOTO_SECTION
    ]
  },

  // ── 9. EMERGENCY ──────────────────────────────────────
  emergency: {
    tab:   '9 - طوارئ',
    label: 'طوارئ',
    sections: [
      {
        title: 'المشكلة',
        items: [
          { label: 'نوع الطارئ (تلوث/عطل/انقطاع كهرباء/أخرى)' }
        ]
      },
      {
        title: 'التفاصيل',
        items: [
          { label: 'الغرفة المتأثرة'                  },
          { label: 'مستوى الخطورة (عالي/متوسط/منخفض)' },
          { label: 'وقت الاكتشاف'                     },
          { label: 'الوصف التفصيلي'                   }
        ]
      },
      {
        title: 'الإجراءات',
        items: [
          { label: 'هل تم عزل المنطقة؟'               },
          { label: 'هل تم إعلام المسؤول؟'             },
          { label: 'الإجراء الأول المتخذ'             },
          { label: 'هل تم استدعاء متخصص؟'             },
          { label: 'المعدات المستخدمة'                },
          { label: 'المواد الكيميائية المستخدمة'      },
          { label: 'مدة التدخل (دقيقة)'               },
          { label: 'نتيجة التدخل'                     },
          { label: 'الأكياس المتضررة (عدد)'           },
          { label: 'الخسارة التقديرية (كغ)'            },
          { label: 'هل تم حل المشكلة؟'                }
        ]
      },
      {
        title: 'المتابعة',
        items: [
          { label: 'خطة المتابعة'                     },
          { label: 'توقيع المسؤول'                    }
        ]
      },
      PHOTO_SECTION
    ]
  }
};

// ─────────────────────────────────────────────────────────
// STAGE TIMELINE
// ─────────────────────────────────────────────────────────

var STAGES = [
  { id: 'setup',     label: 'استلام الأكياس',    dayStart: 1,  dayEnd: 1   },
  { id: 'spawn_run', label: 'انتشار الميسيليوم', dayStart: 2,  dayEnd: 16  },
  { id: 'casing',    label: 'التغطية',            dayStart: 17, dayEnd: 17  },
  { id: 'case_run',  label: 'نمو الميسيليوم',    dayStart: 18, dayEnd: 24  },
  { id: 'pinning',   label: 'تحفيز الإثمار',     dayStart: 25, dayEnd: 26  },
  { id: 'waiting',   label: 'انتظار الرؤوس',     dayStart: 27, dayEnd: 31  },
  { id: 'harvest',   label: 'الحصاد',            dayStart: 32, dayEnd: 999 }
];

// ─────────────────────────────────────────────────────────
// HEADER BUILDER
// ─────────────────────────────────────────────────────────

/**
 * Builds the flat header array for a given checklist definition.
 * Always: التاريخ | اسم العامل | رقم الدورة | <section items...> | وقت الإرسال
 */
function buildHeaders(cl) {
  var headers = ['التاريخ', 'اسم العامل', CYCLE_ID_HEADER];
  var sections = cl.sections || [];
  for (var i = 0; i < sections.length; i++) {
    var section = sections[i];
    var items   = section.items || [];
    for (var j = 0; j < items.length; j++) {
      headers.push(section.title + ' - ' + items[j].label);
    }
  }
  headers.push('وقت الإرسال');
  return headers;
}

// ─────────────────────────────────────────────────────────
// SETUP
// ─────────────────────────────────────────────────────────

/**
 * Main setup: run once from the Apps Script editor or menu.
 * Creates all tabs in order, builds dashboard, shares.
 */
function setupEverything() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // 1. Cycles tab first
  createCyclesTab(ss);

  // 2. Checklist tabs
  var keys = Object.keys(CHECKLISTS);
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    var cl  = CHECKLISTS[key];
    _ensureChecklistSheet(ss, cl);
  }

  // 3. Dashboard tab
  buildDashboard(ss);

  // 4. Remove default "Sheet1" if still present
  removeDefaultSheet(ss);

  // 5. Reorder tabs
  reorderTabs(ss);

  // 6. Share
  shareSpreadsheet(ss);

  SpreadsheetApp.getUi().alert(
    '✅ تم إعداد MAKNABIS بنجاح!\nالإصدار: ' + VERSION + '\n' + new Date().toLocaleString()
  );
}

/**
 * Creates (or resets headers of) the 🔄 الدورات tab.
 */
function createCyclesTab(ss) {
  var sheet = ss.getSheetByName(CYCLES_TAB);
  if (!sheet) {
    sheet = ss.insertSheet(CYCLES_TAB);
  }
  var range = sheet.getRange(1, 1, 1, CYCLES_COLUMNS.length);
  range.setValues([CYCLES_COLUMNS]);
  _styleHeaderRow(range, '#1a5276');
  sheet.setFrozenRows(1);
  sheet.setColumnWidth(1, 120);
  sheet.setColumnWidth(2, 180);
  sheet.setColumnWidth(3, 110);
  sheet.setColumnWidth(4, 110);
  sheet.setColumnWidth(5, 100);
  sheet.setColumnWidth(6, 130);
  sheet.setColumnWidth(7, 90);
  sheet.setColumnWidth(8, 100);
  sheet.setColumnWidth(9, 220);
  sheet.setColumnWidth(10, 160);
  return sheet;
}

/**
 * Ensures a checklist sheet exists with the correct header row.
 * Non-destructive: only touches row 1.
 */
function _ensureChecklistSheet(ss, cl) {
  var headers = buildHeaders(cl);
  var sheet   = ss.getSheetByName(cl.tab);
  if (!sheet) {
    sheet = ss.insertSheet(cl.tab);
  }
  var range = sheet.getRange(1, 1, 1, headers.length);
  range.setValues([headers]);
  _styleHeaderRow(range, '#1b4f72');
  sheet.setFrozenRows(1);
  sheet.setColumnWidth(1, 100); // التاريخ
  sheet.setColumnWidth(2, 120); // اسم العامل
  sheet.setColumnWidth(3, 120); // رقم الدورة

  // Apply target-based conditional formatting where applicable
  if (cl.targets) {
    applyTargetAlerts(sheet, headers, cl.targets);
  }
  return sheet;
}

/**
 * Applies bold white text on coloured background to a header range.
 */
function _styleHeaderRow(range, bgColor) {
  range.setFontWeight('bold');
  range.setBackground(bgColor || '#1a5276');
  range.setFontColor('#ffffff');
  range.setHorizontalAlignment('center');
}

/**
 * Removes the default "Sheet1" (or "ورقة1") tab if it has no data.
 */
function removeDefaultSheet(ss) {
  var defaults = ['Sheet1', 'ورقة1', 'Feuille 1', 'Hoja 1'];
  for (var i = 0; i < defaults.length; i++) {
    var s = ss.getSheetByName(defaults[i]);
    if (s && s.getLastRow() <= 1) {
      try { ss.deleteSheet(s); } catch (e) { /* ignore */ }
    }
  }
}

/**
 * Reorders tabs: Cycles → Checklists 1-9 → Dashboard.
 */
function reorderTabs(ss) {
  var order = [CYCLES_TAB];
  var keys  = Object.keys(CHECKLISTS);
  for (var i = 0; i < keys.length; i++) {
    order.push(CHECKLISTS[keys[i]].tab);
  }
  order.push(DASHBOARD_TAB);

  for (var idx = 0; idx < order.length; idx++) {
    var s = ss.getSheetByName(order[idx]);
    if (s) ss.moveActiveSheet && ss.setActiveSheet(s) && ss.moveActiveSheet(idx + 1);
  }
}

/**
 * Shares the spreadsheet per CONFIG.shareWith.
 */
function shareSpreadsheet(ss) {
  var shareList = CONFIG.shareWith || [];
  for (var i = 0; i < shareList.length; i++) {
    var entry = shareList[i];
    try {
      if (entry.role === 'editor') {
        ss.addEditor(entry.email);
      } else {
        ss.addViewer(entry.email);
      }
    } catch (e) {
      Logger.log('Share failed for ' + entry.email + ': ' + e.message);
    }
  }
}

// ─────────────────────────────────────────────────────────
// CONDITIONAL FORMATTING (target alerts)
// ─────────────────────────────────────────────────────────

/**
 * Applies conditional formatting rules to numeric env columns
 * based on targets: { air_temp:[min,max], humidity:[min,max], co2:[min,max], ... }
 */
function applyTargetAlerts(sheet, headers, targets) {
  var rules = [];
  var lastRow = 1000;

  var envMap = {
    'درجة الهواء (°C)':      targets.air_temp,
    'درجة الكومبوست (°C)':  targets.compost_temp,
    'الرطوبة (%)':            targets.humidity,
    'CO2 (ppm)':              targets.co2
  };

  for (var i = 0; i < headers.length; i++) {
    // Match any header whose base label appears in envMap
    var hdr  = headers[i];
    var base = hdr.indexOf(' - ') >= 0 ? hdr.split(' - ').pop() : hdr;
    var range = targets[base] || envMap[base];
    if (!range) continue;

    var col    = columnLetter(i + 1);
    var colRef = '$' + col + '2:$' + col + lastRow;
    var min    = range[0];
    var max    = range[1];

    var rangeObj = sheet.getRange(2, i + 1, lastRow - 1, 1);

    // Too low → blue background
    rules.push(
      SpreadsheetApp.newConditionalFormatRule()
        .whenNumberLessThan(min)
        .setBackground('#d6eaf8')
        .setFontColor('#1a5276')
        .setRanges([rangeObj])
        .build()
    );
    // Too high → red background
    rules.push(
      SpreadsheetApp.newConditionalFormatRule()
        .whenNumberGreaterThan(max)
        .setBackground('#fadbd8')
        .setFontColor('#922b21')
        .setRanges([rangeObj])
        .build()
    );
    // In range → green background
    rules.push(
      SpreadsheetApp.newConditionalFormatRule()
        .whenNumberBetween(min, max)
        .setBackground('#d5f5e3')
        .setFontColor('#1d8348')
        .setRanges([rangeObj])
        .build()
    );
  }

  if (rules.length) {
    sheet.setConditionalFormatRules(rules);
  }
}

/**
 * Converts a 1-based column number to a letter string (e.g. 1 → A, 27 → AA).
 */
function columnLetter(n) {
  var s = '';
  while (n > 0) {
    var r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

// ─────────────────────────────────────────────────────────
// DASHBOARD TAB (formula-based)
// ─────────────────────────────────────────────────────────

/**
 * Builds the 📊 لوحة القيادة sheet with 6 sections:
 *   1. KPIs            – harvest total, today, efficiency, bags
 *   2. Env averages    – AVERAGEIF formulas per session
 *   3. Alert counts    – COUNTIF out-of-range cells
 *   4. Harvest last 10 – QUERY from harvest tab
 *   5. Waves history   – QUERY summary per wave
 *   6. Emergency summary – QUERY from emergency tab
 */
function buildDashboard(ss) {
  var sheet = ss.getSheetByName(DASHBOARD_TAB);
  if (!sheet) {
    sheet = ss.insertSheet(DASHBOARD_TAB);
  } else {
    sheet.clearContents();
    sheet.clearFormats();
  }

  var harvestTab   = CHECKLISTS.harvest.tab;
  var emergencyTab = CHECKLISTS.emergency.tab;

  // Determine column letters for harvest
  var hHeaders = buildHeaders(CHECKLISTS.harvest);
  var hDateIdx  = hHeaders.indexOf('التاريخ') + 1;
  var hWorkerIdx = hHeaders.indexOf('اسم العامل') + 1;
  // harvest weight columns — look for sections containing weight labels
  var hKg1Col = _findHeaderCol(hHeaders, '07:00 — بداية الحصاد - وزن الحصاد الجزء الأول (كغ)');
  var hKg2Col = _findHeaderCol(hHeaders, '08:00 — منتصف الحصاد - وزن الحصاد الجزء الثاني (كغ)');
  var hKg3Col = _findHeaderCol(hHeaders, '16:00 — الحصاد المسائي - وزن الحصاد المسائي (كغ)');
  var hTotalCol = _findHeaderCol(hHeaders, '17:00 — التغليف والتوزيع - إجمالي وزن الحصاد اليومي (كغ)');
  var hCycleCol = hHeaders.indexOf(CYCLE_ID_HEADER) + 1;

  var R = 1; // current row

  // ── Section 1: Title ─────────────────────────────────
  sheet.getRange(R, 1, 1, 5).merge()
       .setValue('📊 MAKNABIS — لوحة القيادة')
       .setFontSize(16).setFontWeight('bold')
       .setBackground('#1a5276').setFontColor('#ffffff')
       .setHorizontalAlignment('center');
  sheet.getRange(R, 6).setValue('=NOW()').setNumberFormat('yyyy-mm-dd hh:mm');
  R += 2;

  // ── Section 2: KPIs ──────────────────────────────────
  _dashSectionHeader(sheet, R, 'مؤشرات الأداء الرئيسية');
  R++;
  var kpiData = [
    ['إجمالي الحصاد (كغ)',    hTotalCol > 0 ? '=IFERROR(SUM(\'' + harvestTab + '\'!' + columnLetter(hTotalCol) + '2:' + columnLetter(hTotalCol) + '),0)' : 0],
    ['حصاد اليوم (كغ)',       hTotalCol > 0 ? '=IFERROR(SUMIF(\'' + harvestTab + '\'!A:A,TEXT(TODAY(),"yyyy-mm-dd"),\'' + harvestTab + '\'!' + columnLetter(hTotalCol) + ':' + columnLetter(hTotalCol) + '),0)' : 0],
    ['عدد أيام الحصاد',       '=IFERROR(COUNTA(\'' + harvestTab + '\'!A2:A)-COUNTBLANK(\'' + harvestTab + '\'!A2:A),0)'],
    ['حالات الطوارئ',          '=IFERROR(COUNTA(\'' + emergencyTab + '\'!A2:A)-COUNTBLANK(\'' + emergencyTab + '\'!A2:A),0)']
  ];
  for (var ki = 0; ki < kpiData.length; ki++) {
    sheet.getRange(R + ki, 1).setValue(kpiData[ki][0]).setFontWeight('bold');
    sheet.getRange(R + ki, 2).setFormula(String(kpiData[ki][1]));
  }
  R += kpiData.length + 2;

  // ── Section 3: Env averages (spawn_run) ──────────────
  _dashSectionHeader(sheet, R, 'متوسطات البيئة — انتشار الميسيليوم');
  R++;
  var spHeaders = buildHeaders(CHECKLISTS.spawn_run);
  var spTab     = CHECKLISTS.spawn_run.tab;
  var spEnvCols = _findEnvCols(spHeaders, spTab);
  if (spEnvCols.length) {
    sheet.getRange(R, 1).setValue('القياس').setFontWeight('bold');
    sheet.getRange(R, 2).setValue('المتوسط').setFontWeight('bold');
    R++;
    for (var ei = 0; ei < spEnvCols.length; ei++) {
      var ec = spEnvCols[ei];
      sheet.getRange(R, 1).setValue(ec.label);
      sheet.getRange(R, 2).setFormula('=IFERROR(AVERAGE(\'' + spTab + '\'!' + ec.col + '2:' + ec.col + '),"-")');
      R++;
    }
  }
  R += 2;

  // ── Section 4: Harvest last 10 ───────────────────────
  _dashSectionHeader(sheet, R, 'آخر 10 سجلات حصاد');
  R++;
  if (hHeaders.length > 3) {
    var qCols = 'Col1,Col' + hCycleCol + (hTotalCol > 0 ? ',Col' + hTotalCol : '');
    sheet.getRange(R, 1).setFormula(
      '=IFERROR(QUERY(\'' + harvestTab + '\'!A:' + columnLetter(hHeaders.length) + ',' +
      '"SELECT A,' + (hCycleCol > 0 ? columnLetter(hCycleCol) + ',' : '') +
      (hTotalCol > 0 ? columnLetter(hTotalCol) : 'B') +
      ' WHERE A IS NOT NULL ORDER BY A DESC LIMIT 10 LABEL A \'التاريخ\'",1),"لا توجد بيانات")'
    );
    R += 12;
  }
  R += 2;

  // ── Section 5: Emergency summary ─────────────────────
  _dashSectionHeader(sheet, R, 'ملخص الطوارئ');
  R++;
  var emHeaders = buildHeaders(CHECKLISTS.emergency);
  var emTypeCol = _findHeaderCol(emHeaders, 'المشكلة - نوع الطارئ (تلوث/عطل/انقطاع كهرباء/أخرى)');
  var emLvlCol  = _findHeaderCol(emHeaders, 'التفاصيل - مستوى الخطورة (عالي/متوسط/منخفض)');
  if (emHeaders.length > 3) {
    sheet.getRange(R, 1).setFormula(
      '=IFERROR(QUERY(\'' + emergencyTab + '\'!A:' + columnLetter(emHeaders.length) + ',' +
      '"SELECT A,B,C' +
      (emTypeCol > 0 ? ',' + columnLetter(emTypeCol) : '') +
      (emLvlCol  > 0 ? ',' + columnLetter(emLvlCol)  : '') +
      ' WHERE A IS NOT NULL ORDER BY A DESC LIMIT 20 LABEL A \'التاريخ\',B \'العامل\',C \'الدورة\'",1),"لا توجد طوارئ")'
    );
    R += 22;
  }

  // Formatting
  sheet.setColumnWidth(1, 280);
  sheet.setColumnWidth(2, 200);
  sheet.setColumnWidth(3, 160);
  sheet.setColumnWidth(4, 160);
  sheet.setColumnWidth(5, 160);
  sheet.setFrozenRows(1);

  return sheet;
}

function _dashSectionHeader(sheet, row, title) {
  var range = sheet.getRange(row, 1, 1, 6).merge();
  range.setValue(title)
       .setFontWeight('bold')
       .setBackground('#2e86c1')
       .setFontColor('#ffffff')
       .setFontSize(12)
       .setHorizontalAlignment('right');
}

function _findHeaderCol(headers, label) {
  for (var i = 0; i < headers.length; i++) {
    if (headers[i] === label) return i + 1;
  }
  return 0;
}

function _findEnvCols(headers, tabName) {
  var result = [];
  var envKeywords = ['درجة الهواء', 'درجة الكومبوست', 'الرطوبة', 'CO2'];
  for (var i = 0; i < headers.length; i++) {
    var hdr = headers[i];
    for (var k = 0; k < envKeywords.length; k++) {
      if (hdr.indexOf(envKeywords[k]) >= 0) {
        result.push({ label: hdr, col: columnLetter(i + 1) });
        break;
      }
    }
  }
  return result;
}

// ─────────────────────────────────────────────────────────
// extractEnvSeries — used by room/dashboard payloads
// ─────────────────────────────────────────────────────────

/**
 * Extracts a named environmental time-series from checklist rows.
 * fieldSubstring: partial header match e.g. 'درجة الهواء'
 * Returns array of { date, value } sorted chronologically.
 */
function extractEnvSeries(sheetKey, fieldSubstring, cycleId, limit) {
  limit = limit || 100;
  var result = buildRecentPayload(sheetKey, cycleId, limit);
  if (!result.ok || !result.rows.length) return [];

  var headers = result.headers;
  var colIdx  = -1;
  var dateIdx = -1;

  for (var i = 0; i < headers.length; i++) {
    if (headers[i] === 'التاريخ') dateIdx = i;
    if (headers[i].indexOf(fieldSubstring) >= 0 && colIdx < 0) colIdx = i;
  }

  if (colIdx < 0) return [];

  var series = [];
  var rows   = result.rows.slice().reverse(); // chronological order
  for (var r = 0; r < rows.length; r++) {
    var vals  = rows[r].values;
    var v     = parseFloat(vals[colIdx]);
    if (!isNaN(v)) {
      series.push({
        date:  dateIdx >= 0 ? String(vals[dateIdx]).substring(0, 10) : '',
        value: v
      });
    }
  }
  return series;
}

// ─────────────────────────────────────────────────────────
// PHOTO UPLOAD
// ─────────────────────────────────────────────────────────

/**
 * Uploads a base64-encoded photo to Google Drive under MAKNABIS - مرفقات.
 * Returns the public shareable URL, or '' on error.
 */
function uploadPhoto(base64Data, filename) {
  try {
    if (!base64Data || base64Data.indexOf(',') === -1) return '';
    var folders = DriveApp.getFoldersByName('MAKNABIS - مرفقات');
    var folder  = folders.hasNext() ? folders.next() : DriveApp.createFolder('MAKNABIS - مرفقات');
    var contentType = base64Data.substring(base64Data.indexOf(':') + 1, base64Data.indexOf(';'));
    var bytes   = Utilities.base64Decode(base64Data.split(',')[1]);
    var blob    = Utilities.newBlob(bytes, contentType, filename || ('photo_' + Date.now() + '.jpg'));
    var file    = folder.createFile(blob);
    file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
    return file.getUrl();
  } catch (e) {
    Logger.log('uploadPhoto error: ' + e.message);
    return '';
  }
}

// ─────────────────────────────────────────────────────────
// HTTP HANDLERS
// ─────────────────────────────────────────────────────────

function doGet(e) {
  try {
    var params = (e && e.parameter) ? e.parameter : {};
    var key    = params.key  || '';
    var mode   = params.mode || '';

    // Health check — no auth needed
    if (mode === 'ping' || params.ping === '1') {
      return jsonOut({
        ok:         true,
        version:    VERSION,
        service:    'MAKNABIS Growing API',
        timestamp:  new Date().toISOString(),
        checklists: Object.keys(CHECKLISTS)
      });
    }

    // cycle_active — no auth needed (lightweight)
    if (mode === 'cycle_active') {
      return jsonOut({ ok: true, active: getActiveCycle() });
    }

    // All other modes require key
    if (key !== DASHBOARD_KEY) {
      return jsonOut({ ok: false, error: 'unauthorized' });
    }

    if (mode === 'cycles') {
      return jsonOut({
        ok:      true,
        version: CHECKLISTS_VERSION,
        cycles:  listCycles(),
        active:  getActiveCycle()
      });
    }

    if (mode === 'dashboard') {
      return jsonOut(buildDashboardPayload(params.cycle_id || null));
    }

    if (mode === 'room') {
      return jsonOut(buildRoomPayload(params.cycle_id || null));
    }

    if (mode === 'recent') {
      return jsonOut(buildRecentPayload(
        params.sheet    || '',
        params.cycle_id || null,
        parseInt(params.limit || '50', 10)
      ));
    }

    // Default: service info
    return jsonOut({
      ok:         true,
      version:    CHECKLISTS_VERSION,
      service:    'MAKNABIS Growing API',
      timestamp:  new Date().toISOString(),
      checklists: Object.keys(CHECKLISTS)
    });

  } catch (err) {
    return jsonOut({ ok: false, error: err.message, stack: err.stack });
  }
}

function doPost(e) {
  try {
    var raw = (e && e.postData && e.postData.contents) ? e.postData.contents : '{}';
    var data;
    try {
      data = JSON.parse(raw);
    } catch (parseErr) {
      // Try URLSearchParams: payload=<json>
      var decoded = decodeURIComponent(raw.replace(/^payload=/, ''));
      data = JSON.parse(decoded);
    }

    var type = data.type     || '';
    var key  = data.key      || data.password || '';

    // All actions require key
    if (key !== DASHBOARD_KEY) {
      return jsonOut({ ok: false, error: 'unauthorized' });
    }

    if (type === 'cycle_create') {
      return jsonOut(createCycle(data.data || data));
    }
    if (type === 'cycle_set_active') {
      return jsonOut(setActiveCycle(data.cycle_id || (data.data && data.data.cycle_id)));
    }
    if (type === 'cycle_close') {
      return jsonOut(closeCycle(data.cycle_id || (data.data && data.data.cycle_id)));
    }
    if (type === 'delete_row') {
      return jsonOut(deleteRowFromChecklist(data.sheet, data.row_number));
    }
    if (type === 'uploadPhoto') {
      return jsonOut({ ok: true, url: uploadPhoto(data.base64, data.filename) });
    }
    if (type === 'checklist') {
      return jsonOut(appendToChecklist(data.data || data));
    }

    return jsonOut({ ok: false, error: 'Unknown type: ' + type });

  } catch (err) {
    return jsonOut({ ok: false, error: err.message, stack: err.stack });
  }
}

/**
 * Wraps any object as a JSON ContentService output.
 */
function jsonOut(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ─────────────────────────────────────────────────────────
// CYCLE CRUD
// ─────────────────────────────────────────────────────────

/**
 * Lists all cycles from the 🔄 الدورات tab.
 * Returns an array of cycle objects with both Arabic keys and English aliases.
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
    if (!row[0] && !row[1]) continue; // skip blank rows
    var obj = {};
    for (var j = 0; j < headers.length; j++) {
      var val = row[j];
      obj[headers[j]] = (val instanceof Date)
        ? Utilities.formatDate(val, Session.getScriptTimeZone(), 'yyyy-MM-dd')
        : val;
    }
    obj._row       = i + 2;
    // English aliases
    obj.cycle_id         = obj['رقم الدورة'];
    obj.name             = obj['الاسم'];
    obj.start_date       = obj['تاريخ البدء'];
    obj.expected_harvest = obj['الحصاد المتوقع'];
    obj.room             = obj['الغرفة'];
    obj.substrate        = obj['نوع الركيزة'];
    obj.bag_count        = obj['عدد الأكياس'];
    obj.status           = obj['الحالة'];
    obj.notes            = obj['ملاحظات'];
    obj.created_at       = obj['تاريخ الإنشاء'];
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
 * Gets a cycle by its ID string.
 */
function _getCycleById(cycleId) {
  var cycles = listCycles();
  for (var i = 0; i < cycles.length; i++) {
    if (cycles[i].cycle_id === cycleId) return cycles[i];
  }
  return null;
}

/**
 * Generates the next cycle ID in format B-YYYY-NN.
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
 * Creates a new cycle and optionally activates it.
 * data: { name, start_date, expected_harvest, room, substrate, bag_count, notes, set_active }
 */
function createCycle(data) {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(CYCLES_TAB);
  if (!sheet) throw new Error('Cycles tab not found — run setupEverything first');

  var cycleId = _nextCycleId();
  var status  = data.set_active ? 'active' : 'planning';
  var now     = _fmtDateTime(new Date());
  var startDate = data.start_date || _fmtDate(new Date());

  if (data.set_active) {
    _demoteActiveCycles();
  }

  var row = [
    cycleId,
    data.name            || '',
    startDate,
    data.expected_harvest || '',
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
 * Sets a cycle as active; all previously active cycles become 'planning'.
 */
function setActiveCycle(cycleId) {
  if (!cycleId) return { ok: false, error: 'cycle_id required' };

  var ss        = SpreadsheetApp.getActiveSpreadsheet();
  var sheet     = ss.getSheetByName(CYCLES_TAB);
  if (!sheet) throw new Error('Cycles tab not found');

  var cycles    = listCycles();
  var found     = false;
  var statusCol = CYCLES_COLUMNS.indexOf('الحالة') + 1;

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

  var ss        = SpreadsheetApp.getActiveSpreadsheet();
  var sheet     = ss.getSheetByName(CYCLES_TAB);
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
 * Internal: demotes all currently active cycles to 'planning'.
 */
function _demoteActiveCycles() {
  var ss        = SpreadsheetApp.getActiveSpreadsheet();
  var sheet     = ss.getSheetByName(CYCLES_TAB);
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
 * Appends a new row to a checklist tab.
 *
 * data must contain:
 *   sheet_key  (e.g. 'spawn_run') or sheet (tab name)
 *   cycle_id   — injected into the CYCLE_ID_HEADER column
 *   Fields keyed by full header string "Section - Label" OR by just label
 *   Photo fields may be base64; they are uploaded before saving.
 *
 * Returns { ok, row, sheet }
 */
function appendToChecklist(data) {
  var sheetKey = data.sheet_key || data.sheet || '';
  var cl       = CHECKLISTS[sheetKey];
  if (!cl) {
    // Maybe it was passed as a tab name — try to find matching key
    var keys = Object.keys(CHECKLISTS);
    for (var ki = 0; ki < keys.length; ki++) {
      if (CHECKLISTS[keys[ki]].tab === sheetKey) {
        cl = CHECKLISTS[keys[ki]];
        sheetKey = keys[ki];
        break;
      }
    }
    if (!cl) return { ok: false, error: 'Unknown sheet_key: ' + sheetKey };
  }

  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(cl.tab);
  if (!sheet) return { ok: false, error: 'Tab not found: ' + cl.tab };

  var headers  = buildHeaders(cl);
  var cycleId  = data.cycle_id || data[CYCLE_ID_HEADER] || '';
  var now      = _fmtDateTime(new Date());

  // Pre-process photo fields: upload any base64 values
  var processedData = {};
  var fieldKeys = Object.keys(data);
  for (var fk = 0; fk < fieldKeys.length; fk++) {
    var fKey = fieldKeys[fk];
    var fVal = data[fKey];
    if (typeof fVal === 'string' && fVal.indexOf('data:image') === 0) {
      // base64 image — upload to Drive
      processedData[fKey] = uploadPhoto(fVal, sheetKey + '_' + Date.now() + '.jpg');
    } else {
      processedData[fKey] = fVal;
    }
  }

  var rowData = [];
  for (var i = 0; i < headers.length; i++) {
    var h = headers[i];
    if (h === 'التاريخ') {
      rowData.push(processedData['التاريخ'] || _fmtDate(new Date()));
    } else if (h === 'اسم العامل') {
      rowData.push(processedData['اسم العامل'] || processedData['العامل'] || '');
    } else if (h === CYCLE_ID_HEADER) {
      rowData.push(cycleId);
    } else if (h === 'وقت الإرسال') {
      rowData.push(now);
    } else {
      // Try full header match first, then just the label after ' - '
      var val = processedData[h];
      if (val === undefined || val === null) {
        var labelPart = h.indexOf(' - ') >= 0 ? h.split(' - ').pop() : h;
        val = processedData[labelPart];
      }
      rowData.push((val !== undefined && val !== null) ? val : '');
    }
  }

  sheet.appendRow(rowData);
  var newRow = sheet.getLastRow();

  _invalidateCache();

  return { ok: true, row: newRow, sheet: cl.tab };
}

// ─────────────────────────────────────────────────────────
// RECENT PAYLOAD
// ─────────────────────────────────────────────────────────

/**
 * Reads recent rows from a checklist tab.
 *
 * sheetKeyOrTab: CHECKLISTS key (e.g. 'spawn_run') or tab name
 * cycleId:       optional filter
 * limit:         max rows to return (most recent first)
 *
 * Returns { ok, headers, rows: [{row, values}], sheet }
 */
function buildRecentPayload(sheetKeyOrTab, cycleId, limit) {
  limit = limit || 50;

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

  var cycleIdColIdx = -1;
  for (var i = 0; i < headers.length; i++) {
    if (headers[i] === CYCLE_ID_HEADER) { cycleIdColIdx = i; break; }
  }

  var rows = [];
  for (var r = allData.length - 1; r >= 0; r--) {
    var rowValues = allData[r];
    // Skip blank rows
    if (!rowValues[0] && !rowValues[1] && !rowValues[2]) continue;
    // Filter by cycle_id
    if (cycleId && cycleIdColIdx >= 0 && rowValues[cycleIdColIdx] !== cycleId) continue;

    var serialized = rowValues.map(function(v) {
      return (v instanceof Date)
        ? Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss')
        : v;
    });

    rows.push({ row: r + 2, values: serialized });
    if (rows.length >= limit) break;
  }

  return { ok: true, headers: headers, rows: rows, sheet: tabName };
}

// ─────────────────────────────────────────────────────────
// DELETE ROW
// ─────────────────────────────────────────────────────────

/**
 * Deletes a specific data row (rowNumber >= 2) from a checklist tab.
 * Returns { ok, deleted, sheet }
 */
function deleteRowFromChecklist(sheetKeyOrTab, rowNumber) {
  rowNumber = parseInt(rowNumber, 10);
  if (isNaN(rowNumber) || rowNumber < 2) {
    return { ok: false, error: 'Invalid row_number — must be >= 2' };
  }

  var tabName = sheetKeyOrTab;
  if (CHECKLISTS[sheetKeyOrTab]) {
    tabName = CHECKLISTS[sheetKeyOrTab].tab;
  }

  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(tabName);
  if (!sheet) return { ok: false, error: 'Sheet not found: ' + tabName };

  var lastRow = sheet.getLastRow();
  if (rowNumber > lastRow) {
    return { ok: false, error: 'Row ' + rowNumber + ' does not exist (lastRow=' + lastRow + ')' };
  }

  sheet.deleteRow(rowNumber);
  _invalidateCache();
  return { ok: true, deleted: rowNumber, sheet: tabName };
}

// ─────────────────────────────────────────────────────────
// STAGE DETECTION
// ─────────────────────────────────────────────────────────

function _calcDayNumber(startDateStr) {
  if (!startDateStr) return 1;
  var start = new Date(startDateStr);
  var today = new Date();
  start.setHours(0, 0, 0, 0);
  today.setHours(0, 0, 0, 0);
  var diff = Math.floor((today - start) / (1000 * 60 * 60 * 24)) + 1;
  return diff < 1 ? 1 : diff;
}

function _detectStage(dayNumber) {
  for (var i = 0; i < STAGES.length; i++) {
    var s = STAGES[i];
    if (dayNumber >= s.dayStart && dayNumber <= s.dayEnd) return s;
  }
  return STAGES[STAGES.length - 1]; // fallback: harvest
}

// ─────────────────────────────────────────────────────────
// ROOM PAYLOAD
// ─────────────────────────────────────────────────────────

/**
 * Builds the room monitoring payload for the 3D room view.
 * cycleId: optional; uses active cycle if null.
 */
function buildRoomPayload(cycleId) {
  var cycle = cycleId ? _getCycleById(cycleId) : getActiveCycle();
  if (!cycle) return { ok: false, error: 'No active cycle found' };

  var dayNumber  = _calcDayNumber(cycle.start_date);
  var stage      = _detectStage(dayNumber);
  var stageId    = stage.id;
  var targets    = (CHECKLISTS[stageId] && CHECKLISTS[stageId].targets) ? CHECKLISTS[stageId].targets : {};
  var bagCount   = parseInt(cycle.bag_count, 10) || 0;

  var latestReading = _getLatestReading(stageId, cycle.cycle_id);
  var harvestData   = _getHarvestStats(cycle.cycle_id);
  var emergencyCount = _countRows('emergency', cycle.cycle_id);
  var alerts        = _generateAlerts(latestReading, targets, stageId, dayNumber, cycle);

  return {
    ok:              true,
    cycle:           cycle,
    day_number:      dayNumber,
    stage_id:        stageId,
    stage_label:     stage.label,
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
 * Gets the 3 most recent readings (morning/noon/evening) for a stage/cycle.
 */
function _getLatestReading(stageId, cycleId) {
  var result = buildRecentPayload(stageId, cycleId, 3);
  if (!result.ok || !result.rows.length) return null;

  var headers   = result.headers;
  var latestRow = result.rows[0].values;
  var latestObj = {};
  for (var i = 0; i < headers.length; i++) {
    latestObj[headers[i]] = latestRow[i];
  }

  return {
    date:    latestObj['التاريخ']    || '',
    worker:  latestObj['اسم العامل'] || latestObj['العامل'] || '',
    morning: _extractSession(latestObj, 'صباحاً 06:00'),
    noon:    _extractSession(latestObj, 'ظهراً 12:00'),
    evening: _extractSession(latestObj, 'مساءً 18:00')
  };
}

/**
 * Extracts env readings for a section by looking for headers matching the section title prefix.
 */
function _extractSession(obj, sectionTitle) {
  var session = {};
  var envKeys = {
    'درجة الهواء (°C)':       'air_temp',
    'درجة الكومبوست (°C)':   'compost_temp',
    'الرطوبة (%)':             'humidity',
    'CO2 (ppm)':               'co2'
  };
  var objKeys = Object.keys(obj);
  for (var i = 0; i < objKeys.length; i++) {
    var hdr = objKeys[i];
    if (hdr.indexOf(sectionTitle) === 0) {
      var labelPart = hdr.indexOf(' - ') >= 0 ? hdr.split(' - ').pop() : '';
      var envKey    = envKeys[labelPart];
      if (envKey) {
        var v = parseFloat(obj[hdr]);
        if (!isNaN(v)) session[envKey] = v;
      }
    }
  }
  return Object.keys(session).length ? session : null;
}

/**
 * Returns harvest stats: today's kg and total kg for the cycle.
 */
function _getHarvestStats(cycleId) {
  var result = buildRecentPayload('harvest', cycleId, 500);
  if (!result.ok || !result.rows.length) return { today: 0, total: 0 };

  var headers  = result.headers;
  var dateIdx  = headers.indexOf('التاريخ');
  // Collect all weight column indices
  var weightIdxs = [];
  for (var hi = 0; hi < headers.length; hi++) {
    var h = headers[hi];
    if (h.indexOf('(كغ)') >= 0 && h.indexOf('إجمالي') < 0) {
      weightIdxs.push(hi);
    }
  }
  // Prefer total column if available
  var totalIdx = -1;
  for (var ti = 0; ti < headers.length; ti++) {
    if (headers[ti].indexOf('إجمالي وزن الحصاد اليومي') >= 0) { totalIdx = ti; break; }
  }

  var todayStr = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
  var total    = 0;
  var today    = 0;

  for (var r = 0; r < result.rows.length; r++) {
    var row = result.rows[r].values;
    var sum = 0;
    if (totalIdx >= 0) {
      sum = parseFloat(row[totalIdx] || 0) || 0;
    } else {
      for (var wi = 0; wi < weightIdxs.length; wi++) {
        sum += parseFloat(row[weightIdxs[wi]] || 0) || 0;
      }
    }
    total += sum;
    var rowDate = String(row[dateIdx] || '').substring(0, 10);
    if (rowDate === todayStr) today += sum;
  }

  return {
    today: Math.round(today * 100) / 100,
    total: Math.round(total * 100) / 100
  };
}

/**
 * Counts non-blank rows in a checklist for a given cycle.
 */
function _countRows(sheetKey, cycleId) {
  var result = buildRecentPayload(sheetKey, cycleId, 1000);
  if (!result.ok) return 0;
  return result.rows.length;
}

/**
 * Generates alert messages comparing latest readings to stage targets.
 */
function _generateAlerts(latestReading, targets, stageId, dayNumber, cycle) {
  var alerts = [];

  if (!latestReading) {
    alerts.push({ level: 'warning', message: 'لا توجد قراءات مسجلة لهذه الدورة اليوم' });
    return alerts;
  }

  var sessions = [
    { key: 'morning', label: 'الصباحية' },
    { key: 'noon',    label: 'الظهرية'  },
    { key: 'evening', label: 'المسائية' }
  ];

  for (var s = 0; s < sessions.length; s++) {
    var ses  = sessions[s];
    var data = latestReading[ses.key];
    if (!data) continue;
    _checkRange(alerts, data.air_temp,     targets.air_temp,     'درجة الهواء ' + ses.label);
    _checkRange(alerts, data.compost_temp, targets.compost_temp, 'درجة الكومبوست ' + ses.label);
    _checkRange(alerts, data.humidity,     targets.humidity,     'الرطوبة ' + ses.label);
    _checkRange(alerts, data.co2,          targets.co2,          'CO2 ' + ses.label);
  }

  // Stage transition hints
  if (stageId === 'spawn_run' && dayNumber > 16) {
    alerts.push({ level: 'info', message: 'الدورة في يوم ' + dayNumber + ' — يجب الانتقال إلى مرحلة التغطية' });
  }
  if (stageId === 'casing' && dayNumber > 17) {
    alerts.push({ level: 'info', message: 'انتهت مرحلة التغطية — انتقل إلى مرحلة نمو الميسيليوم' });
  }

  return alerts;
}

/**
 * Pushes an alert if value is outside [min, max].
 */
function _checkRange(alerts, value, range, label) {
  if (!range || value === '' || value === null || value === undefined) return;
  var v = parseFloat(value);
  if (isNaN(v)) return;
  if (v < range[0]) {
    alerts.push({ level: 'warning', message: label + ': ' + v + ' — أقل من الحد الأدنى ' + range[0] });
  } else if (v > range[1]) {
    alerts.push({ level: 'danger',  message: label + ': ' + v + ' — أعلى من الحد الأقصى ' + range[1] });
  }
}

// ─────────────────────────────────────────────────────────
// DASHBOARD PAYLOAD (API)
// ─────────────────────────────────────────────────────────

/**
 * Builds the full dashboard JSON payload for the web app.
 * cycleId: optional; uses active cycle if null.
 */
function buildDashboardPayload(cycleId) {
  var cycle = cycleId ? _getCycleById(cycleId) : getActiveCycle();

  var kpis           = _buildKpis(cycle);
  var recentReadings = _buildRecentReadings(cycle);
  var waves          = _buildWaveSummary(cycle);
  var workerActivity = _buildWorkerActivity(cycle);
  var emergencySummary = _buildEmergencySummary(cycle);
  var envAverages    = _buildEnvAverages(cycle);
  var alerts         = [];

  if (cycle) {
    var dayNumber = _calcDayNumber(cycle.start_date);
    var stage     = _detectStage(dayNumber);
    var targets   = (CHECKLISTS[stage.id] && CHECKLISTS[stage.id].targets) ? CHECKLISTS[stage.id].targets : {};
    var latestR   = _getLatestReading(stage.id, cycle.cycle_id);
    alerts        = _generateAlerts(latestR, targets, stage.id, dayNumber, cycle);
  }

  return {
    ok:               true,
    version:          CHECKLISTS_VERSION,
    cycle:            cycle,
    kpis:             kpis,
    recent_readings:  recentReadings,
    alerts:           alerts,
    waves:            waves,
    worker_activity:  workerActivity,
    emergency_summary: emergencySummary,
    env_averages:     envAverages,
    generated_at:     new Date().toISOString()
  };
}

function _buildKpis(cycle) {
  if (!cycle) return { error: 'No active cycle' };
  var harvestStats = _getHarvestStats(cycle.cycle_id);
  var dayNumber    = _calcDayNumber(cycle.start_date);
  var stage        = _detectStage(dayNumber);
  var bagCount     = parseInt(cycle.bag_count, 10) || 0;
  var emergencies  = _countRows('emergency', cycle.cycle_id);
  var efficiency   = bagCount > 0 ? Math.round((harvestStats.total / bagCount) * 1000) / 1000 : 0;

  return {
    day_number:            dayNumber,
    stage_id:              stage.id,
    stage_label:           stage.label,
    bag_count:             bagCount,
    harvest_total_kg:      harvestStats.total,
    harvest_today_kg:      harvestStats.today,
    efficiency_kg_per_bag: efficiency,
    emergency_count:       emergencies,
    cycle_id:              cycle.cycle_id,
    cycle_name:            cycle.name,
    start_date:            cycle.start_date
  };
}

function _buildRecentReadings(cycle) {
  if (!cycle) return [];
  var dayNumber = _calcDayNumber(cycle.start_date);
  var stage     = _detectStage(dayNumber);
  var result    = buildRecentPayload(stage.id, cycle.cycle_id, 10);
  if (!result.ok || !result.rows.length) return [];
  var headers = result.headers;
  var out     = [];
  for (var i = 0; i < result.rows.length; i++) {
    var vals = result.rows[i].values;
    var obj  = {};
    for (var j = 0; j < headers.length; j++) obj[headers[j]] = vals[j];
    obj._row = result.rows[i].row;
    out.push(obj);
  }
  return out;
}

function _buildWaveSummary(cycle) {
  if (!cycle) return [];
  var result = buildRecentPayload('harvest', cycle.cycle_id, 500);
  if (!result.ok || !result.rows.length) return [];

  var headers   = result.headers;
  var dateIdx   = headers.indexOf('التاريخ');
  var totalIdx  = -1;
  for (var ti = 0; ti < headers.length; ti++) {
    if (headers[ti].indexOf('إجمالي وزن الحصاد اليومي') >= 0) { totalIdx = ti; break; }
  }
  if (totalIdx < 0) {
    // fallback: sum all (كغ) columns except إجمالي
    totalIdx = -1; // will sum manually
  }

  var rows    = result.rows.slice().reverse(); // chronological
  var waves   = [];
  var current = { wave: 1, dates: [], total: 0 };

  for (var i = 0; i < rows.length; i++) {
    var row  = rows[i].values;
    var date = String(row[dateIdx] || '').substring(0, 10);
    var kg   = 0;
    if (totalIdx >= 0) {
      kg = parseFloat(row[totalIdx] || 0) || 0;
    } else {
      for (var hi = 0; hi < headers.length; hi++) {
        if (headers[hi].indexOf('(كغ)') >= 0 && headers[hi].indexOf('إجمالي') < 0) {
          kg += parseFloat(row[hi] || 0) || 0;
        }
      }
    }

    if (current.dates.length > 0) {
      var lastDate = new Date(current.dates[current.dates.length - 1]);
      var thisDate = new Date(date);
      var gapDays  = Math.floor((thisDate - lastDate) / (1000 * 60 * 60 * 24));
      if (gapDays > 5) {
        waves.push({ wave: current.wave, total_kg: Math.round(current.total * 100) / 100, days: current.dates.length });
        current = { wave: current.wave + 1, dates: [], total: 0 };
      }
    }
    current.dates.push(date);
    current.total += kg;
  }

  if (current.dates.length) {
    waves.push({ wave: current.wave, total_kg: Math.round(current.total * 100) / 100, days: current.dates.length });
  }
  return waves;
}

function _buildWorkerActivity(cycle) {
  if (!cycle) return [];
  var workerCounts = {};
  var sheetKeys    = Object.keys(CHECKLISTS);
  for (var k = 0; k < sheetKeys.length; k++) {
    var result    = buildRecentPayload(sheetKeys[k], cycle.cycle_id, 500);
    if (!result.ok || !result.rows.length) continue;
    var workerIdx = -1;
    for (var hi = 0; hi < result.headers.length; hi++) {
      if (result.headers[hi] === 'اسم العامل' || result.headers[hi] === 'العامل') {
        workerIdx = hi; break;
      }
    }
    if (workerIdx < 0) continue;
    for (var r = 0; r < result.rows.length; r++) {
      var worker = String(result.rows[r].values[workerIdx] || '').trim();
      if (worker) workerCounts[worker] = (workerCounts[worker] || 0) + 1;
    }
  }
  var out = [];
  var workers = Object.keys(workerCounts);
  for (var w = 0; w < workers.length; w++) {
    out.push({ worker: workers[w], entries: workerCounts[workers[w]] });
  }
  out.sort(function(a, b) { return b.entries - a.entries; });
  return out;
}

function _buildEmergencySummary(cycle) {
  if (!cycle) return { total: 0, high: 0, medium: 0, low: 0, records: [] };
  var result = buildRecentPayload('emergency', cycle.cycle_id, 100);
  if (!result.ok || !result.rows.length) {
    return { total: 0, high: 0, medium: 0, low: 0, records: [] };
  }

  var headers  = result.headers;
  var lvlIdx   = -1;
  var typeIdx  = -1;
  for (var hi = 0; hi < headers.length; hi++) {
    if (headers[hi].indexOf('مستوى الخطورة') >= 0) lvlIdx  = hi;
    if (headers[hi].indexOf('نوع الطارئ')    >= 0) typeIdx = hi;
  }

  var counts = { total: result.rows.length, high: 0, medium: 0, low: 0, records: [] };
  for (var r = 0; r < result.rows.length; r++) {
    var row = result.rows[r].values;
    var lvl = String(row[lvlIdx] || '').trim();
    if (lvl.indexOf('عالي') >= 0)    counts.high++;
    else if (lvl.indexOf('متوسط') >= 0) counts.medium++;
    else if (lvl.indexOf('منخفض') >= 0) counts.low++;
    counts.records.push({
      date: String(row[0] || '').substring(0, 10),
      type: typeIdx >= 0 ? row[typeIdx] : '',
      level: lvl
    });
  }
  return counts;
}

function _buildEnvAverages(cycle) {
  if (!cycle) return {};
  var dayNumber = _calcDayNumber(cycle.start_date);
  var stage     = _detectStage(dayNumber);
  var result    = buildRecentPayload(stage.id, cycle.cycle_id, 30);
  if (!result.ok || !result.rows.length) return {};

  var headers = result.headers;
  var envKeys = ['درجة الهواء', 'درجة الكومبوست', 'الرطوبة', 'CO2'];
  var sums    = {};
  var counts  = {};

  for (var r = 0; r < result.rows.length; r++) {
    var row = result.rows[r].values;
    for (var hi = 0; hi < headers.length; hi++) {
      var h = headers[hi];
      for (var ek = 0; ek < envKeys.length; ek++) {
        if (h.indexOf(envKeys[ek]) >= 0) {
          var v = parseFloat(row[hi]);
          if (!isNaN(v)) {
            sums[h]   = (sums[h]   || 0) + v;
            counts[h] = (counts[h] || 0) + 1;
          }
        }
      }
    }
  }

  var avgs = {};
  var keys = Object.keys(sums);
  for (var ki = 0; ki < keys.length; ki++) {
    var k = keys[ki];
    avgs[k] = Math.round((sums[k] / counts[k]) * 100) / 100;
  }
  return avgs;
}

// ─────────────────────────────────────────────────────────
// PROPERTIES & CACHE HELPERS
// ─────────────────────────────────────────────────────────

function _setProp(key, value) {
  PropertiesService.getScriptProperties().setProperty(key, JSON.stringify(value));
}

function _getProp(key, defaultVal) {
  var raw = PropertiesService.getScriptProperties().getProperty(key);
  if (raw === null || raw === undefined) return defaultVal !== undefined ? defaultVal : null;
  try { return JSON.parse(raw); } catch (e) { return raw; }
}

/**
 * Invalidates cached payloads after any write operation.
 */
function _invalidateCache() {
  try {
    var cache = CacheService.getScriptCache();
    cache.remove('dashboard_payload_v1');
    cache.remove('room_payload_v1');
  } catch (e) { /* ignore */ }
}

// ─────────────────────────────────────────────────────────
// DATE UTILITIES
// ─────────────────────────────────────────────────────────

function _fmtDate(d) {
  if (!d) return '';
  if (!(d instanceof Date)) d = new Date(d);
  return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd');
}

function _fmtDateTime(d) {
  if (!d) return '';
  if (!(d instanceof Date)) d = new Date(d);
  return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
}

// ─────────────────────────────────────────────────────────
// MENU
// ─────────────────────────────────────────────────────────

function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('🍄 MAKNABIS')
    .addItem('⚙️ إعداد كامل (أول مرة)', 'setupEverything')
    .addSeparator()
    .addItem('🔄 إعادة بناء رؤوس الأوراق', 'rebuildAllHeaders')
    .addItem('📊 إعادة بناء لوحة القيادة', 'rebuildDashboard')
    .addSeparator()
    .addItem('📌 الدورة النشطة', 'showActiveCycle')
    .addItem('📋 قائمة الدورات', 'showCyclesList')
    .addSeparator()
    .addItem('ℹ️ معلومات النظام', 'showSystemInfo')
    .addToUi();
}

function rebuildAllHeaders() {
  var ss   = SpreadsheetApp.getActiveSpreadsheet();
  var keys = Object.keys(CHECKLISTS);
  for (var i = 0; i < keys.length; i++) {
    _ensureChecklistSheet(ss, CHECKLISTS[keys[i]]);
  }
  SpreadsheetApp.getUi().alert('✅ تم إعادة بناء جميع رؤوس الأوراق.');
}

function rebuildDashboard() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  buildDashboard(ss);
  SpreadsheetApp.getUi().alert('✅ تم إعادة بناء لوحة القيادة.');
}

function showActiveCycle() {
  var cycle = getActiveCycle();
  var msg   = cycle
    ? [
        'الدورة النشطة:',
        'المعرف: '    + cycle.cycle_id,
        'الاسم: '     + cycle.name,
        'تاريخ البدء: ' + cycle.start_date,
        'اليوم رقم: ' + _calcDayNumber(cycle.start_date),
        'المرحلة: '   + _detectStage(_calcDayNumber(cycle.start_date)).label,
        'عدد الأكياس: ' + cycle.bag_count
      ].join('\n')
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
    return [c.cycle_id, c.name, c.status, c.start_date].join(' | ');
  });
  SpreadsheetApp.getUi().alert('الدورات المسجلة:\n' + lines.join('\n'));
}

function showSystemInfo() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var info = [
    'MAKNABIS System Info',
    '─────────────────────────────',
    'Version:            ' + VERSION,
    'Checklists version: ' + CHECKLISTS_VERSION,
    'Timezone:           ' + Session.getScriptTimeZone(),
    'Spreadsheet:        ' + ss.getName(),
    'Checklist tabs:     ' + Object.keys(CHECKLISTS).length,
    'Operators:          ' + CONFIG.operators.join(', '),
    'Generated:          ' + new Date().toISOString()
  ].join('\n');
  SpreadsheetApp.getUi().alert(info);
}

// ─────────────────────────────────────────────────────────
// TEST HELPERS (run manually from Apps Script editor)
// ─────────────────────────────────────────────────────────

function testRoomPayload() {
  var payload = buildRoomPayload(null);
  Logger.log(JSON.stringify(payload, null, 2));
}

function testDashboardPayload() {
  var payload = buildDashboardPayload(null);
  Logger.log(JSON.stringify(payload, null, 2));
}

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

function testAppendSpawnRun() {
  var result = appendToChecklist({
    sheet_key:    'spawn_run',
    'التاريخ':    _fmtDate(new Date()),
    'اسم العامل': 'Imed',
    'cycle_id':   'B-2026-01',
    'صباحاً 06:00 - درجة الهواء (°C)':        23.5,
    'صباحاً 06:00 - درجة الكومبوست (°C)':    24.1,
    'صباحاً 06:00 - الرطوبة (%)':             92,
    'صباحاً 06:00 - CO2 (ppm)':               12000,
    'ظهراً 12:00 - درجة الهواء (°C)':         23.8,
    'ظهراً 12:00 - الرطوبة (%)':              91,
    'مساءً 18:00 - درجة الهواء (°C)':         23.2,
    'مساءً 18:00 - درجة الكومبوست (°C)':     24.0,
    'مساءً 18:00 - الرطوبة (%)':              93,
    'مساءً 18:00 - CO2 (ppm)':                11000,
    'ملاحظات اليوم - ملاحظات عامة / تقييم اليوم': 'يوم جيد — الميسيليوم ينتشر بشكل طبيعي'
  });
  Logger.log(JSON.stringify(result));
}

function testHarvestStats() {
  var active = getActiveCycle();
  if (!active) { Logger.log('No active cycle'); return; }
  var stats = _getHarvestStats(active.cycle_id);
  Logger.log(JSON.stringify(stats));
}

function testRecentPayload() {
  var result = buildRecentPayload('spawn_run', null, 5);
  Logger.log(JSON.stringify(result, null, 2));
}

function testBuildHeaders() {
  var keys = Object.keys(CHECKLISTS);
  for (var i = 0; i < keys.length; i++) {
    var h = buildHeaders(CHECKLISTS[keys[i]]);
    Logger.log(keys[i] + ' (' + h.length + ' cols): ' + h.slice(0, 5).join(', ') + ' ...');
  }
}

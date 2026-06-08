# MAKNABIS — دليل النشر الكامل

## الملفات المطلوبة

| الملف | المكان | الدور |
|---|---|---|
| `Code.gs` | Growing Apps Script | بيانات الزراعة |
| `Code-finance.gs` | Finance Apps Script | البيانات المالية |
| `Code-ai.gs` | AI Apps Script (مشروع منفصل) | المساعد الذكي |
| `config.js` | Netlify | الإعدادات المركزية |
| `owner.html` | Netlify | تطبيق المالك |
| `growing.html` | Netlify | تطبيق عامل الزراعة |
| `finance.html` | Netlify | تطبيق العامل المالي |
| `dashboard.html` | Netlify | لوحة المراقبة |
| `room3d.html` | Netlify | الغرفة ثلاثية الأبعاد |
| `chat.html` | Netlify | المساعد الذكي |
| `index.html` | Netlify | الموقع العام (MAKNABIS) |

---

## الخطوة 1 — نشر Apps Script (الزراعة)

1. افتح مشروع Apps Script المرتبط بجدول بيانات الزراعة
2. احذف كل الكود القديم
3. الصق محتوى `Code.gs` كاملاً
4. احفظ (Ctrl+S)
5. اضغط **Run → setupEverything** (أعطِه صلاحيات عند الطلب)
6. اضغط **Deploy → New deployment → Web app**
   - Execute as: **Me**
   - Who has access: **Anyone**
7. انسخ رابط `/exec`

---

## الخطوة 2 — نشر Apps Script (المالية)

1. افتح مشروع Apps Script المرتبط بجدول بيانات المالية
2. الصق محتوى `Code-finance.gs`
3. اضغط **Run → setupEverything**
4. **Deploy → New deployment → Web app** (نفس الإعدادات)
5. انسخ رابط `/exec`

---

## الخطوة 3 — نشر Apps Script (الذكاء الاصطناعي)

1. أنشئ مشروع Apps Script **جديد** (منفصل تماماً)
2. الصق محتوى `Code-ai.gs`
3. اضغط **Project Settings → Script Properties** → أضف:
   - `GEMINI_API_KEY` = (مفتاحك من https://aistudio.google.com/apikey)
   - `GROWING_API_URL` = (رابط /exec من الخطوة 1)
   - `DASHBOARD_KEY` = `FARM2026`
4. اضغط **Run → testGemini** للتأكد من أن المفتاح يعمل
5. **Deploy → New deployment → Web app**
6. انسخ رابط `/exec`

---

## الخطوة 4 — تعديل config.js

افتح الملف `config.js` وعدّل الأسطر الثلاثة:

```javascript
GROWING_URL: 'الصق رابط exec الزراعة هنا',
FINANCE_URL: 'الصق رابط exec المالية هنا',
AI_URL:      'الصق رابط exec الذكاء الاصطناعي هنا',
```

---

## الخطوة 5 — نشر Netlify

### الطريقة السريعة (30 ثانية):
1. افتح https://app.netlify.com/drop
2. اسحب وأسقط **كل الملفات** (الـ HTML + config.js)
3. انتظر 20 ثانية → ستحصل على رابط مثل `maknabis.netlify.app`
4. اضغط **Sign up** للاحتفاظ بالموقع

### بعد النشر — إعداد اسم مخصص:
- Site settings → Change site name → اكتب `maknabis`
- ستصبح عناوين التطبيقات:
  - الموقع العام: `maknabis.netlify.app`
  - تطبيق المالك: `maknabis.netlify.app/owner.html`
  - عامل الزراعة: `maknabis.netlify.app/growing.html`
  - العامل المالي: `maknabis.netlify.app/finance.html`

---

## الخطوة 6 — التحقق

بعد النشر، تحقق من كل خطوة:

- [ ] افتح `owner.html` → يجب أن يتصل تلقائياً (بدون إدخال URLs)
- [ ] اضغط على تبويب الرئيسية → يجب أن تظهر بيانات الدورة
- [ ] اضغط على تبويب الدورات → أنشئ دورة تجريبية
- [ ] افتح `growing.html` → يجب أن تظهر الدورة النشطة
- [ ] افتح `finance.html` → سجّل دخول بكلمة المرور `FARM2026`
- [ ] افتح `dashboard.html` → يجب أن تظهر البيانات مباشرة
- [ ] افتح `room3d.html` → يجب أن تظهر الغرفة ثلاثية الأبعاد
- [ ] افتح `chat.html` → اضغط "ملخص اليوم"
- [ ] افتح `index.html` → الموقع العام

---

## عناوين الحفظ (bookmark) للعمال

| الشخص | الرابط |
|---|---|
| أنت (Imed) | `netlify-url/owner.html` |
| عامل الزراعة | `netlify-url/growing.html` |
| عامل المالية | `netlify-url/finance.html` |

للإضافة إلى الشاشة الرئيسية في الهاتف:
- **iPhone**: Safari → Share → "Add to Home Screen"
- **Android**: Chrome → ⋮ → "Add to Home screen"

---

## الإعدادات الجاهزة

- كلمة مرور لوحة القيادة: `FARM2026`
- كلمة مرور المالية: `FARM2026`
- البريد الإلكتروني: `maknabis.tn@gmail.com`
- الهاتف: `+216 25 982 388`
- العنوان: `نهج 4860 السيجومي، تونس 2000`

# Design System — توحيد التصميم

## الخط (Typography)
- **الخط الوحيد:** `Tajawal` (مع fallback: system-ui, -apple-system, Segoe UI, Roboto).
- يتم تحميله من Google Fonts في `base.html`:
  ```html
  <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;600;700&display=swap" rel="stylesheet">
  ```
- **لا استخدام Cairo أو خطوط أخرى** في الشاشات الجديدة؛ للتوحيد نعتمد Tajawal في كل القوالب التي تمتد من `base.html`.

## الألوان (Colors)
المصدر الوحيد هو متغيرات CSS في `base.html` (أو في هذا الملف عند التوسع):

| المتغير | الاستخدام | القيمة الافتراضية |
|---------|-----------|-------------------|
| `--primary` | أزرار أساسية، روابط، عناوين | #1565C0 |
| `--secondary` | عناوين فرعية، تأكيد | #0D47A1 |
| `--bg` | خلفية الصفحة | #F8FAFC |
| `--success` | نجاح، مدفوع | #27AE60 |
| `--danger` | خطر، حذف، غير مدفوع | #E74C3C |
| `--text` | نص أساسي | #212529 |
| `--muted` | نص ثانوي | #6c757d |
| `--link` | روابط | #0d6efd |

للشاشات (screens.css):
- `--ops-blue` = نفس `--primary`
- `--ops-blue-dark` = نفس `--secondary`
- `--ops-blue-light` = خلفية هادئة للعناوين (#e3f2fd)

## المكونات (Components)

### الأزرار
- `border-radius: 8px`, `font-weight: 600`, `padding: 10px 16px`
- Primary: خلفية `--primary`, hover أغمق قليلاً
- توحيد كل الأزرار عبر classes: `btn`, `btn-primary`, `btn-outline-primary`, `btn-success`, `btn-danger`

### الجداول
- غلاف: `.screen-table-wrap` أو `.table-responsive`
- جدول: `.screen-table` أو `.table`
- رأس: لون `--primary` (#1565c0), نص أبيض, `padding: 0.75rem 1rem`
- صفوف: hover خفيف (مثل rgba(21,101,192,.06))
- أرقام: `font-variant-numeric: tabular-nums`, محاذاة لليمين للأرقام (`.text-end`)

### البطاقات (Cards)
- `.card` أو `.ops-form-card` / `.screen-section`
- `border-radius: 12px`, ظل خفيف, حدود رفيعة
- رأس البطاقة: خلفية فاتحة (مثل `--ops-blue-light`), خط عريض, حد سفلي

### الشارات (Badges)
- للحالة: success (أخضر), warning (برتقالي), danger (أحمر), info (أزرق)
- أحجام صغيرة: `font-size: 0.75rem`, `padding: 0.25rem 0.6rem`, `border-radius: 6px`

## القالب الموحد للصفحة (Page Layout)
- غلاف: `div.container.py-4.ops-layout.hub-wrap`
- هيدر: `div.ops-header-bar` مع:
  - `span.ops-icon` (أيقونة)
  - عنوان `h1.ops-title` + `span.ops-subtitle`
  - `div.ops-actions` (أزرار العودة، إجراءات)
- محتوى: `div.ops-body` → `main.ops-main` مع `ops-form-card` أو `screen-section`

## الطباعة
- إخفاء: `.print-hide`, `.no-print`
- في `base.html`: إخفاء الـ navbar والـ back button والـ app-messages عند الطباعة

## الوضع الداكن (Dark)
- يفعّل عبر `body.dark` (حسب إعداد المستخدم).
- الألوان والحدود معرّفة في `base.html` لـ cards, tables, buttons, inputs.

---

**ملاحظة:** أي شاشة جديدة يجب أن:
1. تمتد من `base.html`
2. تستخدم نفس المتغيرات (لا ألوان هاردكود جديدة)
3. تستخدم نفس فئات الجداول والأزرار والبطاقات
4. لا تضيف خطوط إضافية (Cairo أو غيرها) إلا بموافقة موثقة.

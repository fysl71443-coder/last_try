# قائمة التحقق من الترجمة (i18n) — للمطورين

## مصدر النصوص الموحد
- **الملفات**: `translations/ar/LC_MESSAGES/messages.po` و `translations/en/LC_MESSAGES/messages.po`
- **الأداة**: Flask-Babel (gettext). في القوالب الدالة `_()` متاحة تلقائياً؛ في بايثون استخدم `from flask_babel import gettext as _`.

---

## قواعد إلزامية

### ١. رسائل Flash
كل استدعاء `flash(...)` يجب أن يمرر نصاً مترجماً:
```python
from flask_babel import gettext as _
flash(_('تم الحفظ بنجاح'), 'success')
flash(_('الفترة المالية مغلقة لهذا التاريخ.'), 'danger')
```
**لا تكتب** نصوصاً ثابتة بالعربية أو الإنجليزية فقط داخل `flash(...)`.

### ٢. التلميحات (Tooltips)
في القوالب استخدم الترجمة في `title` أو `data-bs-title`:
```html
<button title="{{ _('حفظ التغييرات') }}">...</button>
<span data-bs-toggle="tooltip" title="{{ _('توضيح الحقل') }}">...</span>
```

### ٣. Placeholder
في حقول الإدخال:
```html
<input placeholder="{{ _('ابحث بالاسم أو الرقم...') }}">
```

### ٤. التسميات (Labels)
جميع `<label>` وعناوين النماذج والأقسام:
```html
<label>{{ _('التاريخ') }}</label>
<h2>{{ _('إضافة مصروف') }}</h2>
```

### ٥. عناوين الأعمدة في الجداول
رؤوس الجداول يجب أن تكون قابلة للترجمة:
```html
<th>{{ _('التاريخ') }}</th>
<th>{{ _('المبلغ') }}</th>
```

### ٦. أزرار الإجراءات
نص كل زر:
```html
<button>{{ _('حفظ') }}</button>
<button>{{ _('طباعة') }}</button>
<button>{{ _('إقفال السنة') }}</button>
```

---

## المطبوعات (PDF / HTML للطباعة)
- في **قوالب الطباعة** استخدم `get_locale()` لتعيين اللغة والاتجاه:
  - `lang="{{ get_locale() or 'ar' }}"` و `dir="{{ 'rtl' if (get_locale() or 'ar') == 'ar' else 'ltr' }}"`
- جميع العناوين والنصوص داخل قالب الطباعة يجب أن تمر عبر `{{ _('...') }}` حتى يعكس المطبوع اللغة المختارة.
- إذا تقرير معين **لا يدعم لغة** محددة، اعرض رسالة تنبيه للمستخدم (مثلاً: "هذا التقرير متوفر بالعربية فقط").

---

## إضافة ترجمات جديدة
1. أضف النص بالإنجليزية (أو العربي) كـ **msgid** في الكود أو القالب داخل `_('النص')`.
2. استخرج الرسائل: `pybabel extract -F babel.cfg -o messages.pot .`
3. حدّث ملفات .po: `pybabel update -i messages.pot -d translations`
4. أضف الترجمة في `translations/ar/LC_MESSAGES/messages.po` و `translations/en/LC_MESSAGES/messages.po` (حقل msgstr).
5. Compile: `pybabel compile -d translations` (أو السكربت الموجود في المشروع).

---

## الاختبار
- غيّر اللغة من الواجهة (رابط EN أو ع في الشريط العلوي).
- تحقق أن **كل** النصوص في الصفحة (بما فيها flash بعد إجراء) تتحول بدون قص أو تشوه.
- افتح صفحة طباعة (ميزان مراجعة، فاتورة، كشف حساب) وتأكد أن اللغة والاتجاه يطابقان اللغة المختارة.

---

## تقرير التنفيذ (Execution Report)

تم تنفيذ إصلاحات i18n وفق فحص فعلي على المستودع:

| البند | الحالة بعد التنفيذ |
|--------|---------------------|
| **Flash Messages** | ✅ تم إلزام جميع استدعاءات `flash()` باستخدام `_()` في: `app.py`, `app/routes.py`, `routes/reports.py`, `routes/suppliers.py`, `routes/journal.py`, `routes/inventory.py`, `routes/purchases.py`, `routes/vat.py`, `routes/expenses.py`, `routes/customers.py`, `routes/sales.py`. |
| **قوالب الطباعة (Print/PDF)** | ✅ تم توحيد `lang` و `dir` في قوالب الطباعة باستخدام `get_locale()` في: `balance_sheet_print.html`, `trial_balance_print.html`, `income_statement_print.html`, `vat_declaration_print.html`, `audit_report_print.html`, `receipt_print.html`, `invoice_print.html`, `order_slip.html`, `report_template.html`, `base_embed.html`, `batch.html`, `receipt_print.html`. وتم تغليف النصوص الظاهرة في بعضها بـ `{{ _('...') }}` (مثل `balance_sheet_print.html`, `report_template.html`). |
| **قوالب الواجهة (UI)** | ✅ تم تطبيق `{{ _('...') }}` على النصوص الثابتة في: `login.html` (مع `get_locale()` لـ lang/dir), `base.html`, `dashboard.html`, `settings.html`, `menu.html`. قوالب مثل `customers.html`, `invoices.html` كانت تستخدم `_()` مسبقاً. |
| **ملفات الترجمة (PO)** | ⚠️ الملفات موجودة؛ **يجب** إعادة استخراج وتحديث وتجميع الرسائل بعد إضافة النصوص الجديدة. |

### خطوات إلزامية بعد هذا التحديث

1. **استخراج الرسائل**:  
   `pybabel extract -F babel.cfg -o messages.pot .`
2. **تحديث ملفات .po**:  
   `pybabel update -i messages.pot -d translations`
3. **إكمال حقول msgstr** في `translations/ar/LC_MESSAGES/messages.po` و `translations/en/LC_MESSAGES/messages.po` للنصوص الجديدة.
4. **تجميع الترجمة**:  
   `pybabel compile -d translations` (أو السكربت `compile_translations.py` إن وُجد).
5. **اختبار**: تغيير اللغة من الواجهة + التحقق من رسائل Flash وصفحات الطباعة.

بعد تنفيذ الخطوات أعلاه يمكن إصدار تقرير اعتماد نهائي وإغلاق بند الترجمة رسمياً.

---

## تحديد القوالب ووضع الترجمة

### قوالب تم تعديلها (نصوص → gettext + lang/dir حيث يلزم)

| القالب | التعديلات |
|--------|-----------|
| **login.html** | `lang`/`dir` من `get_locale()`، `_()` للعنوان والـ Company و(اختياري) و alt الصورة، رسائل JS عبر `\| tojson`. |
| **base.html** | عنوان الصفحة الافتراضي، عناوين روابط اللغة والرجوع والخروج، alt الشعار. |
| **dashboard.html** | جميع عناوين البطاقات والنص الفرعي و«المحاسبة والتدقيق» مغلفة بـ `{{ _('...') }}`. |
| **settings.html** | عنوان الصفحة، الإعدادات، General, VAT, China Town, Place India، aria-label إغلاق التنبيه. |
| **menu.html** | نصوص «إضافة أصناف»، «في القسم»، placeholder ترتيب القسم. |
| **balance_sheet_print.html** | Company، «المركز المالي / الميزانية العمومية». |
| **report_template.html** | الترويسة، التاريخ، التقرير، الإجمالي، تذييل الطباعة، زر طباعة. |

### قوالب أخرى (105 ملف HTML)

يُنصح بمراجعة كل قالب وضمان:

- أي **نص ظاهر ثابت** (عناوين، أزرار، تسميات، placeholders، tooltips، alt، aria-label) مغلف بـ `{{ _('...') }}`.
- قوالب **الطباعة** تحتوي على `lang="{{ get_locale() or 'ar' }}"` و `dir="{{ 'rtl' if (get_locale() or 'ar') == 'ar' else 'ltr' }}"` في `<html>`.
- النصوص داخل **JavaScript** في القالب تُمرَّر عبر `{{ _('النص') | tojson }}` لتجنب مشاكل الاقتباس.

---

## مرجع
- الفحص الشامل للواجهة والترجمة: **docs/I18N_AND_UI_AUDIT.md**
- جدول التقييم لكل شاشة: داخل نفس الملف (القسم ٧).

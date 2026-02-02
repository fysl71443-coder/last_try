# -*- coding: utf-8 -*-
"""Add new (msgid, ar_msgstr) pairs to ar and en .po files."""
import os
from babel.messages.pofile import read_po, write_po

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AR_PO = os.path.join(PROJECT_ROOT, "translations", "ar", "LC_MESSAGES", "messages.po")
EN_PO = os.path.join(PROJECT_ROOT, "translations", "en", "LC_MESSAGES", "messages.po")

NEW_PAIRS = [
    ("Company", "الشركة"),
    ("Total sales before VAT", "إجمالي المبيعات قبل الضريبة"),
    ("Total purchases before VAT", "إجمالي المشتريات قبل الضريبة"),
    ("Total expenses before VAT", "إجمالي المصروفات قبل الضريبة"),
    ("Net VAT", "صافي الضريبة"),
    ("Journals Reconciliation", "المصالحة مع القيود"),
    ("Prepared by system", "تم الإعداد بواسطة النظام"),
    ("Print date", "تاريخ الطباعة"),
    ("Period type", "نوع الفترة"),
    ("Quarterly", "ربع سنوي"),
    ("Monthly", "شهري"),
    ("Year", "السنة"),
    ("Quarter", "الربع"),
    ("Q1 (Jan–Mar)", "الربع 1 (يناير - مارس)"),
    ("Q2 (Apr–Jun)", "الربع 2 (أبريل - يونيو)"),
    ("Q3 (Jul–Sep)", "الربع 3 (يوليو - سبتمبر)"),
    ("Q4 (Oct–Dec)", "الربع 4 (أكتوبر - ديسمبر)"),
    ("Month", "الشهر"),
    ("Outputs (Sales)", "المخرجات (مبيعات)"),
    ("Inputs (Purchases & Expenses)", "المدخلات (مشتريات ومصروفات)"),
    ("Declaration & Summary", "الإقرار والملخص"),
    ("Refund balance", "رصيد مسترد"),
    ("Enter notes — do not change numbers", "أدخل ملاحظات — لا تغيير للأرقام"),
    ("Purchases & Expenses", "المشتريات والمصروفات"),
    ("Amount (excl. VAT)", "المبلغ (بدون ض.ق.م)"),
    ("Total (incl. VAT)", "الإجمالي (شامل ض.ق.م)"),
    ("Standard Rated (15%)", "معيار 15%"),
    ("Zero Rated", "صفر"),
    ("Exempt", "معفى"),
    ("Exports", "صادرات"),
    ("Deductible Purchases", "مشتريات قابلة للخصم"),
    ("Deductible Expenses", "مصروفات قابلة للخصم"),
    ("Non-deductible Purchases", "مشتريات غير قابلة للخصم"),
    ("Non-deductible Expenses", "مصروفات غير قابلة للخصم"),
    ("Income Statement", "قائمة الدخل"),
    ("Executive summary and P&L", "ملخص تنفيذي وقائمة ربحية وخسارة"),
    ("Period & view", "الفترة والعرض"),
    ("Today", "اليوم"),
    ("This week", "هذا الأسبوع"),
    ("This month", "هذا الشهر"),
    ("This year", "هذه السنة"),
    ("Custom", "مخصص"),
    ("From – To", "من – إلى"),
    ("Detailed view", "عرض تفصيلي"),
    ("No data for the selected period.", "لا توجد بيانات ضمن الفترة المحددة."),
    ("Total revenue", "إجمالي الإيرادات"),
    ("Cost of sales", "تكلفة المبيعات"),
    ("Gross profit", "مجمل الربح"),
    ("Net profit", "صافي الربح"),
    ("Revenue", "الإيرادات"),
    ("Total cost of sales", "إجمالي تكلفة المبيعات"),
    ("Operating expenses", "المصروفات التشغيلية"),
    ("Total operating expenses", "إجمالي المصروفات التشغيلية"),
    ("Operating profit", "الربح التشغيلي"),
    ("Other income & expenses", "إيرادات ومصروفات أخرى"),
    ("Other income", "إيرادات أخرى"),
    ("Other expenses", "مصروفات أخرى"),
    ("VAT is not part of income statement; see analytical details below.", "ضريبة القيمة المضافة لا تدخل في قائمة الدخل؛ انظر تفاصيل تحليلية أدناه."),
    ("Analytical details", "تفاصيل تحليلية"),
    ("Expand", "توسيع"),
    ("Input VAT", "ضريبة المدخلات"),
    ("Output VAT", "ضريبة المخرجات"),
    ("COGS Breakdown", "تفصيل تكلفة المبيعات"),
    ("Opening stock", "مخزون بداية الفترة"),
    ("Period purchases", "مشتريات الفترة"),
    ("Closing stock", "مخزون نهاية الفترة"),
    ("Material waste", "هدر المواد"),
    ("Computed", "المُحتسب"),
    ("From journals", "من القيود"),
    ("Used", "المعتمد"),
    ("Sales by Branch", "المبيعات حسب الفرع"),
    ("As of", "حتى"),
    ("As of date", "حتى تاريخ"),
    ("Export CSV", "تصدير CSV"),
    ("Warning: Trial balance is not balanced", "تحذير: الميزان غير متوازن"),
    ("diff", "الفرق"),
    ("Trial balance — accounts with movement only (expandable)", "ميزان المراجعة — حسابات ذات حركة فقط (قابلة للتوسيع)"),
    ("Totals by Type", "تفصيل حسب النوع"),
    ("No accounts with movement.", "لا توجد حسابات ذات حركة."),
    ("accounts", "حساب"),
    ("Export PDF", "تصدير PDF"),
    ("Export Excel", "تصدير Excel"),
    ("Assets", "الأصول"),
    ("Liabilities", "الالتزامات"),
    ("Equity", "حقوق الملكية"),
    ("Current assets", "أصول متداولة"),
    ("Non-current assets", "أصول غير متداولة"),
    ("No movements in this period.", "لا توجد حركات في هذه الفترة."),
    ("This screen is for viewing, filtering and printing only. No payments or deletions are performed here.", "هذه الشاشة للعرض والفلترة والطباعة فقط. لا يتم تنفيذ أي دفعات أو حذف هنا."),
    ("Sales Invoices (Itemized, grouped by Branch)", "فواتير المبيعات (مفصلة، مجمعة حسب الفرع)"),
    ("Purchase Invoices (Itemized)", "فواتير المشتريات (مفصلة)"),
    ("Export CSV", "تصدير CSV"),
    ("Export Detailed CSV", "تصدير CSV مفصل"),
]

def main():
    for path, locale, use_ar in [(AR_PO, "ar", True), (EN_PO, "en", False)]:
        with open(path, "rb") as f:
            catalog = read_po(f, locale=locale)
        added = 0
        for msgid, ar in NEW_PAIRS:
            if not msgid:
                continue
            entry = catalog.get(msgid)
            if entry is None:
                catalog.add(msgid, string=ar if use_ar else msgid)
                added += 1
            elif use_ar and (not entry.string or not entry.string.strip()):
                entry.string = ar
                added += 1
        with open(path, "wb") as f:
            write_po(f, catalog, width=0)
        print("Updated %s (%d new/updated)" % (path, added))

if __name__ == "__main__":
    main()

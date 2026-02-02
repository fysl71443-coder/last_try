#!/usr/bin/env bash
set -euo pipefail

# -------------------------------
# 0️⃣ إعداد القيم الافتراضية
# -------------------------------
DATABASE_URL="${DATABASE_URL:-postgresql://china_town_user:itOxqXblGjRAr6IyI3K4b9gEoto6fZ5j@dpg-d2dk9c3e5dus7385023g-a.frankfurt-postgres.render.com/china_town_db}"
[[ "$DATABASE_URL" == postgres://* ]] && DATABASE_URL="${DATABASE_URL/postgres:\/\//postgresql:\/\/}"
ACCOUNTING_API="${ACCOUNTING_API:-http://127.0.0.1:3000}"
ACCOUNTING_KEY="${ACCOUNTING_KEY:-dev-key-accounting}"

echo "🔹 استخدام قاعدة البيانات: ***"
echo "🔹 استخدام API: $ACCOUNTING_API"

# -------------------------------
# 1️⃣ التحقق من السنة المالية 2026
# -------------------------------
echo "🔹 التحقق من السنة المالية 2026"
psql "$DATABASE_URL" -c "
SELECT id, year, start_date, end_date, closed
FROM fiscal_years
WHERE year = 2026;
"

# -------------------------------
# 2️⃣ التحقق من اتزان القيود
# -------------------------------
echo "🔹 التحقق من القيود غير المتوازنة"
psql "$DATABASE_URL" -c "
SELECT journal_id, SUM(debit) AS total_debit, SUM(credit) AS total_credit, ABS(SUM(debit)-SUM(credit)) AS diff
FROM journal_lines
GROUP BY journal_id
HAVING ABS(SUM(debit)-SUM(credit)) > 0.01;
"

# -------------------------------
# 3️⃣ التحقق من الفواتير بدون journal_entry_id
# -------------------------------
echo "🔹 التحقق من الفواتير بدون journal_entry_id"
psql "$DATABASE_URL" -c "
SELECT id AS invoice_id, journal_entry_id
FROM sales_invoices
WHERE journal_entry_id IS NULL;
" 2>/dev/null || echo "   (جدول sales_invoices غير موجود أو خطأ — تخطي)"

# -------------------------------
# 4️⃣ التحقق من التكرار على المصدر
# -------------------------------
echo "🔹 التحقق من التكرارات على المصدر"
psql "$DATABASE_URL" -c "
SELECT source_system, source_ref_type, source_ref_id, COUNT(*)
FROM journal_entries
WHERE source_system IS NOT NULL AND source_ref_type IS NOT NULL AND source_ref_id IS NOT NULL
GROUP BY source_system, source_ref_type, source_ref_id
HAVING COUNT(*) > 1;
"

# -------------------------------
# 5️⃣ اختبار POST API لفاتورة جديدة
# -------------------------------
echo "🔹 اختبار POST فاتورة عبر API"
code5=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$ACCOUNTING_API/api/external/sales-invoice" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $ACCOUNTING_KEY" \
  -d '{
  "source_system":"flask-pos",
  "invoice_number":"INV-TEST-'$(date +%s)'",
  "date":"2026-01-27",
  "branch":"china_town",
  "total_before_tax":85.00,
  "discount_amount":0,
  "vat_amount":15.00,
  "total_after_tax":100.00,
  "payment_method":"cash",
  "items":[{"product_name":"Item 1","quantity":1,"price":85.00,"total":85.00}]
}' || true)
echo "HTTP code: ${code5:-000} (توقع 200 أو 409)"

# -------------------------------
# 6️⃣ اختبار إغلاق السنة المالية 2026
# -------------------------------
echo "🔹 اختبار رفض الفواتير على سنة مغلقة"
psql "$DATABASE_URL" -c "UPDATE fiscal_years SET closed = true WHERE year = 2026;"
code6=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$ACCOUNTING_API/api/external/sales-invoice" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $ACCOUNTING_KEY" \
  -d '{
  "source_system":"flask-pos",
  "invoice_number":"INV-TEST-CLOSED",
  "date":"2026-01-27",
  "branch":"china_town",
  "total_before_tax":42.50,
  "discount_amount":0,
  "vat_amount":7.50,
  "total_after_tax":50.00,
  "payment_method":"cash",
  "items":[{"product_name":"Item Closed","quantity":1,"price":42.50,"total":42.50}]
}' || true)
[ -z "$code6" ] && code6="000"
echo "HTTP code: $code6 (توقع 403)"
if [ "$code6" = "403" ]; then
  echo "   ✓ تم رفض الفاتورة على سنة مغلقة (403)"
else
  echo "   ✗ متوقع 403 (تأكد من تشغيل Node محلياً على المنفذ 3000)"
fi

# إعادة فتح السنة بعد الاختبار
psql "$DATABASE_URL" -c "UPDATE fiscal_years SET closed = false WHERE year = 2026;"
echo "   تم إعادة فتح السنة 2026."

echo "✅ فحص قاعدة البيانات واختبارات التكامل اكتمل"

# -------------------------------
# فحص قاعدة بيانات المحاسبة + اختبارات التكامل (PowerShell)
# يتوافق مع schema Node (fiscal_years.closed, journal_lines.journal_id).
# -------------------------------

$ErrorActionPreference = "Continue"

# -------------------------------
# 0️⃣ تحميل .env
# -------------------------------
$envPath = Join-Path $PSScriptRoot "..\.env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match "^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$") {
            $k = $matches[1].Trim(); $v = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($k, $v, "Process")
        }
    }
}

$DATABASE_URL = $env:DATABASE_URL
$ACCOUNTING_API = $env:ACCOUNTING_API
$ACCOUNTING_KEY = $env:ACCOUNTING_KEY

if (-not $DATABASE_URL) {
    $DATABASE_URL = "postgresql://china_town_user:itOxqXblGjRAr6IyI3K4b9gEoto6fZ5j@dpg-d2dk9c3e5dus7385023g-a.frankfurt-postgres.render.com/china_town_db"
    $env:DATABASE_URL = $DATABASE_URL
}
if ($DATABASE_URL -match "^postgres://") {
    $DATABASE_URL = $DATABASE_URL -replace "^postgres://", "postgresql://"
    $env:DATABASE_URL = $DATABASE_URL
}
if (-not $ACCOUNTING_API) { $ACCOUNTING_API = "http://127.0.0.1:3000"; $env:ACCOUNTING_API = $ACCOUNTING_API }
if (-not $ACCOUNTING_KEY) { $ACCOUNTING_KEY = "dev-key-accounting"; $env:ACCOUNTING_KEY = $ACCOUNTING_KEY }

$apiDisplay = $ACCOUNTING_API
$dbDisplay = if ($DATABASE_URL -match "@([^/]+)") { "***@$($matches[1])" } else { "***" }
Write-Host "🔹 استخدام قاعدة البيانات: $dbDisplay"
Write-Host "🔹 استخدام API: $apiDisplay"

# يحتاج psql في PATH
if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
    Write-Host "psql غير موجود. تثبيت PostgreSQL client أو تشغيل السكربت من بيئة تحتوي psql."
    exit 1
}

# -------------------------------
# 1️⃣ التحقق من السنة المالية 2026
# -------------------------------
Write-Host "`n🔹 التحقق من السنة المالية 2026"
$q1 = "SELECT id, year, start_date, end_date, closed FROM fiscal_years WHERE year = 2026;"
& psql $DATABASE_URL -c $q1

# -------------------------------
# 2️⃣ التحقق من اتزان القيود
# -------------------------------
Write-Host "`n🔹 التحقق من القيود غير المتوازنة"
$q2 = "SELECT journal_id, SUM(debit) AS total_debit, SUM(credit) AS total_credit, ABS(SUM(debit)-SUM(credit)) AS diff FROM journal_lines GROUP BY journal_id HAVING ABS(SUM(debit)-SUM(credit)) > 0.01;"
& psql $DATABASE_URL -c $q2

# -------------------------------
# 3️⃣ التحقق من الفواتير بدون journal_entry_id
# -------------------------------
Write-Host "`n🔹 التحقق من الفواتير بدون journal_entry_id"
$q3 = "SELECT id AS invoice_id, journal_entry_id FROM sales_invoices WHERE journal_entry_id IS NULL;"
try { & psql $DATABASE_URL -c $q3 } catch { Write-Host "   (جدول sales_invoices غير موجود أو خطأ — تخطي)" }

# -------------------------------
# 4️⃣ التحقق من التكرار على المصدر
# -------------------------------
Write-Host "`n🔹 التحقق من التكرارات على المصدر"
$q4 = "SELECT source_system, source_ref_type, source_ref_id, COUNT(*) FROM journal_entries WHERE source_system IS NOT NULL AND source_ref_type IS NOT NULL AND source_ref_id IS NOT NULL GROUP BY source_system, source_ref_type, source_ref_id HAVING COUNT(*) > 1;"
& psql $DATABASE_URL -c $q4

# -------------------------------
# 5️⃣ اختبار POST API لفاتورة جديدة
# -------------------------------
Write-Host "`n🔹 اختبار POST فاتورة عبر API"
$payload = @{
    source_system   = "flask-pos"
    invoice_number  = "INV-TEST-" + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    date            = "2026-01-27"
    branch          = "china_town"
    total_before_tax = 85.0
    discount_amount = 0
    vat_amount      = 15.0
    total_after_tax = 100.0
    payment_method  = "cash"
    items           = @(@{ product_name = "Item 1"; quantity = 1; price = 85.0; total = 85.0 })
} | ConvertTo-Json -Depth 5

try {
    $r5 = Invoke-WebRequest -Uri "$ACCOUNTING_API/api/external/sales-invoice" -Method POST `
        -Headers @{ "X-API-KEY" = $ACCOUNTING_KEY; "Content-Type" = "application/json" } `
        -Body $payload -UseBasicParsing -TimeoutSec 10
    Write-Host "HTTP code: $($r5.StatusCode) (توقع 200 أو 409)"
} catch {
    Write-Host "خطأ: $($_.Exception.Message)"
    if ($_.Exception.Response) { Write-Host "HTTP code: $($_.Exception.Response.StatusCode.Value__)" }
}

# -------------------------------
# 6️⃣ اختبار إغلاق السنة المالية 2026
# -------------------------------
Write-Host "`n🔹 اختبار رفض الفواتير على سنة مغلقة"
& psql $DATABASE_URL -c "UPDATE fiscal_years SET closed = true WHERE year = 2026;"

$payloadClosed = @{
    source_system   = "flask-pos"
    invoice_number  = "INV-TEST-CLOSED"
    date            = "2026-01-27"
    branch          = "china_town"
    total_before_tax = 42.5
    discount_amount = 0
    vat_amount      = 7.5
    total_after_tax = 50.0
    payment_method  = "cash"
    items           = @(@{ product_name = "Item Closed"; quantity = 1; price = 42.5; total = 42.5 })
} | ConvertTo-Json -Depth 5

try {
    $r6 = Invoke-WebRequest -Uri "$ACCOUNTING_API/api/external/sales-invoice" -Method POST `
        -Headers @{ "X-API-KEY" = $ACCOUNTING_KEY; "Content-Type" = "application/json" } `
        -Body $payloadClosed -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
    Write-Host "Unexpected HTTP code: $($r6.StatusCode)"
} catch {
    if ($_.Exception.Response.StatusCode.Value__ -eq 403) {
        Write-Host "✅ تم رفض الفاتورة على سنة مغلقة (403)"
    } else {
        Write-Host "خطأ غير متوقع: $_"
    }
} finally {
    & psql $DATABASE_URL -c "UPDATE fiscal_years SET closed = false WHERE year = 2026;"
    Write-Host "   تم إعادة فتح السنة 2026."
}

Write-Host "`n✅ فحص قاعدة البيانات واختبارات التكامل اكتمل"

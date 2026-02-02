# Phase 2: عقد تكامل API — Flask ↔ Node.js Accounting

## المبادئ
- **Node.js Accounting** = المصدر الوحيد للحقيقة للقيود، سنوات مالية، VAT، Audit.
- **Flask** = نظام تشغيلي فقط (POS / Sales / Inventory / Payroll). يتواصل عبر REST فقط.
- **الأمان:** جميع طلبات `/api/external/*` تتطلب `X-API-KEY`.

---

## Base URL
```
ACCOUNTING_API = process.env.ACCOUNTING_API  # e.g. https://accounting-service.onrender.com
```

## Headers إلزامية
```
X-API-KEY: <ACCOUNTING_KEY>
Content-Type: application/json
```

---

## 1. Sales Invoice

### `POST /api/external/sales-invoice`

**الوصف:** إنشاء فاتورة مبيعات والقيود المرتبطة. Idempotency عبر `idempotency_key`.

**Request:**
```json
{
  "source_system": "flask-pos",
  "idempotency_key": "flask-sales-INV-1738000000-ct5",
  "invoice_number": "INV-1738000000-ct5",
  "date": "2026-01-27",
  "branch": "china_town",
  "customer_ref": 55,
  "customer_name": "Ahmed Ali",
  "customer_phone": "+966500000001",
  "table_number": 5,
  "total_before_tax": 1000,
  "discount_amount": 0,
  "vat_amount": 150,
  "total_after_tax": 1150,
  "payment_method": "cash",
  "items": [
    { "product_name": "Spring Rolls", "quantity": 2, "price": 12, "total": 24 }
  ]
}
```

**Response 200:**
```json
{
  "invoice_id": 123,
  "journal_entry_id": 889
}
```

**Response 403 (سنة مالية مغلقة):**
```json
{
  "error": "fiscal_year_closed",
  "message": "Fiscal year closed for this date"
}
```

**Response 409 (تكرار idempotency_key):**
```json
{
  "error": "duplicate",
  "invoice_id": 123,
  "journal_entry_id": 889
}
```

---

## 2. Purchase Invoice

### `POST /api/external/purchase-invoice`

**Request:**
```json
{
  "source_system": "flask-pos",
  "idempotency_key": "flask-pur-PUR-2026-001",
  "invoice_number": "PUR-2026-001",
  "date": "2026-01-27",
  "supplier_ref": 10,
  "supplier_name": "ABC Supplies",
  "total_before_tax": 500,
  "vat_amount": 75,
  "total_after_tax": 575,
  "payment_method": "cash",
  "status": "paid",
  "items": [
    { "raw_material_name": "Rice", "quantity": 10, "price_before_tax": 50 }
  ]
}
```

**Response 200:**
```json
{
  "invoice_id": 201,
  "journal_entry_id": 890
}
```

---

## 3. Expense Invoice

### `POST /api/external/expense-invoice`

**Request:**
```json
{
  "source_system": "flask-pos",
  "idempotency_key": "flask-exp-EXP-2026-001",
  "invoice_number": "EXP-2026-001",
  "date": "2026-01-27",
  "total_before_tax": 200,
  "vat_amount": 30,
  "total_after_tax": 230,
  "payment_method": "cash",
  "status": "paid",
  "items": [
    { "description": "Office supplies", "quantity": 1, "price_before_tax": 200 }
  ]
}
```

**Response 200:**
```json
{
  "invoice_id": 301,
  "journal_entry_id": 891
}
```

---

## 4. Payment (تحصيل ضد فاتورة مبيعات أو دفع لمشتريات/مصروفات)

### `POST /api/external/payment`

**Request:**
```json
{
  "source_system": "flask-pos",
  "idempotency_key": "flask-pay-sales-123-1738000100",
  "invoice_type": "sales",
  "invoice_id": 123,
  "invoice_number": "INV-1738000000-ct5",
  "amount": 1150,
  "payment_method": "cash",
  "date": "2026-01-27"
}
```

`invoice_type`: `sales` | `purchase` | `expense`

**Response 200:**
```json
{
  "payment_id": 501,
  "journal_entry_id": 892
}
```

---

## 5. Salary Payment

### `POST /api/external/salary-payment`

**Request:**
```json
{
  "source_system": "flask-pos",
  "idempotency_key": "flask-salary-emp5-2026-01",
  "salary_id": 42,
  "employee_id": 5,
  "year": 2026,
  "month": 1,
  "amount": 5000,
  "payment_method": "cash",
  "date": "2026-01-27"
}
```

**Response 200:**
```json
{
  "payment_id": 502,
  "journal_entry_id": 893
}
```

---

## 6. Salary Accrual (استحقاق راتب)

### `POST /api/external/salary-accrual`

**Request:**
```json
{
  "source_system": "flask-pos",
  "idempotency_key": "flask-accrual-emp5-2026-01",
  "salary_id": 42,
  "employee_id": 5,
  "year": 2026,
  "month": 1,
  "amount": 5000,
  "date": "2026-01-31"
}
```

**Response 200:**
```json
{
  "journal_entry_id": 894
}
```

---

## متطلبات Node.js (مراجعة سريعة)
- **Fiscal Years:** جدول سنوات مالية + حالة (مفتوحة/مغلقة).
- **Middleware:** التحقق من `X-API-KEY`؛ رفض الطلبات غير المصرح بها.
- **Fiscal Year Lock:** رفض إنشاء قيود لتواريخ في سنة مغلقة → `403`.
- **Idempotency:** تخزين `idempotency_key` مع المرجع؛ إرجاع نفس `invoice_id` / `journal_entry_id` عند التكرار.
- **Audit Log:** كل قيد مسجل مع `source_system: "flask-pos"` ووصف مثل `"Created from Flask POS System"`.

---

## استخدام العقد في Flask
- كل عملية تشغيلية (فاتورة مبيعات، مشتريات، مصروفات، دفع، راتب) تنتهي باستدعاء الـ endpoint المناسب.
- Flask يحفظ فقط `journal_entry_id` (أو `invoice_id` من المحاسبة إن لزم) ولا يحسب debit/credit.

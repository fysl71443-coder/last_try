# 🚀 Quick Deployment Guide - PostgreSQL Setup

## 📋 Essential PostgreSQL Commands

### Step 1: Execute These Commands on Your PostgreSQL Database

```sql
-- Essential columns for draft_orders table with proper constraints
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50) NOT NULL DEFAULT '0';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft';

-- Fix existing data with NULL values (run this BEFORE adding NOT NULL constraints)
UPDATE draft_orders SET table_number = '0' WHERE table_number IS NULL;
UPDATE draft_orders SET status = 'draft' WHERE status IS NULL;

-- If columns already exist but without proper constraints, update them:
ALTER TABLE draft_orders ALTER COLUMN table_number SET NOT NULL;
ALTER TABLE draft_orders ALTER COLUMN table_number SET DEFAULT '0';
ALTER TABLE draft_orders ALTER COLUMN status SET NOT NULL;
ALTER TABLE draft_orders ALTER COLUMN status SET DEFAULT 'draft';
```

### Step 2: Optional - Complete Schema Setup

If you want to ensure all columns exist, run the complete migration:

```sql
-- Complete draft_orders table setup
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS customer_name VARCHAR(100);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(20);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT 'CASH';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- Fix any remaining NULL values
UPDATE draft_orders SET branch_code = 'china_town' WHERE branch_code IS NULL;
UPDATE draft_orders SET payment_method = 'CASH' WHERE payment_method IS NULL;

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_draft_orders_branch_status ON draft_orders(branch_code, status);
CREATE INDEX IF NOT EXISTS idx_draft_orders_table ON draft_orders(branch_code, table_number);
```

## 🔧 Code Safety Features Added

### Safe table_number Handling

The code now includes safe handling for `table_number` fields:

```python
def safe_table_number(table_number) -> int:
    """Safely convert table_number to int, default to 0 if None/invalid"""
    try:
        return int(table_number or 0)
    except (ValueError, TypeError):
        return 0
```

### Protected Routes

All sales routes now use safe table number handling:

- ✅ `/sales/<branch>/tables` - Safe draft counting
- ✅ `/api/draft/checkout` - Safe table number conversion
- ✅ Draft order processing - Protected against NULL values

## 🎯 Deployment Steps for Render

### 1. Database Setup
```bash
# Connect to your PostgreSQL database and run:
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft';
UPDATE draft_orders SET table_number = '0' WHERE table_number IS NULL;
```

### 2. Deploy Application
- Push code to GitHub
- Deploy on Render
- Verify all endpoints work

### 3. Test Critical Routes
After deployment, test these URLs:
- `/sales` - Branch selection
- `/sales/china_town/tables` - China Town tables
- `/sales/place_india/tables` - Place India tables

## ✅ Success Indicators

Your deployment is successful when:

1. **No "column does not exist" errors**
2. **Sales tables load without 500 errors**
3. **Draft orders display correctly**
4. **Table numbers show properly (not NULL)**

## 🔍 Troubleshooting

### If you still get column errors:
```sql
-- Check if columns exist
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'draft_orders' 
ORDER BY column_name;
```

### If table_number shows as NULL:
```sql
-- Fix NULL values
UPDATE draft_orders SET table_number = '0' WHERE table_number IS NULL;
```

### If status shows as NULL:
```sql
-- Fix NULL status values
UPDATE draft_orders SET status = 'draft' WHERE status IS NULL;
```

### Check column types and constraints:
```sql
-- Verify column structure
\d draft_orders

-- Or use this query to check column details:
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'draft_orders'
AND column_name IN ('table_number', 'status', 'branch_code', 'payment_method')
ORDER BY column_name;
```

### If columns exist but with wrong type/constraints:
```sql
-- Update existing columns to match model requirements
ALTER TABLE draft_orders ALTER COLUMN table_number TYPE VARCHAR(50);
ALTER TABLE draft_orders ALTER COLUMN table_number SET NOT NULL;
ALTER TABLE draft_orders ALTER COLUMN table_number SET DEFAULT '0';

ALTER TABLE draft_orders ALTER COLUMN status TYPE VARCHAR(20);
ALTER TABLE draft_orders ALTER COLUMN status SET NOT NULL;
ALTER TABLE draft_orders ALTER COLUMN status SET DEFAULT 'draft';
```

---

## 🛠 وضع المطور (Dev Server)

**نقطة تشغيل واحدة فقط** — استخدم أحد الأمرين:

```bash
python tools/run_local.py
# أو
python run_dev.py
```

- **العنوان:** http://127.0.0.1:5000  
- **قاعدة البيانات:** `instance/local.db` (SQLite محلي)  
- **التصحيح:** مُفعّل (إعادة تحميل تلقائية عند تعديل ملفات .py)

أوقف أي خادم آخر على المنفذ 5000 أو 5001 قبل التشغيل لتجنب نسخة قديمة.

---

**Status: ✅ READY FOR PRODUCTION**

All safety measures implemented. Database schema issues resolved.

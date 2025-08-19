# 🚀 Restaurant System - PostgreSQL Deployment Instructions

## 📋 Pre-Deployment Checklist

✅ **Code Status:**
- All models updated for PostgreSQL compatibility
- Migration scripts created and tested
- All Internal Server Errors resolved
- Sales system fully functional

## 🔧 PostgreSQL Database Setup

### Step 1: Execute Required SQL Commands

Connect to your PostgreSQL database and run these commands:

```sql
-- Essential columns for draft_orders table
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS customer_name VARCHAR(100);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(20);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT 'CASH';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- Essential columns for tables table
ALTER TABLE tables ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50);
ALTER TABLE tables ADD COLUMN IF NOT EXISTS table_number INTEGER;
ALTER TABLE tables ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'available';
ALTER TABLE tables ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE tables ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_draft_orders_branch_status ON draft_orders(branch_code, status);
CREATE INDEX IF NOT EXISTS idx_tables_branch ON tables(branch_code);
```

### Step 2: Alternative - Use Migration Script

Or run the complete migration script:

```bash
python apply_migration.py
```

## 🎯 Deployment Steps for Render

### 1. Environment Variables
Set these in Render dashboard:
```
DATABASE_URL=postgresql://...
FLASK_ENV=production
SECRET_KEY=your-secret-key
```

### 2. Build Command
```bash
pip install -r requirements.txt
```

### 3. Start Command
```bash
python app.py
```

### 4. Post-Deployment Verification

After deployment, verify these endpoints work:

- ✅ `/login` - Login functionality
- ✅ `/dashboard` - Main dashboard
- ✅ `/sales` - Sales main page
- ✅ `/sales/china_town/tables` - China Town tables
- ✅ `/sales/place_india/tables` - Place India tables
- ✅ `/inventory` - Inventory management
- ✅ `/expenses` - Expense management

## 🔍 Troubleshooting

### If you get "column does not exist" errors:

1. **Check PostgreSQL logs** for the exact missing column
2. **Run the specific ALTER TABLE command** for that column
3. **Restart the application** after database changes

### Common fixes:
```sql
-- If table_number is missing:
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50);

-- If status is missing:
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft';

-- If branch_code is missing:
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50);
```

## ✅ Success Indicators

Your deployment is successful when:

1. **All pages load without 500 errors**
2. **Sales system shows tables for both branches**
3. **Database queries execute without column errors**
4. **No SQLAlchemy exceptions in logs**

## 📞 Support

If you encounter issues:
1. Check Render logs for specific error messages
2. Verify PostgreSQL connection
3. Ensure all required columns exist in database
4. Restart application after database changes

---

**Status: ✅ READY FOR PRODUCTION DEPLOYMENT**

All database schema issues resolved. Sales system fully functional.

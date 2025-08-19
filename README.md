# 🏪 Restaurant Management System

A comprehensive bilingual (Arabic/English) restaurant management system built with Flask and PostgreSQL.

## ✨ Features

- 🔐 **User Authentication** - Secure login system
- 🏪 **Multi-Branch Support** - China Town & Place India branches
- 🍽️ **Sales Management** - Table-based POS system with draft orders
- 📦 **Inventory Management** - Raw materials and meals tracking
- 💰 **Expense Management** - Complete expense tracking
- 📊 **Reports & Analytics** - Comprehensive reporting system
- 🧾 **Payment Tracking** - Multiple payment methods support

## 🚀 Quick Deployment on Render

### Step 1: Deploy Application
1. Fork this repository
2. Create new Web Service on Render
3. Connect your GitHub repository
4. Add PostgreSQL database add-on

### Step 2: Setup Database
Connect to your PostgreSQL database and run:

```sql
-- Essential setup commands
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50) NOT NULL DEFAULT '0';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft';
UPDATE draft_orders SET table_number = '0' WHERE table_number IS NULL;
UPDATE draft_orders SET status = 'draft' WHERE status IS NULL;
```

Or execute the complete setup script:
```bash
psql $DATABASE_URL < render_setup.sql
```

### Step 3: Environment Variables
Set these in Render dashboard:
```
DATABASE_URL=postgresql://...
SECRET_KEY=your-secret-key
FLASK_ENV=production
```

### Step 4: Verify Deployment
Test these URLs after deployment:
- `/sales` - Branch selection
- `/sales/china_town/tables` - China Town tables
- `/sales/place_india/tables` - Place India tables

## 🛠️ Local Development

1. Copy `.env.example` to `.env` and update values
2. Create virtual environment: `python -m venv .venv && source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Setup database: `python apply_migration.py`
5. Run application: `python app.py`

## 📋 Default Login
- **Username**: admin
- **Password**: admin123

## 📚 Documentation

- `RENDER_DEPLOYMENT_STEPS.md` - Detailed deployment guide
- `QUICK_DEPLOYMENT_GUIDE.md` - Quick reference
- `verify_database.py` - Database verification tool

## 🎯 System Status

✅ All screens functional
✅ PostgreSQL compatible
✅ Production ready
✅ Multi-language support
✅ Comprehensive error handling

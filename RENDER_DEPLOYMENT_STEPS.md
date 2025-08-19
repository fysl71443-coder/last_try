# 🚀 Render Deployment Steps - Final Instructions

## 📋 Step-by-Step Deployment Guide

### Step 1: Connect to PostgreSQL Database

Connect to your Render PostgreSQL database using the provided connection string:

```bash
psql $DATABASE_URL
```

### Step 2: Add Required Columns with Default Values

Execute these commands in your PostgreSQL console:

```sql
-- Add table_number column with NOT NULL constraint and default value
ALTER TABLE draft_orders
ADD COLUMN IF NOT EXISTS table_number VARCHAR(50) NOT NULL DEFAULT '0';

-- Add status column with NOT NULL constraint and default value
ALTER TABLE draft_orders
ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft';
```

### Step 3: Update Any Existing Data (if needed)

Run these commands to ensure no NULL values exist:

```sql
-- Update any existing NULL values (safety measure)
UPDATE draft_orders SET table_number = '0' WHERE table_number IS NULL;
UPDATE draft_orders SET status = 'draft' WHERE status IS NULL;
```

### Step 4: Verify the Changes

Check that the columns were added correctly:

```sql
-- Verify the table structure
\d draft_orders

-- You should see:
-- table_number | character varying(50) | not null | '0'::character varying
-- status       | character varying(20) | not null | 'draft'::character varying
```

### Step 5: Exit PostgreSQL and Restart Application

```sql
-- Exit PostgreSQL
\q
```

Then restart your application on Render dashboard.

## ✅ Success Verification

After deployment, test these URLs to ensure everything works:

1. **Main Sales Page**: `https://your-app.onrender.com/sales`
   - Should show branch selection (China Town, Place India)

2. **China Town Tables**: `https://your-app.onrender.com/sales/china_town/tables`
   - Should show 50 tables without errors

3. **Place India Tables**: `https://your-app.onrender.com/sales/place_india/tables`
   - Should show 50 tables without errors

## 🔍 Troubleshooting

### If you get "column does not exist" errors:

1. **Check if columns exist**:
   ```sql
   SELECT column_name FROM information_schema.columns 
   WHERE table_name = 'draft_orders' 
   ORDER BY column_name;
   ```

2. **If columns are missing, run the ALTER TABLE commands again**:
   ```sql
   ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50) NOT NULL DEFAULT '0';
   ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft';
   ```

### If you get constraint violation errors:

1. **Fix NULL values first**:
   ```sql
   UPDATE draft_orders SET table_number = '0' WHERE table_number IS NULL;
   UPDATE draft_orders SET status = 'draft' WHERE status IS NULL;
   ```

2. **Then add constraints**:
   ```sql
   ALTER TABLE draft_orders ALTER COLUMN table_number SET NOT NULL;
   ALTER TABLE draft_orders ALTER COLUMN status SET NOT NULL;
   ```

## 🎯 Expected Results

After successful deployment:

- ✅ No "column does not exist" errors
- ✅ Sales page loads and shows both branches
- ✅ Table pages load for both China Town and Place India
- ✅ No 500 Internal Server Errors
- ✅ Draft orders can be created and managed

## 📞 Quick Commands Summary

```sql
-- Complete setup in one go:
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50) NOT NULL DEFAULT '0';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft';
UPDATE draft_orders SET table_number = '0' WHERE table_number IS NULL;
UPDATE draft_orders SET status = 'draft' WHERE status IS NULL;
\d draft_orders
\q
```

---

**Status: ✅ READY FOR RENDER DEPLOYMENT**

Follow these exact steps and your restaurant system will be fully operational on Render with PostgreSQL!

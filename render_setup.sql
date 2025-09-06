-- Render PostgreSQL Setup Script
-- Execute this script on your Render PostgreSQL database

-- Step 1: Add required columns with NOT NULL constraints and default values
ALTER TABLE draft_orders
ADD COLUMN IF NOT EXISTS table_number VARCHAR(50) NOT NULL DEFAULT '0';

ALTER TABLE draft_orders
ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft';

-- Step 2: Update any existing NULL values (safety measure)
UPDATE draft_orders SET table_number = '0' WHERE table_number IS NULL;
UPDATE draft_orders SET status = 'draft' WHERE status IS NULL;

-- Step 3: Add other useful columns if they don't exist
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50) NOT NULL DEFAULT 'china_town';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS customer_name VARCHAR(100);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(20);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) NOT NULL DEFAULT 'CASH';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- Step 4: Fix any remaining NULL values
UPDATE draft_orders SET branch_code = 'china_town' WHERE branch_code IS NULL;
UPDATE draft_orders SET payment_method = 'CASH' WHERE payment_method IS NULL;

-- Step 5: Create performance indexes
CREATE INDEX IF NOT EXISTS idx_draft_orders_branch_status ON draft_orders(branch_code, status);
CREATE INDEX IF NOT EXISTS idx_draft_orders_table ON draft_orders(branch_code, table_number);

-- Step 6: Verify the setup
SELECT 'Setup completed successfully!' as status;
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'draft_orders' 
ORDER BY column_name;

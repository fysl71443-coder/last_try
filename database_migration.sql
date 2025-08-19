-- PostgreSQL Migration Script for Restaurant System
-- This script ensures all required columns exist in the database

-- 1. Ensure draft_orders table has required columns
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS customer_name VARCHAR(100);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(20);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT 'CASH';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- 1.1. Fix existing data with NULL values
UPDATE draft_orders SET table_number = '0' WHERE table_number IS NULL;
UPDATE draft_orders SET status = 'draft' WHERE status IS NULL;
UPDATE draft_orders SET branch_code = 'china_town' WHERE branch_code IS NULL;
UPDATE draft_orders SET payment_method = 'CASH' WHERE payment_method IS NULL;

-- 2. Ensure tables table has required columns
ALTER TABLE tables ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50);
ALTER TABLE tables ADD COLUMN IF NOT EXISTS table_number INTEGER;
ALTER TABLE tables ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'available';
ALTER TABLE tables ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE tables ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 3. Ensure draft_order_items table has required columns
ALTER TABLE draft_order_items ADD COLUMN IF NOT EXISTS draft_order_id INTEGER;
ALTER TABLE draft_order_items ADD COLUMN IF NOT EXISTS meal_id INTEGER;
ALTER TABLE draft_order_items ADD COLUMN IF NOT EXISTS product_name VARCHAR(200);
ALTER TABLE draft_order_items ADD COLUMN IF NOT EXISTS quantity DECIMAL(10,2) DEFAULT 1;
ALTER TABLE draft_order_items ADD COLUMN IF NOT EXISTS unit_price DECIMAL(10,2) DEFAULT 0;
ALTER TABLE draft_order_items ADD COLUMN IF NOT EXISTS total_price DECIMAL(10,2) DEFAULT 0;

-- 4. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_draft_orders_branch_status ON draft_orders(branch_code, status);
CREATE INDEX IF NOT EXISTS idx_tables_branch ON tables(branch_code);
CREATE INDEX IF NOT EXISTS idx_draft_order_items_order_id ON draft_order_items(draft_order_id);

-- 5. Add foreign key constraints if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_draft_orders_user_id'
    ) THEN
        ALTER TABLE draft_orders ADD CONSTRAINT fk_draft_orders_user_id 
        FOREIGN KEY (user_id) REFERENCES users(id);
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_draft_order_items_draft_order_id'
    ) THEN
        ALTER TABLE draft_order_items ADD CONSTRAINT fk_draft_order_items_draft_order_id 
        FOREIGN KEY (draft_order_id) REFERENCES draft_orders(id) ON DELETE CASCADE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_draft_order_items_meal_id'
    ) THEN
        ALTER TABLE draft_order_items ADD CONSTRAINT fk_draft_order_items_meal_id 
        FOREIGN KEY (meal_id) REFERENCES meals(id);
    END IF;
END $$;

-- 6. Update any existing data to ensure consistency
UPDATE draft_orders SET status = 'draft' WHERE status IS NULL;
UPDATE tables SET status = 'available' WHERE status IS NULL;
UPDATE draft_orders SET payment_method = 'CASH' WHERE payment_method IS NULL;

COMMIT;

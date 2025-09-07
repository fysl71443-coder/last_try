ALTER TABLE draft_orders
ADD COLUMN IF NOT EXISTS table_number VARCHAR(50) NOT NULL DEFAULT '0';

ALTER TABLE draft_orders
ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft';

UPDATE draft_orders SET table_number = '0' WHERE table_number IS NULL;
UPDATE draft_orders SET status = 'draft' WHERE status IS NULL;

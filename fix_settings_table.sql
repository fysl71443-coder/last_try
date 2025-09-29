-- Fix Settings Table - Add All Missing Columns
-- Run this SQL script to add all missing columns to the settings table

-- Add missing columns with proper defaults
ALTER TABLE settings ADD COLUMN IF NOT EXISTS default_theme VARCHAR(50) DEFAULT 'light';
ALTER TABLE settings ADD COLUMN IF NOT EXISTS china_town_void_password VARCHAR(50) DEFAULT '1991';
ALTER TABLE settings ADD COLUMN IF NOT EXISTS place_india_void_password VARCHAR(50) DEFAULT '1991';
ALTER TABLE settings ADD COLUMN IF NOT EXISTS china_town_vat_rate FLOAT DEFAULT 15.0;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS place_india_vat_rate FLOAT DEFAULT 15.0;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS china_town_discount_rate FLOAT DEFAULT 0.0;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS place_india_discount_rate FLOAT DEFAULT 0.0;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS receipt_paper_width VARCHAR(10) DEFAULT '80';
ALTER TABLE settings ADD COLUMN IF NOT EXISTS receipt_margin_top_mm INTEGER DEFAULT 5;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS receipt_margin_bottom_mm INTEGER DEFAULT 5;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS receipt_margin_left_mm INTEGER DEFAULT 5;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS receipt_margin_right_mm INTEGER DEFAULT 5;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS receipt_font_size INTEGER DEFAULT 12;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS receipt_show_logo BOOLEAN DEFAULT TRUE;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS receipt_show_tax_number BOOLEAN DEFAULT TRUE;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS receipt_footer_text TEXT DEFAULT 'شكراً لزيارتكم - Thank you for visiting';
ALTER TABLE settings ADD COLUMN IF NOT EXISTS logo_url VARCHAR(255);
ALTER TABLE settings ADD COLUMN IF NOT EXISTS receipt_logo_height INTEGER DEFAULT 40;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS receipt_extra_bottom_mm INTEGER DEFAULT 15;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS china_town_phone1 VARCHAR(50);
ALTER TABLE settings ADD COLUMN IF NOT EXISTS china_town_phone2 VARCHAR(50);
ALTER TABLE settings ADD COLUMN IF NOT EXISTS place_india_phone1 VARCHAR(50);
ALTER TABLE settings ADD COLUMN IF NOT EXISTS place_india_phone2 VARCHAR(50);

-- Update existing records with default values if they are NULL
UPDATE settings SET 
    default_theme = COALESCE(default_theme, 'light'),
    china_town_void_password = COALESCE(china_town_void_password, '1991'),
    place_india_void_password = COALESCE(place_india_void_password, '1991'),
    china_town_vat_rate = COALESCE(china_town_vat_rate, 15.0),
    place_india_vat_rate = COALESCE(place_india_vat_rate, 15.0),
    china_town_discount_rate = COALESCE(china_town_discount_rate, 0.0),
    place_india_discount_rate = COALESCE(place_india_discount_rate, 0.0),
    receipt_paper_width = COALESCE(receipt_paper_width, '80'),
    receipt_margin_top_mm = COALESCE(receipt_margin_top_mm, 5),
    receipt_margin_bottom_mm = COALESCE(receipt_margin_bottom_mm, 5),
    receipt_margin_left_mm = COALESCE(receipt_margin_left_mm, 5),
    receipt_margin_right_mm = COALESCE(receipt_margin_right_mm, 5),
    receipt_font_size = COALESCE(receipt_font_size, 12),
    receipt_show_logo = COALESCE(receipt_show_logo, TRUE),
    receipt_show_tax_number = COALESCE(receipt_show_tax_number, TRUE),
    receipt_footer_text = COALESCE(receipt_footer_text, 'شكراً لزيارتكم - Thank you for visiting'),
    receipt_logo_height = COALESCE(receipt_logo_height, 40),
    receipt_extra_bottom_mm = COALESCE(receipt_extra_bottom_mm, 15)
WHERE id IS NOT NULL;

-- Create default settings record if none exists
INSERT INTO settings (
    company_name, tax_number, address, phone, email, vat_rate, currency,
    china_town_label, place_india_label, default_theme,
    china_town_void_password, place_india_void_password,
    china_town_vat_rate, place_india_vat_rate,
    china_town_discount_rate, place_india_discount_rate,
    china_town_phone1, china_town_phone2, place_india_phone1, place_india_phone2,
    receipt_paper_width, receipt_font_size, receipt_show_logo, receipt_show_tax_number,
    receipt_footer_text, receipt_logo_height, receipt_extra_bottom_mm
)
SELECT 
    'مطعم الصين وقصر الهند', '123456789', 'الرياض، المملكة العربية السعودية',
    '0112345678', 'info@restaurant.com', 15.0, 'SAR',
    'China Town', 'Palace India', 'light',
    '1991', '1991',
    15.0, 15.0,
    0.0, 0.0,
    NULL, NULL, NULL, NULL,
    '80', 12, TRUE, TRUE,
    'شكراً لزيارتكم - Thank you for visiting', 40, 15
WHERE NOT EXISTS (SELECT 1 FROM settings LIMIT 1);

-- Verify the fix
SELECT 'Settings table fixed successfully!' as status,
       COUNT(*) as total_settings_records
FROM settings;

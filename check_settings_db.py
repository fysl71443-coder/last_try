#!/usr/bin/env python3
"""
Check Settings database and fix missing fields
"""

import os
import sys
sys.path.append('.')

from app import create_app
from models import Settings, db

def check_settings():
    app = create_app()
    
    with app.app_context():
        print("🔍 Checking Settings database...")
        
        # Check if Settings table exists
        try:
            settings = Settings.query.first()
            if settings:
                print("✅ Settings record found")
                print(f"   ID: {settings.id}")
                print(f"   Company: {settings.company_name}")
                print(f"   Logo URL: {settings.logo_url}")
                print(f"   China Town Logo: {settings.china_town_logo_url}")
                print(f"   Place India Logo: {settings.place_india_logo_url}")
            else:
                print("❌ No Settings record found - creating one...")
                settings = Settings()
                db.session.add(settings)
                db.session.commit()
                print("✅ Created new Settings record")
        except Exception as e:
            print(f"❌ Error accessing Settings: {e}")
            return False
        
        # Check for missing columns
        print("\n🔍 Checking for missing columns...")
        missing_columns = []
        
        # List of expected columns
        expected_columns = [
            'china_town_logo_url', 'place_india_logo_url',
            'china_town_void_password', 'china_town_vat_rate', 'china_town_discount_rate',
            'place_india_void_password', 'place_india_vat_rate', 'place_india_discount_rate',
            'receipt_logo_height', 'receipt_extra_bottom_mm'
        ]
        
        for col in expected_columns:
            try:
                getattr(settings, col)
                print(f"   ✅ {col}")
            except AttributeError:
                print(f"   ❌ {col} - MISSING")
                missing_columns.append(col)
        
        if missing_columns:
            print(f"\n🔧 Adding missing columns: {missing_columns}")
            try:
                # Add missing columns
                for col in missing_columns:
                    if col in ['china_town_logo_url', 'place_india_logo_url']:
                        db.engine.execute(f"ALTER TABLE settings ADD COLUMN {col} VARCHAR(300)")
                    elif col in ['china_town_void_password', 'place_india_void_password']:
                        db.engine.execute(f"ALTER TABLE settings ADD COLUMN {col} VARCHAR(50) DEFAULT '1991'")
                    elif col in ['china_town_vat_rate', 'china_town_discount_rate', 'place_india_vat_rate', 'place_india_discount_rate']:
                        db.engine.execute(f"ALTER TABLE settings ADD COLUMN {col} NUMERIC(5,2) DEFAULT 15.00")
                    elif col == 'receipt_logo_height':
                        db.engine.execute(f"ALTER TABLE settings ADD COLUMN {col} INTEGER DEFAULT 72")
                    elif col == 'receipt_extra_bottom_mm':
                        db.engine.execute(f"ALTER TABLE settings ADD COLUMN {col} INTEGER DEFAULT 15")
                
                print("✅ Missing columns added")
                
                # Refresh the settings object
                db.session.refresh(settings)
                print("✅ Settings refreshed")
                
            except Exception as e:
                print(f"❌ Error adding columns: {e}")
                return False
        
        print("\n🎉 Settings database check completed!")
        return True

if __name__ == "__main__":
    check_settings()

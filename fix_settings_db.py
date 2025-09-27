#!/usr/bin/env python3
"""
Fix Settings database by adding missing columns
"""

import os
import sys
sys.path.append('.')

from app import create_app
from models import Settings, db

def fix_settings_db():
    app = create_app()
    
    with app.app_context():
        print("🔧 Fixing Settings database...")
        
        try:
            # Add missing columns
            missing_columns = [
                ("china_town_logo_url", "VARCHAR(300)"),
                ("place_india_logo_url", "VARCHAR(300)"),
            ]
            
            for col_name, col_type in missing_columns:
                try:
                    # Check if column exists
                    result = db.engine.execute(f"PRAGMA table_info(settings)")
                    columns = [row[1] for row in result]
                    
                    if col_name not in columns:
                        print(f"   Adding column: {col_name}")
                        db.engine.execute(f"ALTER TABLE settings ADD COLUMN {col_name} {col_type}")
                    else:
                        print(f"   Column {col_name} already exists")
                        
                except Exception as e:
                    print(f"   Error adding {col_name}: {e}")
            
            print("✅ Database fixed!")
            
            # Test Settings access
            settings = Settings.query.first()
            if not settings:
                print("   Creating default Settings record...")
                settings = Settings()
                db.session.add(settings)
                db.session.commit()
            
            print(f"✅ Settings record: ID={settings.id}")
            print(f"   Company: {settings.company_name}")
            print(f"   China Town Logo: {settings.china_town_logo_url}")
            print(f"   Place India Logo: {settings.place_india_logo_url}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error fixing database: {e}")
            return False

if __name__ == "__main__":
    fix_settings_db()

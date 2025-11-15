#!/usr/bin/env python3
"""Check database status and add branch settings if needed"""

import os
import sys
from app import create_app
from extensions import db
from models import Settings

def check_and_update_db():
    """Check database and add branch settings"""
    app = create_app()
    with app.app_context():
        try:
            # Create all tables if they don't exist
            db.create_all()
            print("Database tables created/verified")

            # Ensure 'settings' table has all expected columns
            try:
                from sqlalchemy import text
                engine = db.engine
                dialect = engine.dialect.name
                existing_cols = set()
                if dialect == 'sqlite':
                    res = engine.execute(text("PRAGMA table_info(settings)"))
                    existing_cols = {str(row[1]) for row in res}
                else:
                    res = engine.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='settings'"))
                    existing_cols = {str(row[0]) for row in res}

                def add_col(name: str, ddl: str):
                    if name not in existing_cols:
                        try:
                            with engine.begin() as conn:
                                conn.execute(text(f"ALTER TABLE settings ADD COLUMN {ddl}"))
                            print(f"Added column: {name}")
                            existing_cols.add(name)
                        except Exception as e:
                            print(f"⚠️ Failed to add column {name}: {e}")

                # Late-added tuning columns
                add_col('receipt_high_contrast', "receipt_high_contrast BOOLEAN DEFAULT 1")
                add_col('receipt_bold_totals', "receipt_bold_totals BOOLEAN DEFAULT 1")
                add_col('receipt_border_style', "receipt_border_style VARCHAR(10) DEFAULT 'solid'")
                add_col('receipt_font_bump', "receipt_font_bump INTEGER DEFAULT 1")
                # Essential branding fields
                add_col('logo_url', "logo_url VARCHAR(300) DEFAULT '/static/chinese-logo.svg'")
                add_col('china_town_logo_url', "china_town_logo_url VARCHAR(300)")
                add_col('place_india_logo_url', "place_india_logo_url VARCHAR(300)")
                add_col('currency_image', "currency_image VARCHAR(300)")
                add_col('china_town_phone1', "china_town_phone1 VARCHAR(50)")
                add_col('china_town_phone2', "china_town_phone2 VARCHAR(50)")
                add_col('place_india_phone1', "place_india_phone1 VARCHAR(50)")
                add_col('place_india_phone2', "place_india_phone2 VARCHAR(50)")
            except Exception as e:
                print("⚠️ Column ensure step failed:", e)
            
            # Check if Settings table exists and has data
            settings = Settings.query.first()
            if not settings:
                settings = Settings()
                db.session.add(settings)
                db.session.commit()
                print("Created initial settings record")
            else:
                print("Settings record exists")
            
            # Check if new columns exist by trying to access them
            try:
                china_pwd = settings.china_town_void_password
                india_pwd = settings.place_india_void_password
                print("Branch-specific settings columns already exist")
                print(f"China Town void password: {china_pwd}")
                print(f"Palace India void password: {india_pwd}")
            except AttributeError as e:
                print(f"Branch settings columns missing: {e}")
                print("Please run the migration manually")

            # Ensure essential branding fields are set
            try:
                changed = False
                if not (settings.company_name and str(settings.company_name).strip()):
                    settings.company_name = 'Restaurant'
                    changed = True
                # Default generic logo
                if not (settings.logo_url and str(settings.logo_url).strip()):
                    settings.logo_url = '/static/logo.svg'
                    changed = True
                # Branch-specific logos (fallbacks)
                if not getattr(settings, 'china_town_logo_url', None):
                    settings.china_town_logo_url = '/static/chinese-logo.svg'
                    changed = True
                if not getattr(settings, 'place_india_logo_url', None):
                    settings.place_india_logo_url = '/static/logo.svg'
                    changed = True
                # Make sure logo display is enabled
                if getattr(settings, 'receipt_show_logo', None) in (None, False, 0):
                    settings.receipt_show_logo = True
                    changed = True
                # Optional: keep tax number if present; otherwise blank is fine
                if changed:
                    db.session.commit()
                    print("Updated branding defaults in settings (logo/company name)")
                print("Settings snapshot:")
                print("  company_name:", settings.company_name)
                print("  tax_number:", settings.tax_number)
                print("  logo_url:", settings.logo_url)
                print("  china_town_logo_url:", settings.china_town_logo_url)
                print("  place_india_logo_url:", settings.place_india_logo_url)
                print("  receipt_show_logo:", settings.receipt_show_logo)
            except Exception as e:
                db.session.rollback()
                print("❌ Failed updating branding defaults:", e)

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    check_and_update_db()

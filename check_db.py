#!/usr/bin/env python3
"""Check database status and add branch settings if needed"""

import os
import sys
from app import app, db
from models import Settings

def check_and_update_db():
    """Check database and add branch settings"""
    with app.app_context():
        try:
            # Create all tables if they don't exist
            db.create_all()
            print("Database tables created/verified")
            
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
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    check_and_update_db()

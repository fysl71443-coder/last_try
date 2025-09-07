"""Add branch-specific settings to Settings model

This migration adds branch-specific settings for China Town and Palace India,
including separate void passwords and tax/discount rates for each branch.
"""

from app import app, db
from models import Settings
from sqlalchemy import text

def add_branch_settings():
    """Add branch-specific settings columns to Settings table"""
    with app.app_context():
        try:
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('settings')]
            
            # Add China Town settings columns
            if 'china_town_void_password' not in columns:
                db.engine.execute(text('ALTER TABLE settings ADD COLUMN china_town_void_password VARCHAR(50) DEFAULT "1991"'))
                print("Added china_town_void_password column")
            
            if 'china_town_vat_rate' not in columns:
                db.engine.execute(text('ALTER TABLE settings ADD COLUMN china_town_vat_rate DECIMAL(5,2) DEFAULT 15.00'))
                print("Added china_town_vat_rate column")
                
            if 'china_town_discount_rate' not in columns:
                db.engine.execute(text('ALTER TABLE settings ADD COLUMN china_town_discount_rate DECIMAL(5,2) DEFAULT 0.00'))
                print("Added china_town_discount_rate column")
            
            # Add Palace India settings columns
            if 'place_india_void_password' not in columns:
                db.engine.execute(text('ALTER TABLE settings ADD COLUMN place_india_void_password VARCHAR(50) DEFAULT "1991"'))
                print("Added place_india_void_password column")
                
            if 'place_india_vat_rate' not in columns:
                db.engine.execute(text('ALTER TABLE settings ADD COLUMN place_india_vat_rate DECIMAL(5,2) DEFAULT 15.00'))
                print("Added place_india_vat_rate column")
                
            if 'place_india_discount_rate' not in columns:
                db.engine.execute(text('ALTER TABLE settings ADD COLUMN place_india_discount_rate DECIMAL(5,2) DEFAULT 0.00'))
                print("Added place_india_discount_rate column")
            
            # Initialize settings if they don't exist
            settings = Settings.query.first()
            if not settings:
                settings = Settings()
                db.session.add(settings)
                db.session.commit()
                print("Created initial settings record")
            
            print("Branch settings migration completed successfully")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    add_branch_settings()

#!/usr/bin/env python3
"""
Migration script to add table management features:
1. Create tables table for tracking table status
2. Add table_no column to sales_invoices
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Table, SalesInvoice

def run_migration():
    with app.app_context():
        try:
            # Create tables table
            print("Creating tables table...")
            db.create_all()
            
            # Add table_no column to sales_invoices if it doesn't exist
            print("Checking sales_invoices table...")
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('sales_invoices')]
            
            if 'table_no' not in columns:
                print("Adding table_no column to sales_invoices...")
                db.engine.execute('ALTER TABLE sales_invoices ADD COLUMN table_no INTEGER')
            else:
                print("table_no column already exists in sales_invoices")
            
            # Initialize some default tables for both branches
            print("Initializing default tables...")
            for branch in ['place_india', 'china_town']:
                for table_num in range(1, 11):  # Tables 1-10 for each branch
                    existing = Table.query.filter_by(branch_code=branch, table_number=table_num).first()
                    if not existing:
                        table = Table(
                            branch_code=branch,
                            table_number=table_num,
                            status='available'
                        )
                        db.session.add(table)
            
            db.session.commit()
            print("Migration completed successfully!")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    run_migration()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""إضافة عمود customer_type إلى جدول العملاء إن لم يكن موجوداً."""
import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
os.chdir(base_dir)

os.environ.setdefault('DATABASE_URL', 'sqlite:///instance/accounting_app.db')

from app import create_app
from extensions import db

app = create_app()
with app.app_context():
    try:
        db.session.execute(db.text(
            "ALTER TABLE customers ADD COLUMN customer_type VARCHAR(20) DEFAULT 'cash'"
        ))
        db.session.commit()
        print("Added customer_type column to customers table.")
    except Exception as e:
        db.session.rollback()
        if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
            print("Column customer_type already exists.")
        else:
            raise

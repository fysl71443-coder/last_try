"""إضافة أعمدة customer_type و discount_percent و active و created_at لجدول customers

Revision ID: cust_cols_01
Revises: je_pay_inv_01
Create Date: 2026-02-03

"""
from alembic import op
from sqlalchemy import text


revision = 'cust_cols_01'
down_revision = 'je_pay_inv_01'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        op.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS customer_type VARCHAR(20) DEFAULT 'cash'"))
        op.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS discount_percent NUMERIC(5,2) DEFAULT 0"))
        op.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT true"))
        op.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS created_at TIMESTAMP"))
    else:
        # SQLite: add columns one by one, ignore if already present
        for col, spec in [
            ('customer_type', "VARCHAR(20) DEFAULT 'cash'"),
            ('discount_percent', 'NUMERIC(5,2) DEFAULT 0'),
            ('active', 'INTEGER DEFAULT 1'),
            ('created_at', 'TIMESTAMP'),
        ]:
            try:
                op.execute(text(f"ALTER TABLE customers ADD COLUMN {col} {spec}"))
            except Exception:
                pass


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.execute(text("ALTER TABLE customers DROP COLUMN IF EXISTS created_at"))
        op.execute(text("ALTER TABLE customers DROP COLUMN IF EXISTS active"))
        op.execute(text("ALTER TABLE customers DROP COLUMN IF EXISTS discount_percent"))
        op.execute(text("ALTER TABLE customers DROP COLUMN IF EXISTS customer_type"))
    else:
        # SQLite: no DROP COLUMN IF EXISTS; drop one by one
        for col in ('created_at', 'active', 'discount_percent', 'customer_type'):
            try:
                op.drop_column('customers', col)
            except Exception:
                pass

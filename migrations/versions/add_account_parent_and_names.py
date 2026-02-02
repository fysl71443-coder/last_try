"""Add parent_account_code, name_ar, name_en to accounts for sub-account creation

Revision ID: acc_parent_01
Revises: jl_acc_idx_01
Create Date: 2026-01-31

"""
from alembic import op
from sqlalchemy import text


revision = 'acc_parent_01'
down_revision = 'jl_acc_idx_01'
branch_labels = None
depends_on = None


def upgrade():
    for col, typ in [
        ('parent_account_code', 'VARCHAR(20)'),
        ('name_ar', 'VARCHAR(200)'),
        ('name_en', 'VARCHAR(200)'),
    ]:
        try:
            op.execute(text(f"ALTER TABLE accounts ADD COLUMN {col} {typ}"))
        except Exception:
            pass


def downgrade():
    # Optional: remove columns (some DBs don't support DROP COLUMN easily)
    pass

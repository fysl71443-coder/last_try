"""Add liability_account_code to expense_invoices for platform/gov payables

Revision ID: exp_liab_01
Revises: acc_parent_01
Create Date: 2026-01-31

"""
from alembic import op
from sqlalchemy import text


revision = 'exp_liab_01'
down_revision = 'acc_parent_01'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.execute(text("ALTER TABLE expense_invoices ADD COLUMN liability_account_code VARCHAR(20)"))
    except Exception:
        pass


def downgrade():
    pass

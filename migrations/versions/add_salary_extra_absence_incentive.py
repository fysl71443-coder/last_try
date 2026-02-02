"""Add extra, absence, incentive to salaries for payroll breakdown

Revision ID: salary_extra_01
Revises: jl_acc_idx_01
Create Date: 2026-01-31

"""
from alembic import op
from sqlalchemy import text


revision = 'salary_extra_01'
down_revision = 'jl_acc_idx_01'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.execute(text('ALTER TABLE salaries ADD COLUMN extra NUMERIC(12,2) DEFAULT 0'))
    except Exception:
        pass
    try:
        op.execute(text('ALTER TABLE salaries ADD COLUMN absence NUMERIC(12,2) DEFAULT 0'))
    except Exception:
        pass
    try:
        op.execute(text('ALTER TABLE salaries ADD COLUMN incentive NUMERIC(12,2) DEFAULT 0'))
    except Exception:
        pass


def downgrade():
    try:
        op.drop_column('salaries', 'incentive')
    except Exception:
        pass
    try:
        op.drop_column('salaries', 'absence')
    except Exception:
        pass
    try:
        op.drop_column('salaries', 'extra')
    except Exception:
        pass

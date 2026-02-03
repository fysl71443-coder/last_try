"""Index on journal_lines.line_date for faster date-range filters (cash flow, trial balance, etc.)

Revision ID: jl_line_date_idx
Revises: cashflow_01
Create Date: 2026-02-03

"""
from alembic import op
from sqlalchemy import text


revision = 'jl_line_date_idx'
down_revision = 'cashflow_01'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_journal_lines_line_date ON journal_lines (line_date)"))
    # مركّب للاستعلامات الشائعة: نطاق تاريخ + حساب
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_journal_lines_line_date_account ON journal_lines (line_date, account_id)"))


def downgrade():
    op.execute(text("DROP INDEX IF EXISTS idx_journal_lines_line_date_account"))
    op.execute(text("DROP INDEX IF EXISTS idx_journal_lines_line_date"))

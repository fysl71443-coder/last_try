"""Add index on journal_lines.account_id for faster joins and filters

Revision ID: jl_acc_idx_01
Revises: add_acc_src_01
Create Date: 2026-01-27

"""
from alembic import op
from sqlalchemy import text


revision = 'jl_acc_idx_01'
down_revision = 'add_acc_src_01'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_journal_lines_account_id ON journal_lines (account_id)"
    ))


def downgrade():
    op.execute(text("DROP INDEX IF EXISTS ix_journal_lines_account_id"))

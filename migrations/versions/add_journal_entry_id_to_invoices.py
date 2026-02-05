"""Add journal_entry_id to sales_invoices for accounting integration

Revision ID: add_je_id_01
Revises: b4fe997e5c15
Create Date: 2026-01-27

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_je_id_01'
down_revision = 'b4fe997e5c15'
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    """Return True if column exists on table (idempotent check)."""
    if conn.dialect.name == 'sqlite':
        result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in result)
    from sqlalchemy import inspect
    insp = inspect(conn)
    cols = [c['name'] for c in insp.get_columns(table)]
    return column in cols


def upgrade():
    conn = op.get_bind()
    if _column_exists(conn, 'sales_invoices', 'journal_entry_id'):
        return
    op.add_column('sales_invoices', sa.Column('journal_entry_id', sa.Integer(), nullable=True))


def downgrade():
    conn = op.get_bind()
    if not _column_exists(conn, 'sales_invoices', 'journal_entry_id'):
        return
    op.drop_column('sales_invoices', 'journal_entry_id')

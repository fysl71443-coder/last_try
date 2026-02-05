"""Add source_system, source_ref_type, source_ref_id to journal_entries for Node accounting

Revision ID: add_acc_src_01
Revises: add_je_id_01
Create Date: 2026-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'add_acc_src_01'
down_revision = 'add_je_id_01'
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    """Return True if column exists (SQLite and others)."""
    if conn.dialect.name == 'sqlite':
        result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in result)
    from sqlalchemy import inspect
    return column in [c['name'] for c in inspect(conn).get_columns(table)]


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, 'journal_entries', 'source_system'):
        op.add_column('journal_entries', sa.Column('source_system', sa.String(50), nullable=True))
    if not _column_exists(conn, 'journal_entries', 'source_ref_type'):
        op.add_column('journal_entries', sa.Column('source_ref_type', sa.String(50), nullable=True))
    if not _column_exists(conn, 'journal_entries', 'source_ref_id'):
        op.add_column('journal_entries', sa.Column('source_ref_id', sa.String(100), nullable=True))


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, 'journal_entries', 'source_ref_id'):
        op.drop_column('journal_entries', 'source_ref_id')
    if _column_exists(conn, 'journal_entries', 'source_ref_type'):
        op.drop_column('journal_entries', 'source_ref_type')
    if _column_exists(conn, 'journal_entries', 'source_system'):
        op.drop_column('journal_entries', 'source_system')

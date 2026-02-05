"""إضافة reopened_at و reopened_by لجدول fiscal_years (إعادة فتح مُتحكَّمة)

Revision ID: fiscal_reopen_01
Revises: audit_find_01
Create Date: 2026-02-04

"""
from alembic import op
import sqlalchemy as sa


revision = 'fiscal_reopen_01'
down_revision = 'audit_find_01'
branch_labels = None
depends_on = None


def _column_exists(conn, table, col):
    if conn.dialect.name == 'sqlite':
        # SQLite PRAGMA does not accept bound params for table name
        r = conn.execute(sa.text(f"PRAGMA table_info({table})"))
        for row in r:
            if row[1] == col:
                return True
        return False
    from sqlalchemy import inspect
    return col in [c["name"] for c in inspect(conn).get_columns(table)]


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, 'fiscal_years', 'reopened_at'):
        op.add_column('fiscal_years', sa.Column('reopened_at', sa.DateTime(), nullable=True))
    if not _column_exists(conn, 'fiscal_years', 'reopened_by'):
        op.add_column('fiscal_years', sa.Column('reopened_by', sa.Integer(), nullable=True))


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, 'fiscal_years', 'reopened_by'):
        op.drop_column('fiscal_years', 'reopened_by')
    if _column_exists(conn, 'fiscal_years', 'reopened_at'):
        op.drop_column('fiscal_years', 'reopened_at')

"""Add year_name, closed_at, closed_by to fiscal_years

Revision ID: fiscal_02
Revises: fiscal_01
Create Date: 2026-02-04

"""
from alembic import op
import sqlalchemy as sa


revision = 'fiscal_02'
down_revision = 'fiscal_01'
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    if conn.dialect.name == 'sqlite':
        result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in result)
    from sqlalchemy import inspect
    return column in [c['name'] for c in inspect(conn).get_columns(table)]


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, 'fiscal_years', 'year_name'):
        op.add_column('fiscal_years', sa.Column('year_name', sa.String(50), nullable=True))
    if not _column_exists(conn, 'fiscal_years', 'closed_at'):
        op.add_column('fiscal_years', sa.Column('closed_at', sa.DateTime(), nullable=True))
    if not _column_exists(conn, 'fiscal_years', 'closed_by'):
        op.add_column('fiscal_years', sa.Column('closed_by', sa.Integer(), nullable=True))


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, 'fiscal_years', 'closed_by'):
        op.drop_column('fiscal_years', 'closed_by')
    if _column_exists(conn, 'fiscal_years', 'closed_at'):
        op.drop_column('fiscal_years', 'closed_at')
    if _column_exists(conn, 'fiscal_years', 'year_name'):
        op.drop_column('fiscal_years', 'year_name')

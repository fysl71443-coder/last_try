"""جدول كاش لقطات التدقيق audit_snapshots

Revision ID: audit_snap_01
Revises: fiscal_reopen_01
Create Date: 2026-02-04

"""
from alembic import op
import sqlalchemy as sa


revision = 'audit_snap_01'
down_revision = 'fiscal_reopen_01'
branch_labels = None
depends_on = None


def _table_exists(conn, name):
    if conn.dialect.name == 'sqlite':
        r = conn.execute(sa.text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{name}'"))
        return r.scalar() is not None
    from sqlalchemy import inspect
    return name in inspect(conn).get_table_names()


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, 'audit_snapshots'):
        op.create_table(
            'audit_snapshots',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('fiscal_year_id', sa.Integer(), nullable=False),
            sa.Column('total', sa.Integer(), nullable=False),
            sa.Column('high', sa.Integer(), nullable=False),
            sa.Column('medium', sa.Integer(), nullable=False),
            sa.Column('low', sa.Integer(), nullable=False),
            sa.Column('run_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['fiscal_year_id'], ['fiscal_years.id']),
        )
        op.create_index('ix_audit_snapshots_fiscal_year_id', 'audit_snapshots', ['fiscal_year_id'])
        op.create_index('ix_audit_snapshots_run_at', 'audit_snapshots', ['run_at'])


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, 'audit_snapshots'):
        op.drop_index('ix_audit_snapshots_run_at', 'audit_snapshots')
        op.drop_index('ix_audit_snapshots_fiscal_year_id', 'audit_snapshots')
        op.drop_table('audit_snapshots')

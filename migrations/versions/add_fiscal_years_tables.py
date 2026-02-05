"""السنوات المالية: fiscal_years، فترات استثنائية، سجل تدقيق

Revision ID: fiscal_01
Revises: perf_idx_01
Create Date: 2026-02-04

"""
from alembic import op
import sqlalchemy as sa


revision = 'fiscal_01'
down_revision = 'perf_idx_01'
branch_labels = None
depends_on = None


def _table_exists(conn, name):
    if conn.dialect.name == 'sqlite':
        r = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": name})
        return r.scalar() is not None
    from sqlalchemy import inspect
    return name in inspect(conn).get_table_names()


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, 'fiscal_years'):
        op.create_table(
            'fiscal_years',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('year', sa.Integer(), nullable=False),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('end_date', sa.Date(), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('closed_until', sa.Date(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_fiscal_years_year', 'fiscal_years', ['year'])
        op.create_index('ix_fiscal_years_status', 'fiscal_years', ['status'])

    if not _table_exists(conn, 'fiscal_year_exceptional_periods'):
        op.create_table(
            'fiscal_year_exceptional_periods',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('fiscal_year_id', sa.Integer(), nullable=False),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('end_date', sa.Date(), nullable=False),
            sa.Column('reason', sa.String(500), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['fiscal_year_id'], ['fiscal_years.id']),
            sa.ForeignKeyConstraint(['created_by'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_fiscal_year_exceptional_periods_fiscal_year_id', 'fiscal_year_exceptional_periods', ['fiscal_year_id'])

    if not _table_exists(conn, 'fiscal_year_audit_log'):
        op.create_table(
            'fiscal_year_audit_log',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('fiscal_year_id', sa.Integer(), nullable=False),
            sa.Column('action', sa.String(50), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('details_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['fiscal_year_id'], ['fiscal_years.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_fiscal_year_audit_log_fiscal_year_id', 'fiscal_year_audit_log', ['fiscal_year_id'])


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, 'fiscal_year_audit_log'):
        op.drop_index('ix_fiscal_year_audit_log_fiscal_year_id', 'fiscal_year_audit_log')
        op.drop_table('fiscal_year_audit_log')
    if _table_exists(conn, 'fiscal_year_exceptional_periods'):
        op.drop_index('ix_fiscal_year_exceptional_periods_fiscal_year_id', 'fiscal_year_exceptional_periods')
        op.drop_table('fiscal_year_exceptional_periods')
    if _table_exists(conn, 'fiscal_years'):
        op.drop_index('ix_fiscal_years_status', 'fiscal_years')
        op.drop_index('ix_fiscal_years_year', 'fiscal_years')
        op.drop_table('fiscal_years')

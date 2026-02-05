"""جدول ملاحظات التدقيق audit_findings

Revision ID: audit_find_01
Revises: fiscal_02
Create Date: 2026-02-04

"""
from alembic import op
import sqlalchemy as sa


revision = 'audit_find_01'
down_revision = 'fiscal_02'
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
    if not _table_exists(conn, 'audit_findings'):
        op.create_table(
            'audit_findings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('fiscal_year_id', sa.Integer(), nullable=True),
            sa.Column('journal_entry_id', sa.Integer(), nullable=True),
            sa.Column('entry_number', sa.String(80), nullable=True),
            sa.Column('issue_type_ar', sa.String(100), nullable=False),
            sa.Column('place_ar', sa.String(100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('difference_details', sa.Text(), nullable=True),
            sa.Column('root_cause_ar', sa.String(150), nullable=True),
            sa.Column('severity', sa.String(20), nullable=False),
            sa.Column('correction_method', sa.String(300), nullable=True),
            sa.Column('entry_date', sa.Date(), nullable=True),
            sa.Column('audit_run_from', sa.Date(), nullable=True),
            sa.Column('audit_run_to', sa.Date(), nullable=True),
            sa.Column('audit_run_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['fiscal_year_id'], ['fiscal_years.id']),
            sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entries.id']),
        )
        op.create_index('ix_audit_findings_fiscal_year_id', 'audit_findings', ['fiscal_year_id'])
        op.create_index('ix_audit_findings_journal_entry_id', 'audit_findings', ['journal_entry_id'])
        op.create_index('ix_audit_findings_severity', 'audit_findings', ['severity'])


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, 'audit_findings'):
        op.drop_index('ix_audit_findings_severity', 'audit_findings')
        op.drop_index('ix_audit_findings_journal_entry_id', 'audit_findings')
        op.drop_index('ix_audit_findings_fiscal_year_id', 'audit_findings')
        op.drop_table('audit_findings')

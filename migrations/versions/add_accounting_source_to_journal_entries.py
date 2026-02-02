"""Add source_system, source_ref_type, source_ref_id to journal_entries for Node accounting

Revision ID: add_acc_src_01
Revises: add_je_id_01
Create Date: 2026-01-27

"""
from alembic import op
from sqlalchemy import text


revision = 'add_acc_src_01'
down_revision = 'add_je_id_01'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text('ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS source_system VARCHAR(50)'))
    op.execute(text('ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS source_ref_type VARCHAR(50)'))
    op.execute(text('ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS source_ref_id VARCHAR(100)'))


def downgrade():
    op.drop_column('journal_entries', 'source_ref_id')
    op.drop_column('journal_entries', 'source_ref_type')
    op.drop_column('journal_entries', 'source_system')

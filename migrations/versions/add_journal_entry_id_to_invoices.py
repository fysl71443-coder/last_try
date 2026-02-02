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


def upgrade():
    op.add_column('sales_invoices', sa.Column('journal_entry_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('sales_invoices', 'journal_entry_id')

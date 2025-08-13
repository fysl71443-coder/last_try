"""
add_common_indexes

Revision ID: a1b2c3d4e5f6
Revises: 9cdfd5fec1cc
Create Date: 2025-08-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9cdfd5fec1cc'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Sales
    op.create_index('ix_sales_invoices_date', 'sales_invoices', ['date'], unique=False)
    op.create_index('ix_sales_invoices_branch', 'sales_invoices', ['branch'], unique=False)
    op.create_index('ix_sales_items_invoice_id', 'sales_invoice_items', ['invoice_id'], unique=False)
    # Purchases
    op.create_index('ix_purchase_invoices_date', 'purchase_invoices', ['date'], unique=False)
    op.create_index('ix_purchase_items_invoice_id', 'purchase_invoice_items', ['invoice_id'], unique=False)
    # Expenses
    op.create_index('ix_expense_invoices_date', 'expense_invoices', ['date'], unique=False)
    op.create_index('ix_expense_items_invoice_id', 'expense_invoice_items', ['invoice_id'], unique=False)
    # Payments
    op.create_index('ix_payments_invoice', 'payments', ['invoice_id', 'invoice_type'], unique=False)


def downgrade() -> None:
    # Payments
    op.drop_index('ix_payments_invoice', table_name='payments')
    # Expenses
    op.drop_index('ix_expense_items_invoice_id', table_name='expense_invoice_items')
    op.drop_index('ix_expense_invoices_date', table_name='expense_invoices')
    # Purchases
    op.drop_index('ix_purchase_items_invoice_id', table_name='purchase_invoice_items')
    op.drop_index('ix_purchase_invoices_date', table_name='purchase_invoices')
    # Sales
    op.drop_index('ix_sales_items_invoice_id', table_name='sales_invoice_items')
    op.drop_index('ix_sales_invoices_branch', table_name='sales_invoices')
    op.drop_index('ix_sales_invoices_date', table_name='sales_invoices')


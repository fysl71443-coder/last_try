"""
Add POS tables: customers, menu_sections, menu_section_items, dining_tables
and extend sales_invoices with table_number, customer_id, customer_phone

Revision ID: 8f1a2b3c4d5e
Revises: 9cdfd5fec1cc
Create Date: 2025-08-13
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8f1a2b3c4d5e'
down_revision = '24a825dc5561'
branch_labels = None
depends_on = None

def upgrade():
    # customers
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('discount_percent', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # menu_sections
    op.create_table(
        'menu_sections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('branch', sa.String(length=50), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
    )

    # menu_section_items
    op.create_table(
        'menu_section_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.Column('meal_id', sa.Integer(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['section_id'], ['menu_sections.id']),
        sa.ForeignKeyConstraint(['meal_id'], ['meals.id']),
    )

    # dining_tables
    op.create_table(
        'dining_tables',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('branch', sa.String(length=50), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('active', sa.Boolean(), server_default=sa.text('true')),
    )
    op.create_unique_constraint('uq_dining_table_branch_number', 'dining_tables', ['branch','number'])

    # extend sales_invoices
    op.add_column('sales_invoices', sa.Column('table_number', sa.Integer(), nullable=True))
    op.add_column('sales_invoices', sa.Column('customer_id', sa.Integer(), nullable=True))
    op.add_column('sales_invoices', sa.Column('customer_phone', sa.String(length=30), nullable=True))
    op.create_foreign_key('fk_sales_customer', 'sales_invoices', 'customers', ['customer_id'], ['id'])

    # helpful indexes
    op.create_index('ix_sales_branch_table_status', 'sales_invoices', ['branch','table_number','status'])
    op.create_index('ix_menu_section_branch_order', 'menu_sections', ['branch','display_order'])

def downgrade():
    op.drop_index('ix_menu_section_branch_order', table_name='menu_sections')
    op.drop_index('ix_sales_branch_table_status', table_name='sales_invoices')
    op.drop_constraint('fk_sales_customer', 'sales_invoices', type_='foreignkey')
    op.drop_column('sales_invoices', 'customer_phone')
    op.drop_column('sales_invoices', 'customer_id')
    op.drop_column('sales_invoices', 'table_number')
    op.drop_constraint('uq_dining_table_branch_number', 'dining_tables', type_='unique')
    op.drop_table('dining_tables')
    op.drop_table('menu_section_items')
    op.drop_table('menu_sections')
    op.drop_table('customers')


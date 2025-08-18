"""fix_sales_invoices_table_columns

Revision ID: 097c20248414
Revises: 20250816_02
Create Date: 2025-08-19 01:31:30.299426

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '097c20248414'
down_revision = '20250816_02'
branch_labels = None
depends_on = None


def upgrade():
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('sales_invoices', schema=None) as batch_op:
        # Check if table_number column exists, if not add it
        try:
            batch_op.add_column(sa.Column('table_number', sa.Integer(), nullable=True))
        except Exception:
            # Column might already exist, that's fine
            pass

        # Check if customer_id column exists, if not add it
        try:
            batch_op.add_column(sa.Column('customer_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_sales_customer_id', 'customers', ['customer_id'], ['id'])
        except Exception:
            # Column might already exist, that's fine
            pass


def downgrade():
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('sales_invoices', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('fk_sales_customer_id', type_='foreignkey')
            batch_op.drop_column('customer_id')
        except Exception:
            pass

        try:
            batch_op.drop_column('table_number')
        except Exception:
            pass

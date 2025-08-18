"""
Add missing Settings receipt columns and logo_url; ensure menu_categories table exists (idempotent)

Revision ID: 20250816_02
Revises: 20250814_01
Create Date: 2025-08-16
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250816_02'
down_revision = '20250814_01'
branch_labels = None
depends_on = None


def table_exists(bind, table_name: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return table_name in insp.get_table_names()
    except Exception:
        return False


def column_exists(bind, table_name: str, column_name: str) -> bool:
    insp = sa.inspect(bind)
    try:
        cols = [c['name'] for c in insp.get_columns(table_name)]
        return column_name in cols
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()

    # 1) Ensure menu_categories exists
    if not table_exists(bind, 'menu_categories'):
        op.create_table(
            'menu_categories',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=200), nullable=False, unique=True),
            sa.Column('active', sa.Boolean(), server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        )

    # 2) Add Settings receipt-related columns and logo_url if missing
    if table_exists(bind, 'settings'):
        if not column_exists(bind, 'settings', 'receipt_paper_width'):
            op.add_column('settings', sa.Column('receipt_paper_width', sa.String(length=4), nullable=True))
        if not column_exists(bind, 'settings', 'receipt_margin_top_mm'):
            op.add_column('settings', sa.Column('receipt_margin_top_mm', sa.Integer(), nullable=True))
        if not column_exists(bind, 'settings', 'receipt_margin_bottom_mm'):
            op.add_column('settings', sa.Column('receipt_margin_bottom_mm', sa.Integer(), nullable=True))
        if not column_exists(bind, 'settings', 'receipt_margin_left_mm'):
            op.add_column('settings', sa.Column('receipt_margin_left_mm', sa.Integer(), nullable=True))
        if not column_exists(bind, 'settings', 'receipt_margin_right_mm'):
            op.add_column('settings', sa.Column('receipt_margin_right_mm', sa.Integer(), nullable=True))
        if not column_exists(bind, 'settings', 'receipt_font_size'):
            op.add_column('settings', sa.Column('receipt_font_size', sa.Integer(), nullable=True))
        if not column_exists(bind, 'settings', 'receipt_show_logo'):
            op.add_column('settings', sa.Column('receipt_show_logo', sa.Boolean(), server_default=sa.text('true')))
        if not column_exists(bind, 'settings', 'receipt_show_tax_number'):
            op.add_column('settings', sa.Column('receipt_show_tax_number', sa.Boolean(), server_default=sa.text('true')))
        if not column_exists(bind, 'settings', 'receipt_footer_text'):
            op.add_column('settings', sa.Column('receipt_footer_text', sa.String(length=300), nullable=True))
        if not column_exists(bind, 'settings', 'logo_url'):
            op.add_column('settings', sa.Column('logo_url', sa.String(length=300), nullable=True))


def downgrade():
    # Best-effort: drop added columns if exist; do not drop menu_categories table automatically
    bind = op.get_bind()
    if table_exists(bind, 'settings'):
        for col in [
            'logo_url',
            'receipt_footer_text',
            'receipt_show_tax_number',
            'receipt_show_logo',
            'receipt_font_size',
            'receipt_margin_right_mm',
            'receipt_margin_left_mm',
            'receipt_margin_bottom_mm',
            'receipt_margin_top_mm',
            'receipt_paper_width',
        ]:
            try:
                if column_exists(bind, 'settings', col):
                    op.drop_column('settings', col)
            except Exception:
                pass

